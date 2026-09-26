"""CSV import and export of applicant and program populations.

One module defines the format for both directions, so a download can always be uploaded again unchanged:

- applicants (students): `name,score,score_meta,meta_preference`
- programs (schools): `name,capacity,score,score_meta,meta_preference`

`score_meta` and `meta_preference` are JSON objects mapping attribute names to numbers; they may be left empty.
The header row is required, UTF-8 is expected (a byte-order mark, as Excel writes, is fine) and every row is
validated before anything is stored, so a bad file changes nothing.
"""

import csv
import io
import json
import math
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from .exceptions import SimulationError
from .validators import ATTRIBUTE_NAME_PATTERN

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_UPLOAD_ROWS = 50_000
MAX_REPORTED_ERRORS = 20

COLUMNS = {
    "students": ["name", "score", "score_meta", "meta_preference"],
    "schools": ["name", "capacity", "score", "score_meta", "meta_preference"],
}
REQUIRED = {
    "students": {"name", "score"},
    "schools": {"name", "capacity", "score"},
}
LABELS = {"students": "applicant", "schools": "program"}


@dataclass
class RowError:
    """A problem with one cell or row of an uploaded file."""

    line: int | None
    column: str | None
    message: str

    def __str__(self) -> str:
        """Describe the problem with its line and column, for example "line 3, column score: is empty."."""
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


def _decode(uploaded) -> str:
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
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise _fail("The file is not UTF-8 text. Save it as “CSV UTF-8” and try again.") from exc


def _number(text: str, column: str, errors: list[RowError], line: int) -> float | None:
    try:
        value = float(text)
    except ValueError:
        errors.append(RowError(line, column, f"{text!r} is not a number."))
        return None
    if not math.isfinite(value):
        errors.append(RowError(line, column, f"{text!r} is not a finite number."))
        return None
    return value


def _mapping(text: str, column: str, errors: list[RowError], line: int, *, unit: bool) -> dict[str, float]:
    """Parse a JSON object of attribute name -> number (in 0-1 if `unit`, else >= 0)."""
    text = text.strip()
    if not text:
        return {}
    try:
        value = json.loads(text)
    except ValueError:
        errors.append(RowError(line, column, 'is not valid JSON; expected an object such as {"research": 0.5}.'))
        return {}
    if not isinstance(value, dict):
        errors.append(RowError(line, column, 'must be a JSON object such as {"research": 0.5}.'))
        return {}
    result = {}
    for key, number in value.items():
        if not ATTRIBUTE_NAME_PATTERN.fullmatch(key):
            errors.append(
                RowError(line, column, f"{key!r} is not a valid attribute name (lowercase letters, digits, _).")
            )
            continue
        if isinstance(number, bool) or not isinstance(number, int | float) or not math.isfinite(number):
            errors.append(RowError(line, column, f"the value for {key!r} must be a number."))
            continue
        if unit and not 0 <= number <= 1:
            errors.append(RowError(line, column, f"the value for {key!r} must be between 0 and 1."))
            continue
        if not unit and number < 0:
            errors.append(RowError(line, column, f"the value for {key!r} must not be negative."))
            continue
        result[key] = float(number)
    return result


def parse_population_csv(uploaded, kind: str) -> list[dict]:
    """Parse and validate an uploaded population CSV; return one dict per row with typed values.

    `kind` is "students" or "schools". Raises PopulationCSVError listing the problems (with line numbers) if the
    file is too large, has too many rows, lacks required columns, has unknown columns or has invalid values.
    """
    text = _decode(uploaded)
    reader = csv.DictReader(io.StringIO(text, newline=""))
    header = [name.strip() for name in (reader.fieldnames or [])]
    if not header:
        raise _fail("The file is empty.")
    reader.fieldnames = header
    missing = [c for c in COLUMNS[kind] if c in REQUIRED[kind] and c not in header]
    if missing:
        raise _fail(
            f"The header row must name the columns {', '.join(COLUMNS[kind])} (missing: {', '.join(missing)}).", 1
        )
    unknown = [c for c in header if c not in COLUMNS[kind]]
    if unknown:
        raise _fail(f"Unknown column(s): {', '.join(unknown)}. Allowed: {', '.join(COLUMNS[kind])}.", 1)

    errors: list[RowError] = []
    rows: list[dict] = []
    for count, record in enumerate(reader, start=1):
        line = reader.line_num
        if count > MAX_UPLOAD_ROWS:
            raise _fail(f"The file has more than {MAX_UPLOAD_ROWS:,} rows.")
        if None in record:  # more cells than header columns
            errors.append(RowError(line, None, "has more values than the header has columns."))
            continue
        cells = {key: (value or "").strip() for key, value in record.items()}
        row_errors: list[RowError] = []
        name = cells.get("name", "")
        if not name:
            row_errors.append(RowError(line, "name", "is empty."))
        elif len(name) > 255:
            row_errors.append(RowError(line, "name", "is longer than 255 characters."))
        score = _number(cells.get("score", ""), "score", row_errors, line)
        if score is not None and not 0 <= score <= 1:
            row_errors.append(RowError(line, "score", f"{score:g} is not between 0 and 1."))
        row = {
            "name": name,
            "score": score,
            "score_meta": _mapping(cells.get("score_meta", ""), "score_meta", row_errors, line, unit=True),
            "meta_preference": _mapping(
                cells.get("meta_preference", ""), "meta_preference", row_errors, line, unit=False
            ),
        }
        if kind == "schools":
            capacity = _number(cells.get("capacity", ""), "capacity", row_errors, line)
            if capacity is not None and (capacity != int(capacity) or capacity < 0):
                row_errors.append(RowError(line, "capacity", f"{capacity:g} is not a whole number of 0 or more."))
            row["capacity"] = None if capacity is None else int(capacity)
        errors.extend(row_errors)
        if not row_errors:
            rows.append(row)
    if errors:
        raise PopulationCSVError(errors=errors[:MAX_REPORTED_ERRORS], total_errors=len(errors))
    if not rows:
        raise _fail(f"The file has a header but no {LABELS[kind]} rows.")
    return rows


class _Echo:
    """A write-only file-like object that returns what it is given, for streaming CSV."""

    def write(self, value):
        """Return the value instead of storing it."""
        return value


def csv_lines(kind: str, records: Iterable[tuple]) -> Iterator[str]:
    """Yield CSV lines (header first) for population records, in the format `parse_population_csv` reads.

    `records` yields tuples in `COLUMNS[kind]` order, with the two JSON columns as dicts.
    """
    writer = csv.writer(_Echo())
    yield writer.writerow(COLUMNS[kind])
    for record in records:
        *plain, score_meta, meta_preference = record
        yield writer.writerow(
            [
                *plain,
                json.dumps(score_meta or {}, ensure_ascii=False),
                json.dumps(meta_preference or {}, ensure_ascii=False),
            ]
        )
