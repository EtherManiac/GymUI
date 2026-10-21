"""Headless Streamlit checks for scheduling and finishing a workout."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from workout_app import storage
from workout_app.calendar_logic import (
    empty_calendar_document,
    local_today,
    log_completed_workout,
    schedule_routine,
)
from workout_app.workout_logic import new_workout_snapshot


class CalendarUiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        temporary_users = Path(self.temporary_directory.name) / "users"
        shutil.copytree(storage.USER_DATA_DIRECTORY, temporary_users)
        self.user_data_patch = patch.object(
            storage, "USER_DATA_DIRECTORY", temporary_users
        )
        self.user_data_patch.start()
        self.addCleanup(self.user_data_patch.stop)

    def test_scheduled_workout_opens_and_enables_finish_when_complete(self) -> None:
        _, routine_document = storage.load_data("dev")
        push_routine = next(
            routine
            for routine in routine_document["routines"]
            if routine["id"] == "routine-push-1"
        )
        calendar, _ = schedule_routine(
            empty_calendar_document(),
            local_today(),
            push_routine,
            event_id="scheduled-today",
            created_at="2026-10-20T12:00:00+00:00",
        )
        storage.save_calendar("dev", calendar)
        storage.save_split(
            "dev",
            {
                "schema_version": 1,
                "routine_ids": ["routine-pull-1"],
                "current_index": 0,
            },
            routine_document,
        )

        app = AppTest.from_file(
            Path(__file__).resolve().parent.parent / "app.py",
            default_timeout=10,
        )
        app.session_state["active_user_id"] = "dev"
        app.run()
        self.assertFalse(app.exception)

        finish_button = next(
            button for button in app.button if button.label == "Finish workout"
        )
        self.assertTrue(finish_button.disabled)
        self.assertEqual(
            next(
                selectbox
                for selectbox in app.selectbox
                if selectbox.label == "Select workout"
            ).value,
            "routine-push-1",
        )

        self.assertEqual(len(app.checkbox), 4)
        for checkbox in app.checkbox:
            app.session_state[checkbox.key] = True
        for _ in range(3):
            app.run()
            self.assertFalse(app.exception)
            if any(button.label == "Finish workout" for button in app.button):
                break

        finish_button = next(
            button for button in app.button if button.label == "Finish workout"
        )
        self.assertFalse(finish_button.disabled)

    def test_calendar_page_marks_and_removes_completed_workout(self) -> None:
        exercise_document, routine_document = storage.load_data("dev")
        routine_by_id = {
            routine["id"]: routine for routine in routine_document["routines"]
        }
        calendar, _ = schedule_routine(
            empty_calendar_document(),
            local_today(),
            routine_by_id["routine-push-1"],
            event_id="scheduled-today",
            created_at="2026-10-20T12:00:00+00:00",
        )
        pull_routine = routine_by_id["routine-pull-1"]
        snapshot = new_workout_snapshot(pull_routine, len(pull_routine["slots"]))
        calendar, _ = log_completed_workout(
            calendar,
            local_today(),
            pull_routine,
            snapshot,
            {
                exercise["id"]: exercise
                for exercise in exercise_document["exercises"]
            },
            event_id="completed-today",
            workout_session_id="completed-session",
            completed_at="2026-10-20T13:00:00+00:00",
            source="workout",
        )
        storage.save_calendar("dev", calendar)

        app = AppTest.from_file(
            Path(__file__).resolve().parent.parent / "app.py",
            default_timeout=10,
        )
        app.session_state["active_user_id"] = "dev"
        app.run()
        app.switch_page("pages/calendar.py").run()
        self.assertFalse(app.exception)
        self.assertIn(
            f"{local_today().day} ● ○",
            [button.label for button in app.button],
        )

        app.button(
            key="calendar_remove_event_dev_completed-today"
        ).click().run()
        self.assertFalse(app.exception)
        remaining_events = storage.load_calendar("dev")["events"]
        self.assertEqual(
            [event["id"] for event in remaining_events], ["scheduled-today"]
        )

    def test_split_routine_opens_when_no_calendar_workout_is_scheduled(self) -> None:
        _, routine_document = storage.load_data("dev")
        split = {
            "schema_version": 1,
            "routine_ids": ["routine-push-1", "routine-pull-1"],
            "current_index": 0,
        }
        storage.save_split("dev", split, routine_document)

        app = AppTest.from_file(
            Path(__file__).resolve().parent.parent / "app.py",
            default_timeout=10,
        )
        app.session_state["active_user_id"] = "dev"
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(
            next(
                selectbox
                for selectbox in app.selectbox
                if selectbox.label == "Select workout"
            ).value,
            "routine-push-1",
        )

        app.switch_page("pages/workout_split.py").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.title[0].value, "Workout split")


if __name__ == "__main__":
    unittest.main()
