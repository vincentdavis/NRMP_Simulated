"""The patched legacy engine (plan steps 0.3 and 0.4).

Covers additive noise with sigma = 0 exact (SIM-1, OPT-2), stored true utilities (SIM-9, STG-2), strict ranks with a
deterministic tie-break and no stale ranks (SIM-10, STG-12), clear errors instead of 500s and partial writes (SIM-4,
STG-11), the post-interview guard (L-1) and stage resets after population changes (L-2).
"""

import numpy as np
import pytest
from scipy.stats import spearmanr

from nrmps import simulation_engine as se
from nrmps.exceptions import PopulationError, SizeLimitError
from nrmps.models import Interview

pytestmark = pytest.mark.django_db


def _set_errors(sim, pre: float, post: float = 0.02) -> None:
    """Set both sides' pre- and post-interview rating errors on the simulation's configuration."""
    sim.configs.update(
        applicant_pre_interview_rating_error=pre,
        school_pre_interview_rating_error=pre,
        applicant_post_interview_rating_error=post,
        school_post_interview_rating_error=post,
    )


def _rows(sim, *fields):
    """Return the simulation's interview rows as a list of tuples, ordered by id."""
    return list(Interview.objects.filter(simulation=sim).order_by("id").values_list(*fields))


@pytest.fixture
def initialized(populated_simulation):
    """Return a simulation with populations (20 applicants x 4 programs) and interview rows."""
    se.initialize_interview(populated_simulation)
    return populated_simulation


def test_initialize_creates_the_cross_product_and_sets_the_stage(initialized):
    assert Interview.objects.filter(simulation=initialized).count() == 80
    initialized.refresh_from_db()
    assert initialized.status == "initialized"


def test_true_utility_is_the_weighted_sum_of_attributes(initialized):
    se.compute_pre_interview_scores_and_rankings(initialized, rng=np.random.default_rng(0))
    inter = Interview.objects.filter(simulation=initialized).select_related("student", "school").first()
    student, school = inter.student, inter.school
    expected_u = sum(w * school.score_meta[k] for k, w in student.meta_preference.items())
    expected_v = sum(w * student.score_meta[k] for k, w in school.meta_preference.items())
    assert inter.student_true_score_of_school == pytest.approx(expected_u)
    assert inter.school_true_score_of_student == pytest.approx(expected_v)


def test_zero_rating_error_means_perfect_information(initialized):
    """Sigma = 0 gives observed == true, so pre-interview ranks are the true ranks (0 no longer means x1)."""
    _set_errors(initialized, pre=0.0)
    se.compute_pre_interview_scores_and_rankings(initialized)
    for true_u, obs_u, true_v, obs_v in _rows(
        initialized,
        "student_true_score_of_school",
        "student_pre_observed_score_of_school",
        "school_true_score_of_student",
        "school_pre_observed_score_of_student",
    ):
        assert obs_u == true_u
        assert obs_v == true_v


def test_rating_error_adds_noise_instead_of_scaling(initialized):
    """Observed = true + N(0, sigma): not a rescaled copy, so observed rankings can differ from true ones."""
    _set_errors(initialized, pre=0.1)
    se.compute_pre_interview_scores_and_rankings(initialized, rng=np.random.default_rng(1))
    rows = _rows(initialized, "student_id", "student_true_score_of_school", "student_pre_observed_score_of_school")
    true = np.array([r[1] for r in rows])
    observed = np.array([r[2] for r in rows])
    noise = observed - true
    assert abs(noise.mean()) < 0.03
    assert 0.07 < noise.std() < 0.13
    assert observed.max() > 0.2  # the old multiplier shrank every score to about 0-0.1
    per_student = [
        spearmanr(
            true[[i for i, r in enumerate(rows) if r[0] == sid]],
            observed[[i for i, r in enumerate(rows) if r[0] == sid]],
        )[0]
        for sid in {r[0] for r in rows}
    ]
    assert min(per_student) < 1


def test_ranks_are_strict_and_consecutive(initialized):
    se.compute_pre_interview_scores_and_rankings(initialized, rng=np.random.default_rng(2))
    rows = _rows(initialized, "student_id", "school_id", "students_pre_rank_of_school", "schools_pre_rank_of_student")
    by_student, by_school = {}, {}
    for student_id, school_id, student_rank, school_rank in rows:
        by_student.setdefault(student_id, []).append(student_rank)
        by_school.setdefault(school_id, []).append(school_rank)
    assert all(sorted(ranks) == [1, 2, 3, 4] for ranks in by_student.values())
    assert all(sorted(ranks) == list(range(1, 21)) for ranks in by_school.values())


def test_rank_one_has_the_highest_observed_score(initialized):
    se.compute_pre_interview_scores_and_rankings(initialized, rng=np.random.default_rng(3))
    rows = _rows(initialized, "student_id", "student_pre_observed_score_of_school", "students_pre_rank_of_school")
    for sid in {r[0] for r in rows}:
        mine = sorted((r for r in rows if r[0] == sid), key=lambda r: r[2])
        observed_in_rank_order = [r[1] for r in mine]
        assert observed_in_rank_order == sorted(observed_in_rank_order, reverse=True)


def test_ties_are_broken_by_id(initialized):
    """With identical attributes and no noise every utility ties; ranks then follow ascending ids."""
    initialized.schools.update(score_meta={"program_size": 0.5, "reputation": 0.5, "location": 0.5})
    initialized.students.update(score_meta={"board_scores": 0.5, "research": 0.5, "honors": 0.5})
    _set_errors(initialized, pre=0.0)
    se.compute_pre_interview_scores_and_rankings(initialized)
    rows = _rows(initialized, "student_id", "school_id", "students_pre_rank_of_school", "schools_pre_rank_of_student")
    school_order = sorted({r[1] for r in rows})
    student_order = sorted({r[0] for r in rows})
    for student_id, school_id, student_rank, school_rank in rows:
        assert student_rank == school_order.index(school_id) + 1
        assert school_rank == student_order.index(student_id) + 1


def test_separate_steps_match_the_combined_step_and_clear_stale_ranks(initialized):
    """The single-side steps write the same kind of data, and re-ranking clears ranks of unrated rows."""
    _set_errors(initialized, pre=0.0)
    se.students_rate_schools_pre_interview(initialized)
    se.schools_rate_students_pre_interview(initialized)
    se.compute_students_pre_rankings(initialized)
    se.compute_schools_pre_rankings(initialized)
    separate = _rows(initialized, "students_pre_rank_of_school", "schools_pre_rank_of_student")
    se.compute_pre_interview_scores_and_rankings(initialized)
    assert _rows(initialized, "students_pre_rank_of_school", "schools_pre_rank_of_student") == separate

    first = Interview.objects.filter(simulation=initialized).order_by("id").first()
    Interview.objects.filter(pk=first.pk).update(student_pre_observed_score_of_school=None)
    se.compute_students_pre_rankings(initialized)
    first.refresh_from_db()
    assert first.students_pre_rank_of_school is None


def test_attribute_mismatch_is_reported_and_nothing_is_written(initialized):
    """A program without a score for an attribute applicants weigh gives a clear error, and no partial writes."""
    school = initialized.schools.order_by("id").first()
    school.score_meta.pop("reputation")
    school.save()
    with pytest.raises(PopulationError, match="reputation"):
        se.compute_pre_interview_scores_and_rankings(initialized)
    assert not Interview.objects.filter(
        simulation=initialized, student_pre_observed_score_of_school__isnull=False
    ).exists()


def test_population_without_preferences_is_reported(initialized):
    """Applicants with no preference weights (as after a CSV upload) are reported instead of scoring 0 everywhere."""
    initialized.students.update(meta_preference={})
    with pytest.raises(PopulationError, match="no preference weights"):
        se.compute_pre_interview_scores_and_rankings(initialized)


def test_error_messages_use_ids_not_names(initialized):
    """Engine errors can reach logs, so they identify participants by id, never by name (CRIT-4)."""
    initialized.schools.update(name="Real Hospital Name")
    school = initialized.schools.order_by("id").first()
    school.score_meta.pop("reputation")
    school.save()
    with pytest.raises(PopulationError) as info:
        se.compute_pre_interview_scores_and_rankings(initialized)
    assert "Real Hospital Name" not in str(info.value)
    assert f"id {school.pk}" in str(info.value)


def test_pre_interview_needs_interview_rows(populated_simulation):
    with pytest.raises(PopulationError, match="Initialize the interviews first"):
        se.compute_pre_interview_scores_and_rankings(populated_simulation)


def test_post_interview_without_interviews_is_reported_and_keeps_the_stage(initialized):
    """No stage marks pairs as interviewed yet, so the post-interview step says so instead of claiming success (L-1)."""
    se.compute_pre_interview_scores_and_rankings(initialized)
    with pytest.raises(PopulationError, match="No interviews have taken place"):
        se.compute_post_interview_scores_and_rankings(initialized)
    initialized.refresh_from_db()
    assert initialized.status == "pre_interview"


def test_post_interview_rates_only_interviewed_pairs(initialized):
    _set_errors(initialized, pre=0.1, post=0.0)
    school = initialized.schools.order_by("id").first()
    Interview.objects.filter(simulation=initialized, school=school).update(status="interviewed")
    se.compute_post_interview_scores_and_rankings(initialized)
    rows = _rows(initialized, "school_id", "student_post_observed_score_of_school", "schools_post_rank_of_student")
    interviewed = [r for r in rows if r[0] == school.pk]
    others = [r for r in rows if r[0] != school.pk]
    assert all(r[1] is not None for r in interviewed)
    assert sorted(r[2] for r in interviewed) == list(range(1, 21))
    assert all(r[1] is None and r[2] is None for r in others)


def test_changing_a_population_resets_the_stage(initialized):
    """Recreating applicants deletes the interview rows, so the stage goes back to 'populations' (L-2)."""
    se.compute_pre_interview_scores_and_rankings(initialized)
    initialized.refresh_from_db()
    assert initialized.status == "pre_interview"
    initialized.create_students()
    initialized.refresh_from_db()
    assert initialized.status == "populations"
    assert not Interview.objects.filter(simulation=initialized).exists()
    initialized.delete_schools()
    initialized.refresh_from_db()
    assert initialized.status == "setup"


def test_rerunning_initialize_resets_later_stages(initialized):
    se.compute_pre_interview_scores_and_rankings(initialized)
    se.initialize_interview(initialized)
    initialized.refresh_from_db()
    assert initialized.status == "initialized"


def test_initialize_respects_the_size_limit(initialized, settings):
    settings.NRMP_MAX_PAIRS = 79
    with pytest.raises(SizeLimitError, match="20 applicants x 4 programs = 80 pairs"):
        se.initialize_interview(initialized)
    assert Interview.objects.filter(simulation=initialized).count() == 80  # nothing was deleted
