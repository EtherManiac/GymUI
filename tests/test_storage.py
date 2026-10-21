"""Tests for profile-scoped persistence and workout recovery drafts."""

from __future__ import annotations

import tempfile
import unittest
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from workout_app import storage
from workout_app.workout_logic import new_workout_snapshot
from workout_app.calendar_logic import empty_calendar_document
from workout_app.split_logic import empty_split_document


class ProfileStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.user_data_patch = patch.object(
            storage,
            "USER_DATA_DIRECTORY",
            Path(self.temporary_directory.name),
        )
        self.user_data_patch.start()
        self.addCleanup(self.user_data_patch.stop)

        self.empty_exercises = {"schema_version": 1, "exercises": []}
        self.empty_routines = {"schema_version": 1, "routines": []}

    def test_profile_data_is_isolated(self) -> None:
        tyler_exercises = {
            "schema_version": 1,
            "exercises": [
                {
                    "id": "row",
                    "name": "Row",
                    "muscles_targeted": ["Back"],
                    "tags": [],
                    "notes": "",
                    "demo_url": "",
                }
            ],
        }
        storage.save_data("tyler", tyler_exercises, self.empty_routines)
        storage.save_data("mia", self.empty_exercises, self.empty_routines)

        loaded_tyler, _ = storage.load_data("tyler")
        loaded_mia, _ = storage.load_data("mia")

        self.assertEqual(loaded_tyler["exercises"][0]["name"], "Row")
        self.assertEqual(loaded_mia["exercises"], [])

    def test_recent_workout_draft_restores_and_then_expires(self) -> None:
        routine = {
            "id": "routine-1",
            "name": "Test workout",
            "slots": [
                {
                    "id": "slot-1",
                    "order": 1,
                    "priority": 1,
                    "required_muscles": ["Back"],
                    "required_tags": [],
                    "default_exercise_id": "row",
                    "alternative_exercise_ids": [],
                    "sets": "3",
                    "reps": "8",
                    "reference_weight": "50 lb",
                    "superset_group_id": None,
                }
            ],
        }
        routines = {"schema_version": 1, "routines": [routine]}
        snapshot = new_workout_snapshot(routine, 1)
        snapshot[0].update(completed=True, weight_used="55.5")
        storage.save_workout_draft("dev", "routine-1", 1, snapshot)

        restored = storage.load_workout_draft("dev", routines)

        self.assertIsNotNone(restored)
        self.assertTrue(restored["snapshot"][0]["completed"])
        self.assertEqual(restored["snapshot"][0]["weight_used"], "55.5")
        self.assertTrue(restored["workout_session_id"])
        self.assertTrue(restored["started_at"])

        expired = storage.load_workout_draft(
            "dev",
            routines,
            now=datetime.now(timezone.utc) + timedelta(hours=13),
        )
        self.assertIsNone(expired)
        self.assertFalse((Path(self.temporary_directory.name) / "dev" / "active_workout.json").exists())

    def test_calendar_is_profile_scoped_and_included_in_backups(self) -> None:
        calendar = {
            "schema_version": 1,
            "events": [
                {
                    "id": "scheduled",
                    "date": "2026-10-21",
                    "status": "scheduled",
                    "routine_id": "routine-1",
                    "routine_name": "Test workout",
                    "created_at": "2026-10-20T12:00:00+00:00",
                }
            ],
        }
        storage.save_calendar("tyler", calendar)

        self.assertEqual(storage.load_calendar("tyler"), calendar)
        self.assertEqual(storage.load_calendar("mia"), empty_calendar_document())

        split = empty_split_document()
        raw_bundle = storage.data_bundle_json(
            self.empty_exercises, self.empty_routines, calendar, split
        ).encode("utf-8")
        exercises, routines, restored_calendar, restored_split = (
            storage.parse_data_bundle(raw_bundle)
        )
        self.assertEqual(exercises, self.empty_exercises)
        self.assertEqual(routines, self.empty_routines)
        self.assertEqual(restored_calendar, calendar)
        self.assertEqual(restored_split, split)

    def test_version_one_backup_restores_with_an_empty_calendar(self) -> None:
        raw_bundle = json.dumps(
            {
                "bundle_version": 1,
                "exercises": self.empty_exercises,
                "routines": self.empty_routines,
            }
        ).encode("utf-8")

        _, _, calendar, split = storage.parse_data_bundle(raw_bundle)

        self.assertEqual(calendar, empty_calendar_document())
        self.assertEqual(split, empty_split_document())

    def test_split_is_profile_scoped(self) -> None:
        routines = {
            "schema_version": 1,
            "routines": [
                {"id": "push", "name": "Push", "slots": []},
                {"id": "pull", "name": "Pull", "slots": []},
            ],
        }
        split = {
            "schema_version": 1,
            "routine_ids": ["push", "pull"],
            "current_index": 1,
        }

        storage.save_split("tyler", split, routines)

        self.assertEqual(storage.load_split("tyler", routines), split)
        self.assertEqual(storage.load_split("mia", routines), empty_split_document())


if __name__ == "__main__":
    unittest.main()
