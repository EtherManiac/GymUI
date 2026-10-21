"""Pure calendar and completed-workout transformations."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo


APP_TIME_ZONE = ZoneInfo("America/Chicago")


def local_today() -> date:
    """Return the application's current calendar date."""

    return datetime.now(APP_TIME_ZONE).date()


def empty_calendar_document() -> dict[str, Any]:
    """Return a new profile calendar document."""

    return {"schema_version": 1, "events": []}


def events_on_date(
    calendar_document: dict[str, Any], selected_date: date
) -> list[dict[str, Any]]:
    """Return independent calendar events for one date."""

    date_text = selected_date.isoformat()
    return [
        deepcopy(event)
        for event in calendar_document["events"]
        if event["date"] == date_text
    ]


def scheduled_event_on_date(
    calendar_document: dict[str, Any], selected_date: date
) -> dict[str, Any] | None:
    """Return the single scheduled event for a date, if present."""

    return next(
        (
            event
            for event in events_on_date(calendar_document, selected_date)
            if event["status"] == "scheduled"
        ),
        None,
    )


def schedule_routine(
    calendar_document: dict[str, Any],
    selected_date: date,
    routine: dict[str, Any],
    *,
    event_id: str,
    created_at: str,
) -> tuple[dict[str, Any], str]:
    """Schedule one routine, replacing any prior schedule for that date."""

    updated = deepcopy(calendar_document)
    date_text = selected_date.isoformat()
    updated["events"] = [
        event
        for event in updated["events"]
        if not (event["date"] == date_text and event["status"] == "scheduled")
    ]
    updated["events"].append(
        {
            "id": event_id,
            "date": date_text,
            "status": "scheduled",
            "routine_id": routine["id"],
            "routine_name": routine["name"],
            "created_at": created_at,
        }
    )
    return updated, event_id


def remove_scheduled_routine(
    calendar_document: dict[str, Any], selected_date: date
) -> dict[str, Any]:
    """Remove a date's scheduled routine while preserving completed history."""

    updated = deepcopy(calendar_document)
    date_text = selected_date.isoformat()
    updated["events"] = [
        event
        for event in updated["events"]
        if not (event["date"] == date_text and event["status"] == "scheduled")
    ]
    return updated


def remove_calendar_event(
    calendar_document: dict[str, Any], event_id: str
) -> dict[str, Any]:
    """Remove one scheduled or completed event by its stable identifier."""

    updated = deepcopy(calendar_document)
    updated["events"] = [
        event for event in updated["events"] if event["id"] != event_id
    ]
    return updated


def log_completed_workout(
    calendar_document: dict[str, Any],
    selected_date: date,
    routine: dict[str, Any],
    snapshot: list[dict[str, Any]],
    exercise_by_id: dict[str, dict[str, Any]],
    *,
    event_id: str,
    workout_session_id: str,
    completed_at: str,
    source: str,
) -> tuple[dict[str, Any], str]:
    """Append an immutable completed-workout snapshot exactly once per session."""

    existing = next(
        (
            event
            for event in calendar_document["events"]
            if event.get("status") == "completed"
            and event.get("workout_session_id") == workout_session_id
        ),
        None,
    )
    if existing is not None:
        return deepcopy(calendar_document), existing["id"]

    date_text = selected_date.isoformat()
    updated = deepcopy(calendar_document)
    updated["events"] = [
        event
        for event in updated["events"]
        if not (
            event["date"] == date_text
            and event["status"] == "scheduled"
            and event["routine_id"] == routine["id"]
        )
    ]
    completed_exercises = []
    for row in sorted(snapshot, key=lambda item: item["slot"]["order"]):
        slot = row["slot"]
        exercise_id = row["selected_exercise_id"]
        completed_exercises.append(
            {
                "slot_id": slot["id"],
                "exercise_id": exercise_id,
                "exercise_name": exercise_by_id[exercise_id]["name"],
                "sets": slot["sets"],
                "reps": slot["reps"],
                "reference_weight": slot["reference_weight"],
                "weight_used": str(row.get("weight_used", "")),
            }
        )
    updated["events"].append(
        {
            "id": event_id,
            "date": date_text,
            "status": "completed",
            "routine_id": routine["id"],
            "routine_name": routine["name"],
            "workout_session_id": workout_session_id,
            "completed_at": completed_at,
            "source": source,
            "exercises": completed_exercises,
        }
    )
    return updated, event_id
