"""Population CSV files for model 2.0: parsing, validation, uploads, downloads and round trips (plan step 2.3)."""

import io
from pathlib import Path

import numpy as np
import pytest
from django.conf import settings as django_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from nrmps.engine.persistence import population_digest, population_from_npz
from nrmps.engine.population import PopulationError
from nrmps.models import PopulationUpload, RunArtifact
from nrmps.params import SimulationParams, load_params
from nrmps.population_csv import (
    MAX_UPLOAD_ROWS,
    PopulationCSVError,
    UploadedSide,
    applicant_side,
    columns,
    parse_population_csv,
    population_csv_lines,
    program_side,
    uploaded_csv_lines,
)
from nrmps.runs import run_now

from .conftest import SMALL_PARAMS

PARAMS = SimulationParams()
SAMPLES = Path(django_settings.BASE_DIR) / "static" / "samples"


def _parse(content: bytes, side: str = "applicants", params: SimulationParams = PARAMS) -> UploadedSide:
    return parse_population_csv(SimpleUploadedFile("f.csv", content), side, params)


def _errors(content: bytes, side: str = "applicants") -> str:
    with pytest.raises(PopulationCSVError) as info:
        _parse(content, side)
    return " ".join([str(info.value), *info.value.details])


APPLICANTS = b"name,group,strength,board_scores,research,honors\nAlice,us_md,0.5,0.1,0.2,0.3\nBob,,-1,0,0,0\n"


# --- Parsing ----------------------------------------------------------------------------------------------------------


def test_columns_follow_the_parameters():
    assert columns(PARAMS, "applicants") == [
        "name",
        "group",
        "strength",
        "board_scores",
        "research",
        "honors",
        "weight:reputation",
        "weight:program_size",
        "weight:location",
    ]
    # program_size is computed from capacity, so it is not a column.
    assert columns(PARAMS, "programs", weights=False) == [
        "name",
        "tier",
        "quality",
        "capacity",
        "reputation",
        "location",
    ]


def test_applicants_without_weights_and_groups():
    upload = _parse(APPLICANTS)
    assert upload.names == ("Alice", "Bob")
    assert upload.labels == ("us_md", "uploaded")
    assert upload.latent.tolist() == [0.5, -1.0]
    assert upload.weights is None


def test_weights_are_rescaled_and_columns_may_come_in_any_order():
    content = (
        b"weight:location,honors,name,strength,research,board_scores,weight:reputation,weight:program_size\n"
        b"2,0.3,Alice,0.5,0.2,0.1,1,1\n"
    )
    upload = _parse(content)
    assert upload.weights is not None
    assert upload.weight_keys == ("reputation", "program_size", "location")
    assert upload.weights[0].tolist() == pytest.approx([0.25, 0.25, 0.5])
    side = applicant_side(upload, PARAMS, seed=1)
    assert side.attributes[0].tolist() == [0.1, 0.2, 0.3]


def test_excel_byte_order_mark_is_accepted():
    assert _parse(b"\xef\xbb\xbf" + APPLICANTS).names == ("Alice", "Bob")


def test_programs_need_capacity_and_get_program_size_from_it():
    content = b"name,tier,quality,capacity,reputation,location\nMercy,,0.4,12,0.5,0\nHope,,0.1,3,0,0\n"
    upload = _parse(content, "programs")
    assert upload.capacity is not None
    assert upload.capacity.tolist() == [12, 3]
    side = program_side(upload, PARAMS, seed=1)
    assert side.keys == ("reputation", "program_size", "location")
    size = side.attributes[:, 1]
    assert size[0] > size[1]  # the larger program has the larger program_size
    assert side.weights.shape == (2, 3)  # drawn by the model


@pytest.mark.parametrize(
    ("content", "side", "message"),
    [
        (b"", "applicants", "The file is empty."),
        (b"name,strength\nAlice,0.5\n", "applicants", "Missing column(s): board_scores, research, honors"),
        (APPLICANTS.replace(b"honors\n", b"honors,extra\n"), "applicants", "Unknown column(s): extra"),
        (b"name,group,strength,board_scores,research,honors\n", "applicants", "no applicant rows"),
        (b"name,strength,board_scores,research,honors\nA,1,1,1,1\n", "applicants", ""),  # valid
        (b"name,strength,board_scores,research,honors\nA,1,1,1,1,1,9\n", "applicants", "more values than the header"),
        (b"name,strength,board_scores,research,honors\nA,x,1,1,1\n", "applicants", "'x' is not a number"),
        (b"name,strength,board_scores,research,honors\nA,nan,1,1,1\n", "applicants", "not a finite number"),
        (b"name,strength,board_scores,research,honors\nA,,1,1,1\n", "applicants", "column strength: is empty"),
        (b"name,strength,board_scores,research,honors\nA,1,1,1,1\nA,1,1,1,1\n", "applicants", "also on line 2"),
        (b"name,group,strength,board_scores,research,honors\nA,US MD,1,1,1,1\n", "applicants", "not a valid name"),
        (
            b"name,strength,board_scores,research,honors,weight:reputation\nA,1,1,1,1,1\n",
            "applicants",
            "all weight columns or none",
        ),
        (
            b"name,strength,board_scores,research,honors,weight:reputation,weight:program_size,weight:location\n"
            b"A,1,1,1,1,-1,1,1\n",
            "applicants",
            "must not be negative",
        ),
        (
            b"name,strength,board_scores,research,honors,weight:reputation,weight:program_size,weight:location\n"
            b"A,1,1,1,1,0,0,0\n",
            "applicants",
            "add up to 0",
        ),
        (b"name,quality,capacity,reputation,location\nM,1,2.5,0,0\n", "programs", "not a whole number of 1 or more"),
        (b"name,quality,capacity,reputation,location\nM,1,0,0,0\n", "programs", "not a whole number of 1 or more"),
        (
            b"name,quality,capacity,reputation,location,program_size\nM,1,2,0,0,1\n",
            "programs",
            "computed from capacity",
        ),
        (b"name,name,strength,board_scores,research,honors\n", "applicants", "appear more than once"),
    ],
)
def test_file_problems_are_reported(content, side, message):
    if not message:
        _parse(content, side)
        return
    assert message in _errors(content, side)


def test_too_many_rows_is_rejected():
    rows = "".join(f"a{i},0,0,0,0\n" for i in range(MAX_UPLOAD_ROWS + 1))
    content = ("name,strength,board_scores,research,honors\n" + rows).encode()
    assert "more than 50,000 rows" in _errors(content)


def test_file_over_5_mb_is_rejected():
    assert "larger than 5 MB" in _errors(b"name,strength\n" + b"x" * (5 * 1024 * 1024))


def test_non_utf8_file_is_rejected():
    assert "not UTF-8 text" in _errors(b"name,strength\n\xff\xfe\x00")


def test_only_the_first_problems_are_listed():
    content = b"name,strength,board_scores,research,honors\n" + b"".join(b"x%d,abc,1,1,1\n" % i for i in range(30))
    with pytest.raises(PopulationCSVError) as info:
        _parse(content)
    assert info.value.total_errors == 30
    assert len(info.value.details) == 20
    assert "30 problems" in str(info.value)


def test_mismatched_attributes_are_reported_when_the_run_starts():
    upload = _parse(APPLICANTS)
    other = SimulationParams.model_validate(
        {"applicants": {"attributes": [{"key": "step_1", "program_weight_prior": 1}]}}
    )
    with pytest.raises(PopulationError, match="parameters list step_1"):
        applicant_side(upload, other, seed=1)


def test_upload_npz_round_trip():
    upload = _parse(b"\xef\xbb\xbf" + APPLICANTS)
    again = UploadedSide.from_npz(upload.to_npz())
    assert again.names == upload.names
    assert np.array_equal(again.attributes, upload.attributes)
    assert "".join(uploaded_csv_lines(again)).startswith("name,group,strength,board_scores")


# --- Sample files -----------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("side", ["applicants", "programs"])
def test_sample_files_are_valid(side):
    path = SAMPLES / f"{side}_sample.csv"
    upload = parse_population_csv(SimpleUploadedFile(path.name, path.read_bytes()), side, PARAMS)
    assert upload.rows >= 3
    assert upload.weights is not None


# --- Uploads through the page and runs -------------------------------------------------------------------------------


def _upload(client, sim, side: str, content: bytes, filename: str = "upload.csv"):
    return client.post(
        reverse("nrmps:population_upload", kwargs={"pk": sim.pk, "side": side}),
        {"file": SimpleUploadedFile(filename, content, "text/csv")},
        headers={"hx-request": "true"},
    )


def _download(client, run, name: str) -> bytes:
    url = reverse("nrmps:run_download", kwargs={"pk": run.simulation_id, "number": run.number, "name": name})
    response = client.get(url)
    assert response.status_code == 200
    return b"".join(response.streaming_content)


@pytest.mark.django_db
def test_download_then_upload_gives_the_same_population(auth_client, finished_run, simulation, user):
    """A run's downloads upload back unchanged: the next run has exactly the same population (SIM-5)."""
    for side in ("applicants", "programs"):
        response = _upload(auth_client, simulation, side, _download(auth_client, finished_run, f"{side}.csv"))
        assert b"not loaded" not in response.content, response.content
    run = run_now(simulation, user)
    assert run.population_source == {"applicants": "upload.csv", "programs": "upload.csv"}
    original = population_from_npz(finished_run.artifact(RunArtifact.Kind.POPULATION))
    uploaded = population_from_npz(run.artifact(RunArtifact.Kind.POPULATION))
    for attribute in ("strength", "attributes", "weights", "group"):
        assert np.array_equal(getattr(original.applicants, attribute), getattr(uploaded.applicants, attribute))
    for attribute in ("quality", "attributes", "weights", "capacity", "tier"):
        assert np.array_equal(getattr(original.programs, attribute), getattr(uploaded.programs, attribute))
    assert run.metrics["applicants"]["consensus"] == finished_run.metrics["applicants"]["consensus"]
    # Downloads of the uploaded population are identical to the originals too.
    for side in ("applicants", "programs"):
        assert _download(auth_client, run, f"{side}.csv") == _download(auth_client, finished_run, f"{side}.csv")
    assert population_digest(uploaded) != population_digest(original)  # names differ: generated vs from the file


@pytest.mark.django_db
def test_bad_upload_is_listed_and_changes_nothing(auth_client, simulation):
    response = _upload(
        auth_client, simulation, "applicants", b"name,strength,board_scores,research,honors\nA,x,1,1,1\n"
    )
    body = response.content.decode()
    assert "The file was not loaded (1 problem); nothing was changed." in body
    assert "line 2, column strength" in body
    assert not PopulationUpload.objects.exists()


@pytest.mark.django_db
def test_upload_above_the_size_limit_is_rejected(auth_client, simulation, settings):
    settings.NRMP_MAX_PAIRS = 10
    response = _upload(auth_client, simulation, "applicants", APPLICANTS)
    assert b"above the current limit of 10 pairs" in response.content
    assert not PopulationUpload.objects.exists()


@pytest.mark.django_db
def test_upload_writes_no_files(auth_client, simulation, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    _upload(auth_client, simulation, "applicants", APPLICANTS)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.django_db
def test_upload_can_be_replaced_and_removed(auth_client, simulation, user):
    _upload(auth_client, simulation, "applicants", APPLICANTS, "first.csv")
    _upload(auth_client, simulation, "applicants", (SAMPLES / "applicants_sample.csv").read_bytes(), "second.csv")
    upload = PopulationUpload.objects.get()
    assert upload.filename == "second.csv"
    assert upload.rows == 12
    run = run_now(simulation, user)
    assert run.n_applicants == 12  # the market size follows the upload
    assert run.n_positions == 10  # 12 applicants at 1.2 applicants per position
    response = auth_client.post(
        reverse("nrmps:population_upload_remove", kwargs={"pk": simulation.pk, "side": "applicants"}),
        headers={"hx-request": "true"},
    )
    assert b"Generated from the parameters." in response.content
    assert not PopulationUpload.objects.exists()


@pytest.mark.django_db
def test_uploaded_applicants_with_changed_attributes_fail_clearly(auth_client, simulation, user):
    _upload(auth_client, simulation, "applicants", APPLICANTS)
    data = load_params(SMALL_PARAMS).to_json_data()
    data["applicants"]["attributes"] = [{"key": "step_1", "corr_with_strength": 0.5, "program_weight_prior": 1.0}]
    simulation.params = data
    simulation.save()
    response = auth_client.post(
        reverse("nrmps:run_start", kwargs={"pk": simulation.pk}), headers={"hx-request": "true"}
    )
    assert "The uploaded applicants have the attributes board_scores, research, honors" in response.content.decode()


@pytest.mark.django_db
def test_upload_card_links_the_sample_files_and_lists_the_columns(auth_client, simulation):
    body = auth_client.get(reverse("nrmps:simulation_manage", kwargs={"pk": simulation.pk})).content.decode()
    assert "samples/applicants_sample.csv" in body
    assert "samples/programs_sample.csv" in body
    assert "name,group,strength,board_scores,research,honors" in body


def test_generated_side_writes_the_upload_format():
    from nrmps.engine.population import generate_population

    population = generate_population(
        SimulationParams.model_validate({"market": {"n_applicants": 10, "n_programs": 2}}), 1
    )
    text = "".join(population_csv_lines(population.programs))
    header = next(iter(io.StringIO(text))).strip()
    assert header == "name,tier,quality,capacity,reputation,location,weight:board_scores,weight:research,weight:honors"


@pytest.mark.django_db
def test_too_few_uploaded_applicants_for_the_programs_is_explained(simulation, user):
    from nrmps.exceptions import SimulationError

    data = APPLICANTS
    upload = _parse(data)
    PopulationUpload.objects.create(
        simulation=simulation, side="applicants", filename="two.csv", rows=2, data=upload.to_npz(), digest="x"
    )
    with pytest.raises(SimulationError, match="8 programs need at least 8 positions, but the applicants give only 2"):
        run_now(simulation, user)
