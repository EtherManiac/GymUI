"""Tests for scheduling and immutable workout-history records."""

from __future__ import annotations

import unittest
from datetime import date

from workout_app.calendar_logic import (
    empty_calendar_document,
    log_completed_workout,
    remove_calendar_event,
    schedule_routine,
    scheduled_event_on_date,
)
from workout_app.validation import validate_calendar_document
from workout_app.workout_logic import new_workout_snapshot


class CalendarLogicTests(unittest.TestCase):
    def setUp(self) -> None:
        self.exercise = {
            "id": "row",
            "name": "Cable row",
            "muscles_targeted": ["Back"],
            "tags": ["Pull"],
            "notes": "",
            "demo_url": "",
        }
        self.routine = {
            "id": "pull",
            "name": "Pull day",
            "slots": [
                {
                    "id": "row-slot",
                    "order": 1,
                    "priority": 1,
                    "required_muscles": ["Back"],
                    "required_tags": ["Pull"],
                    "default_exercise_id": "row",
                    "alternative_exercise_ids": [],
                    "sets": "3",
                    "reps": "8-12",
                    "reference_weight": "90 lb",
                    "superset_group_id": None,
                }
            ],
        }
        self.day = date(2026, 10, 20)

    def test_scheduling_replaces_only_the_dates_previous_schedule(self) -> None:
        calendar, _ = schedule_routine(
            empty_calendar_document(),
            self.day,
            self.routine,
            event_id="first",
            created_at="2026-10-01T12:00:00+00:00",
        )
        replacement = {**self.routine, "id": "legs", "name": "Leg day"}
        calendar, _ = schedule_routine(
            calendar,
            self.day,
            replacement,
            event_id="second",
            created_at="2026-10-02T12:00:00+00:00",
        )

        scheduled = scheduled_event_on_date(calendar, self.day)
        self.assertEqual(scheduled["id"], "second")
        self.assertEqual(len(calendar["events"]), 1)
        validate_calendar_document(calendar)

    def test_completion_removes_schedule_and_is_idempotent_by_session(self) -> None:
        calendar, _ = schedule_routine(
            empty_calendar_document(),
            self.day,
            self.routine,
            event_id="scheduled",
            created_at="2026-10-01T12:00:00+00:00",
        )
        snapshot = new_workout_snapshot(self.routine, 1)
        snapshot[0].update(completed=True, weight_used="95.5")

        completed, first_event_id = log_completed_workout(
            calendar,
            self.day,
            self.routine,
            snapshot,
            {"row": self.exercise},
            event_id="completed",
            workout_session_id="session-1",
            completed_at="2026-10-20T12:00:00+00:00",
            source="calendar",
        )
        repeated, repeated_event_id = log_completed_workout(
            completed,
            self.day,
            self.routine,
            snapshot,
            {"row": self.exercise},
            event_id="duplicate",
            workout_session_id="session-1",
            completed_at="2026-10-20T12:01:00+00:00",
            source="calendar",
        )

        self.assertEqual(first_event_id, "completed")
        self.assertEqual(repeated_event_id, "completed")
        self.assertEqual(len(repeated["events"]), 1)
        event = repeated["events"][0]
        self.assertEqual(event["status"], "completed")
        self.assertEqual(event["exercises"][0]["weight_used"], "95.5")
        self.assertEqual(event["exercises"][0]["exercise_name"], "Cable row")
        validate_calendar_document(repeated)

    def test_calendar_event_can_be_removed_by_id(self) -> None:
        calendar, _ = schedule_routine(
            empty_calendar_document(),
            self.day,
            self.routine,
            event_id="remove-me",
            created_at="2026-10-01T12:00:00+00:00",
        )

        updated = remove_calendar_event(calendar, "remove-me")

        self.assertEqual(updated["events"], [])
        self.assertEqual(len(calendar["events"]), 1)
        validate_calendar_document(updated)


if __name__ == "__main__":
    unittest.main()
