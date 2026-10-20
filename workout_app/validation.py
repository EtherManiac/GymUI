"""Validation for exercise and routine JSON documents.

Validation lives outside the UI so malformed files and imports are handled the
same way on every page.
"""

from __future__ import annotations

from typing import Any


class DataValidationError(ValueError):
    """Raised when stored or imported workout data is not safe to use."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("\n".join(errors))


def _is_non_empty_string(value: Any) -> bool:
    """Return whether a value is a string containing visible characters."""

    return isinstance(value, str) and bool(value.strip())


def validate_exercise_document(document: Any) -> list[str]:
    """Return actionable validation errors for an exercise document."""

    errors: list[str] = []
    if not isinstance(document, dict):
        return ["Exercise data must be a JSON object."]
    if document.get("schema_version") != 1:
        errors.append("Exercise data must use schema_version 1.")

    exercises = document.get("exercises")
    if not isinstance(exercises, list):
        return errors + ["The 'exercises' field must be a list."]

    seen_ids: set[str] = set()
    for index, exercise in enumerate(exercises, start=1):
        location = f"Exercise #{index}"
        if not isinstance(exercise, dict):
            errors.append(f"{location} must be an object.")
            continue

        exercise_id = exercise.get("id")
        if not _is_non_empty_string(exercise_id):
            errors.append(f"{location} needs a non-empty 'id'.")
        elif exercise_id in seen_ids:
            errors.append(f"Exercise ID '{exercise_id}' is duplicated.")
        else:
            seen_ids.add(exercise_id)

        if not _is_non_empty_string(exercise.get("name")):
            errors.append(f"{location} needs a non-empty 'name'.")

        tags = exercise.get("tags")
        if not isinstance(tags, list) or any(not _is_non_empty_string(tag) for tag in tags):
            errors.append(f"{location} must have a 'tags' list containing only non-empty strings.")

        for optional_field in ("notes", "demo_url"):
            value = exercise.get(optional_field, "")
            if not isinstance(value, str):
                errors.append(f"{location} field '{optional_field}' must be a string.")

    return errors


def validate_routine_document(document: Any, exercise_ids: set[str]) -> list[str]:
    """Return validation errors for routines, including broken references."""

    errors: list[str] = []
    if not isinstance(document, dict):
        return ["Routine data must be a JSON object."]
    if document.get("schema_version") != 1:
        errors.append("Routine data must use schema_version 1.")

    routines = document.get("routines")
    if not isinstance(routines, list):
        return errors + ["The 'routines' field must be a list."]

    routine_ids: set[str] = set()
    slot_ids: set[str] = set()
    for routine_index, routine in enumerate(routines, start=1):
        routine_location = f"Routine #{routine_index}"
        if not isinstance(routine, dict):
            errors.append(f"{routine_location} must be an object.")
            continue

        routine_id = routine.get("id")
        if not _is_non_empty_string(routine_id):
            errors.append(f"{routine_location} needs a non-empty 'id'.")
        elif routine_id in routine_ids:
            errors.append(f"Routine ID '{routine_id}' is duplicated.")
        else:
            routine_ids.add(routine_id)

        if not _is_non_empty_string(routine.get("name")):
            errors.append(f"{routine_location} needs a non-empty 'name'.")

        slots = routine.get("slots")
        if not isinstance(slots, list):
            errors.append(f"{routine_location} field 'slots' must be a list.")
            continue

        orders: set[int] = set()
        for slot_index, slot in enumerate(slots, start=1):
            location = f"{routine_location}, slot #{slot_index}"
            if not isinstance(slot, dict):
                errors.append(f"{location} must be an object.")
                continue

            slot_id = slot.get("id")
            if not _is_non_empty_string(slot_id):
                errors.append(f"{location} needs a non-empty 'id'.")
            elif slot_id in slot_ids:
                errors.append(f"Slot ID '{slot_id}' is duplicated.")
            else:
                slot_ids.add(slot_id)

            order = slot.get("order")
            if not isinstance(order, int) or order < 1:
                errors.append(f"{location} needs a positive integer 'order'.")
            elif order in orders:
                errors.append(f"{routine_location} has duplicate order value {order}.")
            else:
                orders.add(order)

            priority = slot.get("priority")
            if not isinstance(priority, int) or isinstance(priority, bool) or priority < 1:
                errors.append(f"{location} needs a positive integer 'priority'.")

            required_tags = slot.get("required_tags")
            if not isinstance(required_tags, list) or any(
                not _is_non_empty_string(tag) for tag in required_tags
            ):
                errors.append(f"{location} field 'required_tags' must be a list of non-empty strings.")

            default_id = slot.get("default_exercise_id")
            if default_id not in exercise_ids:
                errors.append(f"{location} references missing default exercise '{default_id}'.")

            alternatives = slot.get("alternative_exercise_ids")
            if not isinstance(alternatives, list):
                errors.append(f"{location} field 'alternative_exercise_ids' must be a list.")
            else:
                if len(alternatives) != len(set(alternatives)):
                    errors.append(f"{location} contains duplicate alternative exercise IDs.")
                for alternative_id in alternatives:
                    if alternative_id not in exercise_ids:
                        errors.append(f"{location} references missing alternative '{alternative_id}'.")
                    if alternative_id == default_id:
                        errors.append(f"{location} repeats its default exercise as an alternative.")

            for required_field in ("sets", "reps", "reference_weight"):
                if not _is_non_empty_string(slot.get(required_field)):
                    errors.append(f"{location} needs a non-empty '{required_field}'.")

            group_id = slot.get("superset_group_id")
            if group_id is not None and not _is_non_empty_string(group_id):
                errors.append(f"{location} field 'superset_group_id' must be null or a non-empty string.")

        # A superset is selected as one unit, so conflicting member priorities
        # would make shortening ambiguous. Require one shared group priority.
        group_priorities: dict[str, set[int]] = {}
        for slot in slots:
            if isinstance(slot, dict) and _is_non_empty_string(slot.get("superset_group_id")):
                priority = slot.get("priority")
                if isinstance(priority, int) and not isinstance(priority, bool):
                    group_priorities.setdefault(slot["superset_group_id"], set()).add(priority)
        for group_id, priorities in group_priorities.items():
            if len(priorities) > 1:
                errors.append(
                    f"{routine_location} superset '{group_id}' must use one shared priority."
                )

    return errors


def validate_all(exercise_document: Any, routine_document: Any) -> None:
    """Raise one error containing every problem found across both documents."""

    exercise_errors = validate_exercise_document(exercise_document)
    exercise_ids = {
        exercise.get("id")
        for exercise in exercise_document.get("exercises", [])
        if isinstance(exercise, dict) and _is_non_empty_string(exercise.get("id"))
    } if isinstance(exercise_document, dict) else set()
    routine_errors = validate_routine_document(routine_document, exercise_ids)
    errors = exercise_errors + routine_errors
    if errors:
        raise DataValidationError(errors)
