"""Small JSON persistence layer used by every page.

Local writes are atomic to reduce the chance of a partially written file. The
UI also exposes import/export because Community Cloud storage is not durable.
"""

from __future__ import annotations

import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

from workout_app.migrations import migrate_documents
from workout_app.validation import DataValidationError, validate_all


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIRECTORY = PROJECT_ROOT / "data"
EXERCISES_PATH = DATA_DIRECTORY / "exercises.json"
ROUTINES_PATH = DATA_DIRECTORY / "routines.json"


class DataLoadError(RuntimeError):
    """Raised when a JSON file cannot be read or decoded."""


def _read_json(path: Path) -> dict[str, Any]:
    """Read a JSON object and provide an actionable error if it is malformed."""

    try:
        with path.open("r", encoding="utf-8") as input_file:
            document = json.load(input_file)
    except FileNotFoundError as error:
        raise DataLoadError(f"Data file is missing: {path}") from error
    except json.JSONDecodeError as error:
        raise DataLoadError(
            f"{path.name} contains malformed JSON at line {error.lineno}, column {error.colno}."
        ) from error
    except OSError as error:
        raise DataLoadError(f"Could not read {path.name}: {error}") from error

    if not isinstance(document, dict):
        raise DataLoadError(f"{path.name} must contain a JSON object at its top level.")
    return document


def load_data() -> tuple[dict[str, Any], dict[str, Any]]:
    """Load and validate both data files before returning independent objects."""

    exercise_document = _read_json(EXERCISES_PATH)
    routine_document = _read_json(ROUTINES_PATH)
    exercise_document, routine_document = migrate_documents(
        exercise_document, routine_document
    )
    validate_all(exercise_document, routine_document)
    return exercise_document, routine_document


def _atomic_write_json(path: Path, document: dict[str, Any]) -> None:
    """Replace a JSON file only after a complete temporary file is written."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
        ) as temporary_file:
            json.dump(document, temporary_file, indent=2, ensure_ascii=False)
            temporary_file.write("\n")
            temporary_path = temporary_file.name
        os.replace(temporary_path, path)
    except OSError as error:
        raise DataLoadError(f"Could not save {path.name}: {error}") from error
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.unlink(temporary_path)


def save_data(exercise_document: dict[str, Any], routine_document: dict[str, Any]) -> None:
    """Validate the complete model, then persist both JSON documents."""

    validate_all(exercise_document, routine_document)
    _atomic_write_json(EXERCISES_PATH, exercise_document)
    _atomic_write_json(ROUTINES_PATH, routine_document)


def data_bundle_json(exercise_document: dict[str, Any], routine_document: dict[str, Any]) -> str:
    """Create a portable single-file backup for browser download."""

    bundle = {
        "bundle_version": 1,
        "exercises": deepcopy(exercise_document),
        "routines": deepcopy(routine_document),
    }
    return json.dumps(bundle, indent=2, ensure_ascii=False) + "\n"


def parse_data_bundle(raw_data: bytes) -> tuple[dict[str, Any], dict[str, Any]]:
    """Decode and validate a user-uploaded backup without writing it first."""

    try:
        bundle = json.loads(raw_data.decode("utf-8"))
    except UnicodeDecodeError as error:
        raise DataLoadError("The imported backup must be UTF-8 encoded.") from error
    except json.JSONDecodeError as error:
        raise DataLoadError(
            f"The imported backup has malformed JSON at line {error.lineno}, column {error.colno}."
        ) from error

    if not isinstance(bundle, dict) or bundle.get("bundle_version") != 1:
        raise DataValidationError(["The uploaded file is not a version 1 workout-data backup."])
    exercise_document = bundle.get("exercises")
    routine_document = bundle.get("routines")
    if isinstance(exercise_document, dict) and isinstance(routine_document, dict):
        exercise_document, routine_document = migrate_documents(
            exercise_document, routine_document
        )
    validate_all(exercise_document, routine_document)
    return exercise_document, routine_document


def exercise_reference_locations(routine_document: dict[str, Any], exercise_id: str) -> list[str]:
    """List routine/slot locations that prevent an exercise from being deleted."""

    references: list[str] = []
    for routine in routine_document["routines"]:
        for slot in routine["slots"]:
            if exercise_id == slot["default_exercise_id"]:
                references.append(f"{routine['name']} (default, slot {slot['order']})")
            if exercise_id in slot["alternative_exercise_ids"]:
                references.append(f"{routine['name']} (alternative, slot {slot['order']})")
    return references
