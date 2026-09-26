"""Property-based tests (plan step 1.1): strict ranking and the population CSV round trip."""

import numpy as np
from django.core.files.uploadedfile import SimpleUploadedFile
from hypothesis import given, settings
from hypothesis import strategies as st

from nrmps.population_csv import csv_lines, parse_population_csv
from nrmps.simulation_engine import _strict_ranks


@st.composite
def ranking_problems(draw):
    """Rows with a group id, a score (NaN = unrated, ties likely) and a unique tie-break id."""
    n = draw(st.integers(1, 60))
    groups = draw(st.lists(st.integers(0, 4), min_size=n, max_size=n))
    scores = draw(
        st.lists(st.sampled_from([0.0, 0.25, 0.5, 1.0, float("nan")]) | st.floats(-2, 2), min_size=n, max_size=n)
    )
    tie_break = draw(st.permutations(range(n)))
    return np.array(groups), np.array(scores, dtype=float), np.array(tie_break)


@settings(max_examples=300, deadline=None)
@given(ranking_problems())
def test_ranks_are_consecutive_and_ordered_within_each_group(problem):
    groups, scores, tie_break = problem
    ranks = _strict_ranks(groups, scores, tie_break)
    assert np.array_equal(np.isnan(ranks), np.isnan(scores))  # unrated rows get no rank
    for group in np.unique(groups):
        rated = np.flatnonzero((groups == group) & ~np.isnan(scores))
        assert sorted(ranks[rated]) == list(range(1, len(rated) + 1))  # 1..k, no gaps or duplicates
        in_rank_order = rated[np.argsort(ranks[rated])]
        keys = [(-scores[i], tie_break[i]) for i in in_rank_order]
        assert keys == sorted(keys)  # higher score first; ties by ascending tie-break


names = st.text(
    alphabet=st.characters(blacklist_categories=("Cc", "Cs"), blacklist_characters="\u2028\u2029\x85"),
    min_size=1,
    max_size=40,
).filter(lambda s: s == s.strip() and s.strip())
attribute = st.from_regex(r"[a-z0-9_]{1,12}", fullmatch=True)
unit = st.floats(0, 1, allow_nan=False)
weights = st.floats(0, 5, allow_nan=False)


@st.composite
def populations(draw):
    """A small population of programs in the upload format (student rows are the same minus capacity)."""
    return [
        {
            "name": draw(names),
            "capacity": draw(st.integers(0, 50)),
            "score": draw(unit),
            "score_meta": draw(st.dictionaries(attribute, unit, max_size=4)),
            "meta_preference": draw(st.dictionaries(attribute, weights, max_size=4)),
        }
        for _ in range(draw(st.integers(1, 8)))
    ]


@settings(max_examples=200, deadline=None)
@given(populations())
def test_csv_download_uploads_back_unchanged(rows):
    """Any valid population survives CSV export and import exactly (names with commas, quotes, unicode...)."""
    records = [(r["name"], r["capacity"], r["score"], r["score_meta"], r["meta_preference"]) for r in rows]
    content = "".join(csv_lines("schools", records)).encode()
    parsed = parse_population_csv(SimpleUploadedFile("p.csv", content), "schools")
    assert parsed == rows
