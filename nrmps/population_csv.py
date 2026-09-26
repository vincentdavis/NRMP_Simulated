"""CSV import and export of applicant and program populations (model 2.0).

One module defines the format for both directions, so a download can always be uploaded again unchanged:

- applicants: `name,group,strength,<applicant attributes>,weight:<program attribute>...`
- programs: `name,tier,quality,capacity,<program attributes>,weight:<applicant attribute>...`

`strength`, `quality` and the attributes are on the model's z-scale (mean about 0, SD about 1; docs/model_spec.md
§2). The `program_size` attribute is not a column: it is computed from `capacity`. `group` and `tier` are optional
names (lowercase letters, digits and underscores). The weight columns are optional as a set: each row's weights are
rescaled to add up to 1, and without them the model draws the weights (Dirichlet, §4.4) when the run starts.

The header row is required, the text must be UTF-8 (a byte-order mark, as Excel writes, is fine), and every row is
validated before anything is stored, so a bad file changes nothing.
"""

import csv
import hashlib
import io
import math
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .engine.persistence import read_npz, write_npz
from .engine.population import (
    MAX_NAME_LENGTH,
    PROGRAM_SIZE,
    ApplicantSide,
    PopulationError,
    ProgramSide,
    dirichlet_rows,
    program_size_attribute,
)
from .engine.rng import Stream, replicate_for, stream_generator
from .exceptions import SimulationError
from .params import SimulationParams

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_UPLOAD_ROWS = 50_000
MAX_REPORTED_ERRORS = 20
WEIGHT_PREFIX = "weight:"
DEFAULT_LABEL = {"applicants": "uploaded", "programs": "all"}
LABEL_COLUMN = {"applicants": "group", "programs": "tier"}
LATENT_COLUMN = {"applicants": "strength", "programs": "quality"}
SINGULAR = {"applicants": "applicant", "programs": "program"}
KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
# Weights whose row sum is this close to 1 are kept as they are, so a download uploads back bit for bit.
WEIGHT_SUM_EXACT = 1e-9

F64 = NDArray[np.float64]


@dataclass
class RowError:
    """A problem with one cell or row of an uploaded file."""

    line: int | None
    column: str | None
    message: str

    def __str__(self) -> str:
        """Describe the problem with its line and column, for example "line 3, column strength: is empty."."""
        where = [f"line {self.line}"] if self.line else []
        if self.column:
            where.append(f"column {self.column}")
        return f"{', '.join(where)}: {self.message}" if where else self.message


class PopulationCSVError(SimulationError):
    """An uploaded population file has problems; nothing was changed."""

    def __init__(self, errors: list[RowError], total_errors: int | None = None):
        self.errors = errors
        self.total_errors = total_errors if total_errors is not None else len(errors)
        noun = "problem" if self.total_errors == 1 else "problems"
        super().__init__(f"The file was not loaded ({self.total_errors} {noun}); nothing was changed.")

    @property
    def details(self) -> list[str]:
        """Return the first problems as readable lines."""
        return [str(error) for error in self.errors]


def _fail(message: str, line: int | None = None, column: str | None = None) -> PopulationCSVError:
    return PopulationCSVError(errors=[RowError(line, column, message)], total_errors=1)


# --- Columns ---------------------------------------------------------------------------------------------------------


def attribute_keys(params: SimulationParams, side: str) -> tuple[str, ...]:
    """Return the attribute columns of a side's file (program_size is computed, so it is not a column)."""
    if side == "applicants":
        return tuple(a.key for a in params.applicants.attributes)
    return tuple(a.key for a in params.programs.attributes if a.key != PROGRAM_SIZE)


def weight_keys(params: SimulationParams, side: str) -> tuple[str, ...]:
    """Return the keys a side's weights cover: the other side's attributes."""
    if side == "applicants":
        return tuple(a.key for a in params.programs.attributes)
    return tuple(a.key for a in params.applicants.attributes)


def columns(params: SimulationParams, side: str, *, weights: bool = True) -> list[str]:
    """Return the full header of a side's file for the given parameters."""
    base = ["name", LABEL_COLUMN[side], LATENT_COLUMN[side]]
    if side == "programs":
        base.append("capacity")
    base.extend(attribute_keys(params, side))
    if weights:
        base.extend(f"{WEIGHT_PREFIX}{key}" for key in weight_keys(params, side))
    return base


# --- Parsed uploads --------------------------------------------------------------------------------------------------


@dataclass(frozen=True, eq=False)
class UploadedSide:
    """A validated upload of one side, kept until a run turns it into an engine population side."""

    side: str
    names: tuple[str, ...]
    labels: tuple[str, ...]  # group or tier names, in order of first appearance
    label: NDArray[np.int16]
    latent: F64  # strength or quality
    keys: tuple[str, ...]
    attributes: F64
    weight_keys: tuple[str, ...]
    weights: F64 | None
    capacity: NDArray[np.int32] | None = None

    @property
    def rows(self) -> int:
        """Return the number of rows."""
        return len(self.names)

    def to_npz(self) -> bytes:
        """Serialise the upload."""
        arrays: dict[str, NDArray[Any]] = {
            "label": self.label.astype("<i2"),
            "latent": self.latent.astype("<f8"),
            "attributes": self.attributes.astype("<f8"),
        }
        if self.weights is not None:
            arrays["weights"] = self.weights.astype("<f8")
        if self.capacity is not None:
            arrays["capacity"] = self.capacity.astype("<i4")
        meta = {
            "format": "nrmp-upload",
            "version": 1,
            "side": self.side,
            "names": list(self.names),
            "labels": list(self.labels),
            "keys": list(self.keys),
            "weight_keys": list(self.weight_keys),
        }
        return write_npz(arrays, meta)

    @classmethod
    def from_npz(cls, data: bytes) -> UploadedSide:
        """Load an upload written by `to_npz`."""
        arrays, meta = read_npz(data)
        return cls(
            side=meta["side"],
            names=tuple(meta["names"]),
            labels=tuple(meta["labels"]),
            label=arrays["label"].astype(np.int16),
            latent=arrays["latent"].astype(np.float64),
            keys=tuple(meta["keys"]),
            attributes=arrays["attributes"].astype(np.float64),
            weight_keys=tuple(meta["weight_keys"]),
            weights=arrays["weights"].astype(np.float64) if "weights" in arrays else None,
            capacity=arrays["capacity"].astype(np.int32) if "capacity" in arrays else None,
        )


def digest(data: bytes) -> str:
    """Return the SHA-256 of an upload's bytes."""
    return hashlib.sha256(data).hexdigest()


# --- Parsing ----------------------------------------------------------------------------------------------------------


def _decode(uploaded: Any) -> str:
    """Read an uploaded file (bytes or text) as UTF-8 text, enforcing the size limit."""
    size = getattr(uploaded, "size", None)
    if size is not None and size > MAX_UPLOAD_BYTES:
        raise _fail(f"The file is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    data = uploaded.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise _fail(f"The file is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    if isinstance(data, str):
        return data.removeprefix("﻿")
    try:
        text: str = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise _fail("The file is not UTF-8 text. Save it as “CSV UTF-8” and try again.") from exc
    return text


def _number(text: str, column: str, errors: list[RowError], line: int) -> float | None:
    if not text:
        errors.append(RowError(line, column, "is empty."))
        return None
    try:
        value = float(text)
    except ValueError:
        errors.append(RowError(line, column, f"{text!r} is not a number."))
        return None
    if not math.isfinite(value):
        errors.append(RowError(line, column, f"{text!r} is not a finite number."))
        return None
    return value


def _check_header(header: list[str], params: SimulationParams, side: str) -> bool:
    """Validate the header row; return whether the file has weight columns. Raises PopulationCSVError."""
    if len(set(header)) != len(header):
        duplicates = sorted({name for name in header if header.count(name) > 1})
        raise _fail(f"The column(s) {', '.join(duplicates)} appear more than once.", 1)
    if side == "programs" and PROGRAM_SIZE in header:
        raise _fail("program_size is computed from capacity; remove the program_size column.", 1, PROGRAM_SIZE)
    required = [
        "name",
        LATENT_COLUMN[side],
        *(["capacity"] if side == "programs" else []),
        *attribute_keys(params, side),
    ]
    optional = {LABEL_COLUMN[side]}
    weight_columns = [f"{WEIGHT_PREFIX}{key}" for key in weight_keys(params, side)]
    missing = [name for name in required if name not in header]
    if missing:
        raise _fail(
            f"Missing column(s): {', '.join(missing)}. The header must name the columns "
            f"{', '.join(columns(params, side, weights=False))} (weight columns are optional).",
            1,
        )
    present_weights = [name for name in weight_columns if name in header]
    if present_weights and len(present_weights) != len(weight_columns):
        absent = [name for name in weight_columns if name not in header]
        raise _fail(f"Give all weight columns or none; missing: {', '.join(absent)}.", 1)
    known = set(required) | optional | set(weight_columns)
    unknown = [name for name in header if name not in known]
    if unknown:
        raise _fail(
            f"Unknown column(s): {', '.join(unknown)}. The columns for these parameters are "
            f"{', '.join(columns(params, side))}.",
            1,
        )
    return bool(present_weights)


def parse_population_csv(uploaded: Any, side: str, params: SimulationParams) -> UploadedSide:
    """Parse and validate an uploaded population file for `side` ("applicants" or "programs").

    The attribute columns must be the ones `params` defines. Raises PopulationCSVError listing the problems with
    their line numbers, if the file is too large, has too many rows, or has missing, unknown or invalid values.
    """
    text = _decode(uploaded)
    reader = csv.reader(io.StringIO(text, newline=""))
    first = next(reader, None)
    if not first or not any(cell.strip() for cell in first):
        raise _fail("The file is empty.")
    header = [cell.strip() for cell in first]
    has_weights = _check_header(header, params, side)
    keys, wkeys = attribute_keys(params, side), weight_keys(params, side)
    label_column, latent_column = LABEL_COLUMN[side], LATENT_COLUMN[side]

    errors: list[RowError] = []
    names: list[str] = []
    seen_names: dict[str, int] = {}
    labels: list[str] = []
    latent: list[float] = []
    attributes: list[list[float]] = []
    weights: list[list[float]] = []
    capacity: list[int] = []
    for count, row in enumerate(reader, start=1):
        line = reader.line_num
        if not any(cell.strip() for cell in row):
            continue  # blank line
        if count > MAX_UPLOAD_ROWS:
            raise _fail(f"The file has more than {MAX_UPLOAD_ROWS:,} rows.")
        if len(row) > len(header):
            errors.append(RowError(line, None, "has more values than the header has columns."))
            continue
        cells = dict(zip(header, (cell.strip() for cell in row), strict=False))
        row_errors: list[RowError] = []
        name = cells.get("name", "")
        if not name:
            row_errors.append(RowError(line, "name", "is empty."))
        elif len(name) > MAX_NAME_LENGTH:
            row_errors.append(RowError(line, "name", f"is longer than {MAX_NAME_LENGTH} characters."))
        elif name in seen_names:
            row_errors.append(
                RowError(line, "name", f"{name!r} is also on line {seen_names[name]}; names must be unique.")
            )
        label = cells.get(label_column, "") or DEFAULT_LABEL[side]
        if not KEY_RE.fullmatch(label):
            row_errors.append(
                RowError(line, label_column, f"{label!r} is not a valid name (lowercase letters, digits, _).")
            )
        value = _number(cells.get(latent_column, ""), latent_column, row_errors, line)
        values = [_number(cells.get(key, ""), key, row_errors, line) for key in keys]
        size = None
        if side == "programs":
            raw = _number(cells.get("capacity", ""), "capacity", row_errors, line)
            if raw is not None and (raw != int(raw) or raw < 1):
                row_errors.append(RowError(line, "capacity", f"{raw:g} is not a whole number of 1 or more."))
            elif raw is not None:
                size = int(raw)
        row_weights: list[float | None] = []
        if has_weights:
            row_weights = [
                _number(cells.get(f"{WEIGHT_PREFIX}{k}", ""), f"{WEIGHT_PREFIX}{k}", row_errors, line) for k in wkeys
            ]
            given = [w for w in row_weights if w is not None]
            if any(w < 0 for w in given):
                row_errors.append(RowError(line, None, "weights must not be negative."))
            elif len(given) == len(wkeys) and math.fsum(given) <= 0:
                row_errors.append(RowError(line, None, "the weights add up to 0; give at least one positive weight."))
        errors.extend(row_errors)
        if row_errors:
            continue
        seen_names[name] = line
        names.append(name)
        labels.append(label)
        latent.append(value)  # type: ignore[arg-type]
        attributes.append(values)  # type: ignore[arg-type]
        if side == "programs":
            capacity.append(size)  # type: ignore[arg-type]
        if has_weights:
            total = math.fsum(row_weights)  # type: ignore[arg-type]
            scale = 1.0 if abs(total - 1.0) <= WEIGHT_SUM_EXACT else total
            weights.append([w / scale for w in row_weights])  # type: ignore[operator]
    if errors:
        raise PopulationCSVError(errors=errors[:MAX_REPORTED_ERRORS], total_errors=len(errors))
    if not names:
        raise _fail(f"The file has a header but no {SINGULAR[side]} rows.")
    label_names = tuple(dict.fromkeys(labels))
    return UploadedSide(
        side=side,
        names=tuple(names),
        labels=label_names,
        label=np.array([label_names.index(label) for label in labels], dtype=np.int16),
        latent=np.array(latent, dtype=np.float64),
        keys=keys,
        attributes=np.array(attributes, dtype=np.float64).reshape(len(names), len(keys)),
        weight_keys=wkeys,
        weights=np.array(weights, dtype=np.float64) if has_weights else None,
        capacity=np.array(capacity, dtype=np.int32) if side == "programs" else None,
    )


# --- Uploads into engine sides ----------------------------------------------------------------------------------------


def _columns_by_key(upload: UploadedSide, keys: tuple[str, ...], what: str) -> F64:
    """Return the upload's attribute columns in the order of `keys`, or raise PopulationError if they differ."""
    if set(upload.keys) != set(keys):
        raise PopulationError(
            f"The uploaded {upload.side} have the attributes {', '.join(upload.keys) or 'none'}, but the parameters "
            f"list {', '.join(keys) or 'none'} for {what}. Upload a new file or change the attributes."
        )
    order = [upload.keys.index(key) for key in keys]
    columns_: F64 = upload.attributes[:, order]
    return columns_


def _weights(upload: UploadedSide, expected: tuple[str, ...], rng_weights: F64 | None) -> F64:
    if upload.weights is None:
        if rng_weights is None:
            raise PopulationError(f"The uploaded {upload.side} have no weights and none were drawn.")
        return rng_weights
    if set(upload.weight_keys) != set(expected):
        raise PopulationError(
            f"The uploaded {upload.side} have weights for {', '.join(upload.weight_keys)}, but the parameters list "
            f"{', '.join(expected)}. Upload a new file or change the attributes."
        )
    order = [upload.weight_keys.index(key) for key in expected]
    result: F64 = upload.weights[:, order]
    return result


def _labels(upload: UploadedSide, known: tuple[str, ...]) -> tuple[tuple[str, ...], NDArray[np.int16]]:
    """Return the upload's group or tier names ordered like the parameters' (unknown names after them) and labels."""
    names = tuple(name for name in known if name in upload.labels)
    names += tuple(name for name in upload.labels if name not in names)
    mapping = np.array([names.index(name) for name in upload.labels], dtype=np.int16)
    labels: NDArray[np.int16] = mapping[upload.label]
    return names, labels


def _drawn_weights(params: SimulationParams, side: str, n: int, seed: int, replicate: int) -> F64:
    """Draw the weights of an uploaded side without weight columns, as generation would."""
    stream = Stream.WEIGHTS_A if side == "applicants" else Stream.WEIGHTS_P
    rng = stream_generator(seed, stream, replicate_for(stream, replicate, params.run.resample_population))
    if side == "applicants":
        prior = np.array([a.applicant_weight_prior for a in params.programs.attributes])
    else:
        prior = np.array([a.program_weight_prior for a in params.applicants.attributes])
    return dirichlet_rows(rng, n, prior / prior.sum(), params.prefs.weight_concentration)


def applicant_side(upload: UploadedSide, params: SimulationParams, seed: int, replicate: int = 0) -> ApplicantSide:
    """Turn uploaded applicants into the engine's applicant side for these parameters."""
    keys = tuple(a.key for a in params.applicants.attributes)
    expected_weights = weight_keys(params, "applicants")
    drawn = _drawn_weights(params, "applicants", upload.rows, seed, replicate) if upload.weights is None else None
    group_names, group = _labels(upload, tuple(g.name for g in params.applicants.groups))
    return ApplicantSide(
        group_names=group_names,
        group=group,
        strength=upload.latent,
        keys=keys,
        attributes=_columns_by_key(upload, keys, "applicants"),
        weight_keys=expected_weights,
        weights=_weights(upload, expected_weights, drawn),
        names=upload.names,
    )


def program_side(upload: UploadedSide, params: SimulationParams, seed: int, replicate: int = 0) -> ProgramSide:
    """Turn uploaded programs into the engine's program side, computing program_size from capacity."""
    if upload.capacity is None:
        raise PopulationError("The uploaded programs have no capacities.")
    keys = tuple(a.key for a in params.programs.attributes)
    uploaded_keys = tuple(key for key in keys if key != PROGRAM_SIZE)
    given = _columns_by_key(upload, uploaded_keys, "programs")
    attributes = np.empty((upload.rows, len(keys)), dtype=np.float64)
    for index, key in enumerate(keys):
        attributes[:, index] = (
            program_size_attribute(upload.capacity) if key == PROGRAM_SIZE else given[:, uploaded_keys.index(key)]
        )
    expected_weights = weight_keys(params, "programs")
    drawn = _drawn_weights(params, "programs", upload.rows, seed, replicate) if upload.weights is None else None
    tier_names, tier = _labels(upload, tuple(t.name for t in params.programs.tiers) or (DEFAULT_LABEL["programs"],))
    return ProgramSide(
        tier_names=tier_names,
        tier=tier,
        quality=upload.latent,
        keys=keys,
        attributes=attributes,
        weight_keys=expected_weights,
        weights=_weights(upload, expected_weights, drawn),
        capacity=upload.capacity,
        names=upload.names,
    )


# --- Writing ----------------------------------------------------------------------------------------------------------


class _Echo:
    """A write-only file-like object that returns what it is given, for streaming CSV."""

    def write(self, value: str) -> str:
        """Return the value instead of storing it."""
        return value


def plain_csv_lines(header: list[str], rows: Iterable[Iterable[Any]]) -> Iterator[str]:
    """Yield CSV lines (header first) for plain rows."""
    writer = csv.writer(_Echo())
    yield writer.writerow(header)
    for row in rows:
        yield writer.writerow(row)


def _number_text(value: float) -> str:
    """Write a float so that it reads back exactly."""
    return repr(float(value))


def applicant_rows(side: ApplicantSide) -> Iterator[list[str]]:
    """Yield the applicants as rows of the upload format (without the header)."""
    for i in range(side.size):
        yield [
            side.name(i),
            side.group_names[side.group[i]],
            _number_text(side.strength[i]),
            *(_number_text(v) for v in side.attributes[i]),
            *(_number_text(w) for w in side.weights[i]),
        ]


def program_rows(side: ProgramSide) -> Iterator[list[str]]:
    """Yield the programs as rows of the upload format (without the header); program_size is left out."""
    keep = [k for k, key in enumerate(side.keys) if key != PROGRAM_SIZE]
    for j in range(side.size):
        yield [
            side.name(j),
            side.tier_names[side.tier[j]],
            _number_text(side.quality[j]),
            str(int(side.capacity[j])),
            *(_number_text(side.attributes[j, k]) for k in keep),
            *(_number_text(w) for w in side.weights[j]),
        ]


def population_csv_lines(side: ApplicantSide | ProgramSide) -> Iterator[str]:
    """Yield a side as CSV lines in the upload format, header first."""
    if isinstance(side, ApplicantSide):
        header = ["name", "group", "strength", *side.keys, *(f"{WEIGHT_PREFIX}{k}" for k in side.weight_keys)]
        return plain_csv_lines(header, applicant_rows(side))
    keys = [key for key in side.keys if key != PROGRAM_SIZE]
    header = ["name", "tier", "quality", "capacity", *keys, *(f"{WEIGHT_PREFIX}{k}" for k in side.weight_keys)]
    return plain_csv_lines(header, program_rows(side))


def uploaded_csv_lines(upload: UploadedSide) -> Iterator[str]:
    """Yield an upload as CSV lines in the upload format, header first (for the personal data export)."""
    label = LABEL_COLUMN[upload.side]
    header = ["name", label, LATENT_COLUMN[upload.side]]
    if upload.capacity is not None:
        header.append("capacity")
    header.extend(upload.keys)
    if upload.weights is not None:
        header.extend(f"{WEIGHT_PREFIX}{key}" for key in upload.weight_keys)

    def rows() -> Iterator[list[str]]:
        for row in range(upload.rows):
            cells = [upload.names[row], upload.labels[upload.label[row]], _number_text(upload.latent[row])]
            if upload.capacity is not None:
                cells.append(str(int(upload.capacity[row])))
            cells.extend(_number_text(value) for value in upload.attributes[row])
            if upload.weights is not None:
                cells.extend(_number_text(value) for value in upload.weights[row])
            yield cells

    return plain_csv_lines(header, rows())
