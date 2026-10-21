"""Small JSON persistence layer used by every page.

Local writes are atomic to reduce the chance of a partially written file. The
UI also exposes import/export because Community Cloud storage is not durable.
"""

from __future__ import annotations

import json
import os
import tempfile
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from workout_app.migrations import migrate_documents
from workout_app.users import user_name
from workout_app.validation import DataValidationError, validate_all
from workout_app.workout_logic import is_valid_weight_input, new_workout_snapshot


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIRECTORY = PROJECT_ROOT / "data"
USER_DATA_DIRECTORY = DATA_DIRECTORY / "users"
WORKOUT_DRAFT_LIFETIME = timedelta(hours=12)
UTC_TIMEZONE = timezone.utc


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


def _user_directory(user_id: str) -> Path:
    """Return the data directory for a known hard-coded profile."""

    user_name(user_id)
    return USER_DATA_DIRECTORY / user_id


def _user_data_paths(user_id: str) -> tuple[Path, Path]:
    directory = _user_directory(user_id)
    return directory / "exercises.json", directory / "routines.json"


def load_data(user_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load and validate both data files before returning independent objects."""

    exercises_path, routines_path = _user_data_paths(user_id)
    exercise_document = _read_json(exercises_path)
    routine_document = _read_json(routines_path)
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


def save_data(
    user_id: str,
    exercise_document: dict[str, Any],
    routine_document: dict[str, Any],
) -> None:
    """Validate the complete model, then persist both JSON documents."""

    validate_all(exercise_document, routine_document)
    exercises_path, routines_path = _user_data_paths(user_id)

    # This app assumes very low write concurrency. Two devices editing the
    # same profile simultaneously can still overwrite one another's changes.
    # Add file locking or transactional storage if that usage becomes common.
    _atomic_write_json(exercises_path, exercise_document)
    _atomic_write_json(routines_path, routine_document)


def _draft_path(user_id: str) -> Path:
    return _user_directory(user_id) / "active_workout.json"


def save_workout_draft(
    user_id: str,
    routine_id: str,
    requested_count: int,
    snapshot: list[dict[str, Any]],
) -> None:
    """Persist the recoverable parts of an in-progress workout."""

    document = {
        "draft_version": 1,
        "saved_at": datetime.now(UTC_TIMEZONE).isoformat(),
        "routine_id": routine_id,
        "requested_count": requested_count,
        "rows": [
            {
                "slot_id": row["slot"]["id"],
                "selected_exercise_id": row["selected_exercise_id"],
                "completed": bool(row["completed"]),
                "weight_used": str(row.get("weight_used", "")),
                "base_position": int(row.get("base_position", position)),
            }
            for position, row in enumerate(snapshot)
        ],
    }
    _atomic_write_json(_draft_path(user_id), document)


def delete_workout_draft(user_id: str) -> None:
    """Remove a saved workout draft when reset, declined, or expired."""

    try:
        _draft_path(user_id).unlink()
    except FileNotFoundError:
        pass
    except OSError as error:
        raise DataLoadError(f"Could not remove the saved workout: {error}") from error


def load_workout_draft(
    user_id: str,
    routine_document: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """Return a recent, internally consistent workout draft if one exists."""

    path = _draft_path(user_id)
    if not path.exists():
        return None
    try:
        document = _read_json(path)
        saved_at = datetime.fromisoformat(str(document["saved_at"]))
        if saved_at.tzinfo is None:
            saved_at = saved_at.replace(tzinfo=UTC_TIMEZONE)
        current_time = now or datetime.now(UTC_TIMEZONE)
        if current_time - saved_at > WORKOUT_DRAFT_LIFETIME:
            delete_workout_draft(user_id)
            return None

        if document.get("draft_version") != 1:
            return None
        routine_id = str(document["routine_id"])
        requested_count = int(document["requested_count"])
        routine = next(
            routine
            for routine in routine_document["routines"]
            if routine["id"] == routine_id
        )
        if not 1 <= requested_count <= len(routine["slots"]):
            return None

        clean_snapshot = new_workout_snapshot(routine, requested_count)
        rows = document["rows"]
        if not isinstance(rows, list) or len(rows) != len(clean_snapshot):
            return None
        saved_by_slot = {row["slot_id"]: row for row in rows}
        if set(saved_by_slot) != {row["slot"]["id"] for row in clean_snapshot}:
            return None

        restored: list[dict[str, Any]] = []
        snapshot_by_slot = {row["slot"]["id"]: row for row in clean_snapshot}
        for saved_row in rows:
            row = snapshot_by_slot[saved_row["slot_id"]]
            allowed_ids = {
                row["slot"]["default_exercise_id"],
                *row["slot"].get("alternative_exercise_ids", []),
            }
            selected_id = str(saved_row["selected_exercise_id"])
            weight_used = str(saved_row.get("weight_used", ""))
            if selected_id not in allowed_ids or not is_valid_weight_input(weight_used):
                return None
            row.update(
                selected_exercise_id=selected_id,
                completed=bool(saved_row.get("completed", False)),
                weight_used=weight_used,
                base_position=int(saved_row.get("base_position", len(restored))),
            )
            restored.append(row)

        return {
            "saved_at": saved_at,
            "routine_id": routine_id,
            "routine_name": routine["name"],
            "requested_count": requested_count,
            "snapshot": restored,
        }
    except (DataLoadError, KeyError, TypeError, ValueError, StopIteration):
        return None


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
