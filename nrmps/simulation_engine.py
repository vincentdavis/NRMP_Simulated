"""Legacy simulation engine (model 1): interview rows, pre-interview ratings and pre-interview rankings.

Model:

- An applicant's true utility for a program is U = sum over attributes of (applicant weight x program attribute
  score); a program's true utility for an applicant is V = sum of (program weight x applicant attribute score).
  Weights sum to 1 and attribute scores lie in 0-1, so utilities lie in 0-1.
- Observations add Gaussian noise: observed = true + N(0, sigma), with sigma the configured rating error.
  sigma = 0 means perfect information.
- Ranks are strict: 1 is the highest observed score; ties go to the lower program (or applicant) id.

Every step runs in one transaction that locks the simulation row, computes with numpy and writes in batches.

Phase 2 of the plan (docs/PROJECT_REVIEW.md) replaces this module with a seeded, vectorised engine package, and
Phase 3 builds the remaining stages (applications, invitations, interviews, rank lists, match) on that engine. Do
not extend this module with new stages.
"""

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from itertools import islice

import numpy as np
from django.db import connection, transaction

from .exceptions import MissingConfigError, PopulationError
from .limits import check_market_size
from .models import Interview, School, Simulation, SimulationConfig, Student

# Rows per UPDATE batch. Small enough for SQLite's parameter limit and to keep memory flat.
WRITE_BATCH_SIZE = 2000


def latest_config(simulation: Simulation) -> SimulationConfig:
    """Return the simulation's latest configuration, or raise MissingConfigError."""
    config = simulation.configs.order_by("-id").first()
    if config is None:
        raise MissingConfigError()
    return config


def _batches(items: Iterable, size: int) -> Iterator[list]:
    """Yield lists of at most `size` items."""
    iterator = iter(items)
    while batch := list(islice(iterator, size)):
        yield batch


def _update_columns(model, pks: Sequence[int], columns: dict[str, Sequence]) -> None:
    """Set several columns on many rows. `columns` maps field names to sequences aligned with `pks`; NaN -> NULL.

    PostgreSQL loads the values with COPY into a temporary table and applies one UPDATE ... FROM; other databases
    (SQLite) run one prepared UPDATE per row in batches, which is fast there.
    """
    if not len(pks):
        return
    fields = [model._meta.get_field(name) for name in columns]
    values = [_to_python(columns[field.name], integer=field.get_internal_type() == "IntegerField") for field in fields]
    rows = zip((int(pk) for pk in pks), *values, strict=True)
    if connection.vendor == "postgresql":
        _update_columns_postgresql(model, fields, rows)
        return
    q = connection.ops.quote_name
    assignments = ", ".join(f"{q(field.column)} = %s" for field in fields)
    sql = f"UPDATE {q(model._meta.db_table)} SET {assignments} WHERE {q('id')} = %s"  # noqa: S608 (identifiers from model meta)
    with connection.cursor() as cursor:
        for batch in _batches(rows, WRITE_BATCH_SIZE):
            cursor.executemany(sql, [(*row[1:], row[0]) for row in batch])


def _update_columns_postgresql(model, fields, rows) -> None:
    """COPY (id, values...) rows into a temporary table, then update the model's table from it in one statement."""
    q = connection.ops.quote_name
    temp = q("nrmps_bulk_update")
    column_defs = ", ".join(
        f"{q(field.column)} {'integer' if field.get_internal_type() == 'IntegerField' else 'double precision'}"
        for field in fields
    )
    column_list = ", ".join(q(field.column) for field in fields)
    assignments = ", ".join(f"{q(field.column)} = u.{q(field.column)}" for field in fields)
    with connection.cursor() as cursor:
        cursor.execute(f"DROP TABLE IF EXISTS {temp}")
        cursor.execute(f"CREATE TEMPORARY TABLE {temp} (id bigint PRIMARY KEY, {column_defs}) ON COMMIT DROP")
        with cursor.cursor.copy(f"COPY {temp} (id, {column_list}) FROM STDIN") as copy:
            for row in rows:
                copy.write_row(row)
        cursor.execute(
            f"UPDATE {q(model._meta.db_table)} AS t SET {assignments} FROM {temp} AS u WHERE t.{q('id')} = u.id"  # noqa: S608
        )


def _to_python(values: Sequence, *, integer: bool = False) -> list:
    """Convert a numpy array (or sequence) to Python floats, or ints if `integer`, mapping NaN to None."""
    convert = int if integer else float
    return [None if np.isnan(v) else convert(v) for v in np.asarray(values, dtype=float)]


# --- Interview rows ---------------------------------------------------------------------------------------------


def initialize_interview(simulation: Simulation) -> int:
    """Recreate the interview rows: one per applicant x program pair (the full cross-product).

    Deletes the simulation's existing interview rows first. Returns the number of rows created.
    """
    with transaction.atomic():
        simulation.lock()
        n_students = simulation.students.count()
        n_schools = simulation.schools.count()
        if not n_students or not n_schools:
            raise PopulationError("Generate or upload both applicants and programs before initializing interviews.")
        check_market_size(n_students, n_schools)
        Interview.objects.filter(simulation=simulation).delete()
        _insert_cross_product(simulation)
        simulation.set_stage("initialized")
        return n_students * n_schools


def _insert_cross_product(simulation: Simulation) -> None:
    """Insert one interview row per applicant x program pair with a single INSERT ... SELECT.

    Much faster than building model instances. Columns not listed are nullable and start as NULL; the listed ones
    get the model defaults. Ids follow (applicant id, program id) order.
    """
    q = connection.ops.quote_name
    meta = Interview._meta
    defaults = ["status", "student_applied", "student_signal", "student_accepted", "school_invited"]
    columns = ["simulation", "student", "school", *defaults]
    column_sql = ", ".join(q(meta.get_field(name).column) for name in columns)
    placeholders = ", ".join(["%s"] * len(defaults))
    sql = (
        f"INSERT INTO {q(meta.db_table)} ({column_sql}) "  # noqa: S608 (identifiers come from model meta)
        f"SELECT %s, s.{q('id')}, p.{q('id')}, {placeholders} "
        f"FROM {q(Student._meta.db_table)} s CROSS JOIN {q(School._meta.db_table)} p "
        f"WHERE s.{q('simulation_id')} = %s AND p.{q('simulation_id')} = %s "
        f"ORDER BY s.{q('id')}, p.{q('id')}"
    )
    params = [simulation.pk, *(meta.get_field(name).get_default() for name in defaults), simulation.pk, simulation.pk]
    with connection.cursor() as cursor:
        cursor.execute(sql, params)


# --- Populations as matrices ------------------------------------------------------------------------------------


@dataclass
class _Side:
    """One side of the market as arrays: ids, attribute scores and preference weights."""

    ids: np.ndarray  # (n,) database ids, ascending
    scores: list[dict]  # score_meta per member: attribute -> score
    weights: list[dict]  # meta_preference per member: attribute -> weight


def _load_side(model, simulation: Simulation) -> _Side:
    """Load a population (students or schools) ordered by id."""
    rows = list(
        model.objects.filter(simulation=simulation).order_by("id").values_list("id", "score_meta", "meta_preference")
    )
    return _Side(
        ids=np.array([row[0] for row in rows], dtype=np.int64),
        scores=[row[1] or {} for row in rows],
        weights=[row[2] or {} for row in rows],
    )


def _utilities(raters: _Side, rated: _Side, rater_label: str, rated_label: str) -> np.ndarray:
    """Return the true utility matrix U[r, t] = sum_k weight[r][k] * score[t][k] (raters x rated).

    Raises PopulationError with a user-facing explanation when the two sides do not fit together (SIM-4, STG-11).
    """
    no_weights = [int(pk) for pk, w in zip(raters.ids, raters.weights, strict=True) if not w]
    if no_weights:
        raise PopulationError(
            f"{len(no_weights)} {rater_label}s have no preference weights (for example id {no_weights[0]}), so every "
            f"{rated_label} would get the same score. Generate the {rater_label}s instead of uploading them, or add "
            "preference weights."
        )
    keys = sorted({key for w in raters.weights for key in w})
    missing = {key: [int(pk) for pk, s in zip(rated.ids, rated.scores, strict=True) if key not in s] for key in keys}
    missing = {key: ids for key, ids in missing.items() if ids}
    if missing:
        key, ids = next(iter(missing.items()))
        raise PopulationError(
            f"{rater_label.capitalize()} preferences use the attribute(s) {', '.join(sorted(missing))}, but "
            f"{len(ids)} {rated_label}s have no score for '{key}' (for example id {ids[0]}). This happens when the "
            f"attribute lists changed after one population was generated: regenerate both populations."
        )
    try:
        weights = np.array([[float(w.get(key, 0.0)) for key in keys] for w in raters.weights])
        scores = np.array([[float(s[key]) for key in keys] for s in rated.scores])
    except (TypeError, ValueError) as exc:
        raise PopulationError(f"A {rater_label} weight or {rated_label} attribute score is not a number.") from exc
    return weights @ scores.T


def _noise(rng: np.random.Generator, sigma: float, size: int) -> np.ndarray:
    """Return N(0, sigma) noise; exactly zero when sigma is 0."""
    if sigma == 0:
        return np.zeros(size)
    return rng.normal(0.0, sigma, size)


def _strict_ranks(groups: np.ndarray, scores: np.ndarray, tie_break: np.ndarray) -> np.ndarray:
    """Rank rows within each group: 1 = highest score; equal scores are ordered by ascending `tie_break`.

    Rows whose score is NaN get rank NaN.
    """
    ranks = np.full(len(scores), np.nan)
    valid = ~np.isnan(scores)
    if not valid.any():
        return ranks
    idx = np.flatnonzero(valid)
    # lexsort sorts by the last key first: group, then score descending, then tie-break ascending.
    order = idx[np.lexsort((tie_break[idx], -scores[idx], groups[idx]))]
    sorted_groups = groups[order]
    starts = np.r_[0, np.flatnonzero(sorted_groups[1:] != sorted_groups[:-1]) + 1]
    group_start = np.repeat(starts, np.diff(np.r_[starts, len(order)]))
    ranks[order] = np.arange(len(order)) - group_start + 1
    return ranks


@dataclass
class _Pairs:
    """Interview rows as parallel arrays."""

    ids: np.ndarray
    student_ids: np.ndarray
    school_ids: np.ndarray


def _load_pairs(simulation: Simulation, **filters) -> _Pairs:
    """Load the simulation's interview rows (optionally filtered), ordered by id."""
    rows = np.array(
        list(
            Interview.objects.filter(simulation=simulation, **filters)
            .order_by("id")
            .values_list("id", "student_id", "school_id")
        ),
        dtype=np.int64,
    ).reshape(-1, 3)
    return _Pairs(ids=rows[:, 0], student_ids=rows[:, 1], school_ids=rows[:, 2])


def _rate_pairs(simulation: Simulation, pairs: _Pairs, config: SimulationConfig, rng, *, post: bool) -> dict:
    """Compute true utilities, noisy observations and strict ranks for the given interview rows.

    Returns a dict of column name -> array, aligned with `pairs.ids`.
    """
    students = _load_side(Student, simulation)
    schools = _load_side(School, simulation)
    if not len(students.ids) or not len(schools.ids):
        raise PopulationError("Generate or upload both applicants and programs first.")
    u = _utilities(students, schools, "applicant", "program")  # applicant -> program
    v = _utilities(schools, students, "program", "applicant")  # program -> applicant

    si = np.searchsorted(students.ids, pairs.student_ids)
    pi = np.searchsorted(schools.ids, pairs.school_ids)
    u_true = u[si, pi]
    v_true = v[pi, si]

    stage = "post" if post else "pre"
    sigma_a = float(getattr(config, f"applicant_{stage}_interview_rating_error"))
    sigma_p = float(getattr(config, f"school_{stage}_interview_rating_error"))
    u_obs = u_true + _noise(rng, sigma_a, len(u_true))
    v_obs = v_true + _noise(rng, sigma_p, len(v_true))

    columns = {
        f"student_{stage}_observed_score_of_school": u_obs,
        f"school_{stage}_observed_score_of_student": v_obs,
        f"students_{stage}_rank_of_school": _strict_ranks(pairs.student_ids, u_obs, pairs.school_ids),
        f"schools_{stage}_rank_of_student": _strict_ranks(pairs.school_ids, v_obs, pairs.student_ids),
    }
    if not post:
        columns["student_true_score_of_school"] = u_true
        columns["school_true_score_of_student"] = v_true
    return columns


# --- Pre-interview stage ----------------------------------------------------------------------------------------


def compute_pre_interview_scores_and_rankings(simulation: Simulation, rng: np.random.Generator | None = None) -> int:
    """Run the whole pre-interview stage: true utilities, noisy ratings and strict ranks, for both sides.

    Writes the true-score, observed-score and rank columns of every interview row. Returns the number of rows.
    """
    rng = rng or np.random.default_rng()
    with transaction.atomic():
        simulation.lock()
        config = latest_config(simulation)
        pairs = _load_pairs(simulation)
        if not len(pairs.ids):
            raise PopulationError("Initialize the interviews first.")
        columns = _rate_pairs(simulation, pairs, config, rng, post=False)
        _update_columns(Interview, pairs.ids, columns)
        simulation.set_stage("pre_interview")
        return len(pairs.ids)


def students_rate_schools_pre_interview(simulation: Simulation, rng: np.random.Generator | None = None) -> None:
    """Write applicants' true utilities and noisy pre-interview ratings of programs; clear their stale ranks."""
    _rate_one_side(simulation, rng, side="student")


def schools_rate_students_pre_interview(simulation: Simulation, rng: np.random.Generator | None = None) -> None:
    """Write programs' true utilities and noisy pre-interview ratings of applicants; clear their stale ranks."""
    _rate_one_side(simulation, rng, side="school")


def _rate_one_side(simulation: Simulation, rng, *, side: str) -> None:
    rng = rng or np.random.default_rng()
    with transaction.atomic():
        simulation.lock()
        config = latest_config(simulation)
        pairs = _load_pairs(simulation)
        columns = _rate_pairs(simulation, pairs, config, rng, post=False)
        if side == "student":
            keep = ("student_true_score_of_school", "student_pre_observed_score_of_school")
            stale_rank = "students_pre_rank_of_school"
        else:
            keep = ("school_true_score_of_student", "school_pre_observed_score_of_student")
            stale_rank = "schools_pre_rank_of_student"
        Interview.objects.filter(simulation=simulation).update(**{stale_rank: None})
        _update_columns(Interview, pairs.ids, {name: columns[name] for name in keep})


def compute_students_pre_rankings(simulation: Simulation) -> None:
    """Rank programs for each applicant by the stored pre-interview ratings (1 = highest; rows without one: none)."""
    _rank_from_stored(simulation, score="student_pre_observed_score_of_school", rank="students_pre_rank_of_school")


def compute_schools_pre_rankings(simulation: Simulation) -> None:
    """Rank applicants for each program by the stored pre-interview ratings (1 = highest; rows without one: none)."""
    _rank_from_stored(simulation, score="school_pre_observed_score_of_student", rank="schools_pre_rank_of_student")


def _rank_from_stored(simulation: Simulation, *, score: str, rank: str) -> None:
    with transaction.atomic():
        simulation.lock()
        rows = list(
            Interview.objects.filter(simulation=simulation)
            .order_by("id")
            .values_list("id", "student_id", "school_id", score)
        )
        if not rows:
            return
        ids = np.array([r[0] for r in rows], dtype=np.int64)
        student_ids = np.array([r[1] for r in rows], dtype=np.int64)
        school_ids = np.array([r[2] for r in rows], dtype=np.int64)
        scores = np.array([np.nan if r[3] is None else r[3] for r in rows], dtype=float)
        if rank.startswith("students"):
            ranks = _strict_ranks(student_ids, scores, school_ids)
        else:
            ranks = _strict_ranks(school_ids, scores, student_ids)
        _update_columns(Interview, ids, {rank: ranks})


# --- Post-interview stage ---------------------------------------------------------------------------------------


def compute_post_interview_scores_and_rankings(simulation: Simulation, rng: np.random.Generator | None = None) -> int:
    """Rate and rank the pairs that interviewed, using the post-interview rating errors.

    Only interview rows with status "interviewed" take part. No stage sets that status yet (the invitation and
    interview stages come with Phase 3 of the plan), so this raises a PopulationError explaining that.
    """
    rng = rng or np.random.default_rng()
    with transaction.atomic():
        simulation.lock()
        config = latest_config(simulation)
        pairs = _load_pairs(simulation, status="interviewed")
        if not len(pairs.ids):
            raise PopulationError(
                "No interviews have taken place yet: the invitation and interview stages are not implemented, so "
                "there is nothing to rate after interviews."
            )
        columns = _rate_pairs(simulation, pairs, config, rng, post=True)
        _update_columns(Interview, pairs.ids, columns)
        simulation.set_stage("post_interview")
        return len(pairs.ids)


def students_rank():
    """Each student, using the post-interview rating, chooses which schools to rank and ranks them by rating.

    1 is the highest rank
    """
    pass


def schools_rank():
    """Each school, using the post-interview rating, chooses which students to rank and ranks them by rating."""
    pass


def match():
    """Run the NRMP match algorithm."""
    pass
