"""Population CSV upload and download (plan step 0.6: UX-4, ENG-6; and SIM-5/SIM-6 from step 1.7)."""

from pathlib import Path

import numpy as np
import pytest
from django.conf import settings as django_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from nrmps import simulation_engine as se
from nrmps.population_csv import DISPLAY_NAMES, MAX_UPLOAD_ROWS, PopulationCSVError, parse_population_csv

pytestmark = pytest.mark.django_db


def _download(client, sim, kind: str) -> bytes:
    response = client.get(reverse(f"nrmps:simulation_download_{kind}", kwargs={"pk": sim.pk}))
    assert response.status_code == 200
    return b"".join(response.streaming_content)


def _upload(client, sim, kind: str, content: bytes, filename: str = "upload.csv"):
    return client.post(
        reverse(f"nrmps:simulation_upload_{kind}", kwargs={"pk": sim.pk}),
        {"file": SimpleUploadedFile(filename, content, "text/csv")},
        headers={"hx-request": "true"},
    )


def _population(sim, kind: str) -> list[tuple]:
    queryset = sim.students if kind == "students" else sim.schools
    fields = ["name", "score", "score_meta", "meta_preference"] + (["capacity"] if kind == "schools" else [])
    return list(queryset.order_by("id").values_list(*fields))


@pytest.mark.parametrize("kind", ["students", "schools"])
def test_download_then_upload_is_lossless(auth_client, populated_simulation, kind):
    """A downloaded population uploads back unchanged, preferences included (SIM-5)."""
    before = _population(populated_simulation, kind)
    response = _upload(auth_client, populated_simulation, kind, _download(auth_client, populated_simulation, kind))
    assert response.status_code == 200
    assert b"not loaded" not in response.content
    assert _population(populated_simulation, kind) == before


def test_round_tripped_populations_still_rate_and_rank(auth_client, populated_simulation):
    """After a round trip the pre-interview stage works: preferences were not dropped (every score 0 before)."""
    for kind in ("students", "schools"):
        _upload(auth_client, populated_simulation, kind, _download(auth_client, populated_simulation, kind))
    se.initialize_interview(populated_simulation)
    se.compute_pre_interview_scores_and_rankings(populated_simulation, rng=np.random.default_rng(0))
    scores = populated_simulation.interviews.values_list("student_true_score_of_school", flat=True)
    assert len(set(scores)) > 1


def test_bad_rows_are_reported_with_line_numbers_and_change_nothing(auth_client, populated_simulation):
    """Invalid values are listed by line and column; the existing population survives (UX-4)."""
    before = _population(populated_simulation, "students")
    content = b"name,score\nAlice,abc\n,0.5\nBob,1.7\n"
    response = _upload(auth_client, populated_simulation, "students", content)
    body = response.content.decode()
    assert response.status_code == 200
    assert "The file was not loaded (3 problems); nothing was changed." in body
    assert "line 2, column score: &#x27;abc&#x27; is not a number." in body
    assert "line 3, column name: is empty." in body
    assert "line 4, column score: 1.7 is not between 0 and 1." in body
    assert _population(populated_simulation, "students") == before


def test_binary_file_is_rejected_and_changes_nothing(auth_client, populated_simulation):
    """Random bytes used to delete the population and then fail with a 500 (ENG-6)."""
    before = _population(populated_simulation, "students")
    response = _upload(auth_client, populated_simulation, "students", bytes(range(256)) * 8)
    assert response.status_code == 200
    assert b"not UTF-8 text" in response.content
    assert _population(populated_simulation, "students") == before


def test_upload_writes_no_files(auth_client, populated_simulation):
    """Uploads are parsed in memory; nothing is written to a shared data/ directory (ENG-6, CRIT-4)."""
    data_dir = Path(django_settings.BASE_DIR) / "data"
    existed = data_dir.exists()
    _upload(auth_client, populated_simulation, "students", b"name,score\nAlice,0.5\n")
    assert data_dir.exists() == existed


def test_successful_upload_replaces_population_and_resets_the_stage(auth_client, populated_simulation):
    se.initialize_interview(populated_simulation)
    response = _upload(auth_client, populated_simulation, "students", b"name,score\nAlice,0.5\nBob,0.25\n")
    assert response.status_code == 200
    assert _population(populated_simulation, "students") == [("Alice", 0.5, {}, {}), ("Bob", 0.25, {}, {})]
    populated_simulation.refresh_from_db()
    assert populated_simulation.status == "populations"
    assert not populated_simulation.interviews.exists()


def test_upload_above_the_size_limit_is_rejected(auth_client, populated_simulation, settings):
    settings.NRMP_MAX_PAIRS = 8  # 4 programs x 3 applicants = 12 pairs
    before = _population(populated_simulation, "students")
    response = _upload(auth_client, populated_simulation, "students", b"name,score\nA,0.1\nB,0.2\nC,0.3\n")
    assert b"above the current limit of 8 pairs" in response.content
    assert _population(populated_simulation, "students") == before


def _parse(content: bytes, kind: str = "students"):
    return parse_population_csv(SimpleUploadedFile("f.csv", content), kind)


def test_excel_byte_order_mark_is_accepted():
    assert _parse(b"\xef\xbb\xbfname,score\nAlice,0.5\n") == [
        {"name": "Alice", "score": 0.5, "score_meta": {}, "meta_preference": {}}
    ]


def test_schools_parse_capacity_and_json_columns():
    rows = _parse(
        b'name,capacity,score,score_meta,meta_preference\nMercy,12,0.4,"{""research"": 0.5}","{""honors"": 1}"\n',
        "schools",
    )
    assert rows == [
        {
            "name": "Mercy",
            "capacity": 12,
            "score": 0.4,
            "score_meta": {"research": 0.5},
            "meta_preference": {"honors": 1.0},
        }
    ]


@pytest.mark.parametrize(
    ("content", "kind", "message"),
    [
        (b"", "students", "The file is empty."),
        (b"name\nAlice\n", "students", "missing: score"),
        (b"name,score,extra\nAlice,0.5,x\n", "students", "Unknown column(s): extra"),
        (b"name,score\n", "students", "no applicant rows"),
        (b"name,score\nAlice,0.5,0.7\n", "students", "more values than the header has columns"),
        (b"name,score,score_meta\nAlice,0.5,{bad json}\n", "students", "is not valid JSON"),
        (b'name,score,score_meta\nAlice,0.5,"{""research"": 2}"\n', "students", "must be between 0 and 1"),
        (b'name,score,score_meta\nAlice,0.5,"{""Research Score"": 0.5}"\n', "students", "not a valid attribute name"),
        (b"name,capacity,score\nMercy,2.5,0.4\n", "schools", "not a whole number of 0 or more"),
        (b"name,capacity,score\nMercy,-1,0.4\n", "schools", "not a whole number of 0 or more"),
        (b"name,score\nAlice,nan\n", "students", "not a finite number"),
    ],
)
def test_invalid_files_are_rejected(content, kind, message):
    with pytest.raises(PopulationCSVError) as info:
        _parse(content, kind)
    assert message in " ".join([str(info.value), *info.value.details])


def test_too_many_rows_is_rejected():
    content = b"name,score\n" + b"x,0.5\n" * (MAX_UPLOAD_ROWS + 1)
    with pytest.raises(PopulationCSVError) as info:
        _parse(content)
    assert "more than 50,000 rows" in info.value.details[0]


def test_file_over_5_mb_is_rejected():
    content = b"name,score\n" + b"x" * (5 * 1024 * 1024)
    with pytest.raises(PopulationCSVError) as info:
        _parse(content)
    assert "larger than 5 MB" in info.value.details[0]


def test_only_the_first_problems_are_listed():
    content = b"name,score\n" + b"x,abc\n" * 30
    with pytest.raises(PopulationCSVError) as info:
        _parse(content)
    assert info.value.total_errors == 30
    assert len(info.value.details) == 20
    assert "30 problems" in str(info.value)


@pytest.mark.parametrize("kind", ["students", "schools"])
def test_sample_files_are_valid(kind):
    """The sample files linked beside the upload inputs parse without problems (HELP-15)."""
    path = Path(django_settings.BASE_DIR) / "static" / "samples" / f"{DISPLAY_NAMES[kind]}_sample.csv"
    rows = parse_population_csv(SimpleUploadedFile(path.name, path.read_bytes()), kind)
    assert rows


def test_sample_files_work_together(auth_client, simulation):
    """Uploading both samples gives a population the pre-interview stage can rate."""
    for kind in ("students", "schools"):
        path = Path(django_settings.BASE_DIR) / "static" / "samples" / f"{DISPLAY_NAMES[kind]}_sample.csv"
        response = _upload(auth_client, simulation, kind, path.read_bytes())
        assert b"not loaded" not in response.content
    se.initialize_interview(simulation)
    assert se.compute_pre_interview_scores_and_rankings(simulation) == 12 * 3


def test_upload_card_links_the_sample_files(auth_client, simulation):
    body = auth_client.get(reverse("nrmps:simulation_manage", kwargs={"pk": simulation.pk})).content.decode()
    assert "samples/applicants_sample.csv" in body
    assert "samples/programs_sample.csv" in body
