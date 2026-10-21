"""Tests for profile-scoped persistence and workout recovery drafts."""

from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from workout_app import storage
from workout_app.workout_logic import new_workout_snapshot


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

        expired = storage.load_workout_draft(
            "dev",
            routines,
            now=datetime.now(UTC) + timedelta(hours=13),
        )
        self.assertIsNone(expired)
        self.assertFalse((Path(self.temporary_directory.name) / "dev" / "active_workout.json").exists())


if __name__ == "__main__":
    unittest.main()
