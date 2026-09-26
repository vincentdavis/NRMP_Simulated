"""Populations and per-agent results as npz bytes, and the population digest (model_spec.md §12.9).

The npz files are written with fixed zip timestamps, so the same arrays always give the same bytes. Arrays are stored
little-endian (float64, int16, int32, int64); names and keys go in a JSON member. Nothing is pickled.
"""

import hashlib
import io
import json
import zipfile
from typing import Any

import numpy as np
from numpy.typing import NDArray

from nrmps.params import canonical_json

from .pipeline import SideResult
from .population import ApplicantSide, Population, ProgramSide

FORMAT = "nrmp-population"
FORMAT_VERSION = 1
_ZIP_DATE = (1980, 1, 1, 0, 0, 0)

# Array name -> (side, attribute, little-endian dtype), in digest order.
POPULATION_ARRAYS: dict[str, tuple[str, str, str]] = {
    "applicant_group": ("applicants", "group", "<i2"),
    "applicant_strength": ("applicants", "strength", "<f8"),
    "applicant_attributes": ("applicants", "attributes", "<f8"),
    "applicant_weights": ("applicants", "weights", "<f8"),
    "program_tier": ("programs", "tier", "<i2"),
    "program_quality": ("programs", "quality", "<f8"),
    "program_attributes": ("programs", "attributes", "<f8"),
    "program_weights": ("programs", "weights", "<f8"),
    "program_capacity": ("programs", "capacity", "<i4"),
}


def write_npz(arrays: dict[str, NDArray[Any]], meta: dict[str, Any] | None = None) -> bytes:
    """Return a compressed npz archive of `arrays` (and `meta` as JSON), byte-for-byte reproducible."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        members: dict[str, NDArray[Any]] = dict(arrays)
        if meta is not None:
            members["meta"] = np.frombuffer(canonical_json(meta).encode(), dtype=np.uint8)
        for name in sorted(members):
            data = io.BytesIO()
            np.lib.format.write_array(data, np.ascontiguousarray(members[name]), allow_pickle=False)
            info = zipfile.ZipInfo(f"{name}.npy", date_time=_ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data.getvalue())
    return buffer.getvalue()


def read_npz(data: bytes) -> tuple[dict[str, NDArray[Any]], dict[str, Any]]:
    """Return the arrays and the JSON metadata of an npz archive written by `write_npz`."""
    with np.load(io.BytesIO(data), allow_pickle=False) as archive:
        arrays = {name: archive[name] for name in archive.files if name != "meta"}
        meta = json.loads(archive["meta"].tobytes().decode()) if "meta" in archive.files else {}
    return arrays, meta


def _metadata(population: Population) -> dict[str, Any]:
    a, p = population.applicants, population.programs
    return {
        "format": FORMAT,
        "version": FORMAT_VERSION,
        "group_names": list(a.group_names),
        "applicant_keys": list(a.keys),
        "applicant_weight_keys": list(a.weight_keys),
        "applicant_names": list(a.names) if a.names is not None else None,
        "tier_names": list(p.tier_names),
        "program_keys": list(p.keys),
        "program_weight_keys": list(p.weight_keys),
        "program_names": list(p.names) if p.names is not None else None,
    }


def _arrays(population: Population) -> dict[str, NDArray[Any]]:
    sides = {"applicants": population.applicants, "programs": population.programs}
    return {
        name: np.asarray(getattr(sides[side], attribute)).astype(dtype, copy=False)
        for name, (side, attribute, dtype) in POPULATION_ARRAYS.items()
    }


def population_to_npz(population: Population) -> bytes:
    """Serialise a population."""
    return write_npz(_arrays(population), _metadata(population))


def population_from_npz(data: bytes) -> Population:
    """Load a population written by `population_to_npz`; arrays come back in native byte order."""
    arrays, meta = read_npz(data)
    if meta.get("format") != FORMAT:
        raise ValueError("Not a population file")

    def native(name: str, dtype: type) -> NDArray[Any]:
        return arrays[name].astype(dtype)

    applicant_names, program_names = meta.get("applicant_names"), meta.get("program_names")
    applicants = ApplicantSide(
        group_names=tuple(meta["group_names"]),
        group=native("applicant_group", np.int16),
        strength=native("applicant_strength", np.float64),
        keys=tuple(meta["applicant_keys"]),
        attributes=native("applicant_attributes", np.float64),
        weight_keys=tuple(meta["applicant_weight_keys"]),
        weights=native("applicant_weights", np.float64),
        names=tuple(applicant_names) if applicant_names is not None else None,
    )
    programs = ProgramSide(
        tier_names=tuple(meta["tier_names"]),
        tier=native("program_tier", np.int16),
        quality=native("program_quality", np.float64),
        keys=tuple(meta["program_keys"]),
        attributes=native("program_attributes", np.float64),
        weight_keys=tuple(meta["program_weight_keys"]),
        weights=native("program_weights", np.float64),
        capacity=native("program_capacity", np.int32),
        names=tuple(program_names) if program_names is not None else None,
    )
    return Population(applicants, programs)


def population_digest(population: Population) -> str:
    """Return the SHA-256 of the canonical metadata and the little-endian array bytes."""
    digest = hashlib.sha256(canonical_json(_metadata(population)).encode())
    for name, array in _arrays(population).items():
        digest.update(f"{name}:{array.dtype.str}:{array.shape}".encode())
        digest.update(np.ascontiguousarray(array).tobytes())
    return digest.hexdigest()


def results_to_npz(applicants: SideResult, programs: SideResult) -> bytes:
    """Serialise the per-agent pre-interview results of both sides.

    Arrays are named by the agents they describe: `applicant_popularity` counts, per applicant, the programs that rank
    the applicant first; `program_popularity` counts, per program, the applicants that rank it first.
    """
    arrays = {
        "applicant_first_choice": applicants.first_choice.astype("<i8"),
        "applicant_fidelity": applicants.fidelity.astype("<f8"),
        "applicant_popularity": programs.popularity.astype("<i8"),
        "program_first_choice": programs.first_choice.astype("<i8"),
        "program_fidelity": programs.fidelity.astype("<f8"),
        "program_popularity": applicants.popularity.astype("<i8"),
    }
    return write_npz(arrays, {"format": "nrmp-pre-interview", "version": 1})


def results_from_npz(data: bytes) -> tuple[SideResult, SideResult]:
    """Load (applicant side, program side) results written by `results_to_npz`."""
    arrays, _meta = read_npz(data)
    applicants = SideResult(
        first_choice=arrays["applicant_first_choice"].astype(np.int64),
        fidelity=arrays["applicant_fidelity"].astype(np.float64),
        popularity=arrays["program_popularity"].astype(np.int64),
    )
    programs = SideResult(
        first_choice=arrays["program_first_choice"].astype(np.int64),
        fidelity=arrays["program_fidelity"].astype(np.float64),
        popularity=arrays["applicant_popularity"].astype(np.int64),
    )
    return applicants, programs
