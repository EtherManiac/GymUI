"""Tests for backward-compatible data upgrades."""

import unittest

from workout_app.migrations import migrate_documents


class MigrationTests(unittest.TestCase):
    def test_mixed_legacy_tags_are_separated(self) -> None:
        exercises = {
            "schema_version": 1,
            "exercises": [{"id": "ex-1", "name": "Press", "tags": ["Push", "Chest", "Compound"]}],
        }
        routines = {
            "schema_version": 1,
            "routines": [{"id": "r-1", "name": "Push", "slots": [{"required_tags": ["Push", "Chest", "Compound"]}]}],
        }

        migrated_exercises, migrated_routines = migrate_documents(exercises, routines)

        self.assertEqual(migrated_exercises["exercises"][0]["muscles_targeted"], ["Chest"])
        self.assertEqual(migrated_exercises["exercises"][0]["tags"], ["Push", "Compound"])
        slot = migrated_routines["routines"][0]["slots"][0]
        self.assertEqual(slot["required_muscles"], ["Chest"])
        self.assertEqual(slot["required_tags"], ["Push", "Compound"])

    def test_current_documents_are_not_reclassified(self) -> None:
        exercises = {
            "exercises": [
                {
                    "muscles_targeted": ["Quadriceps"],
                    "tags": ["Custom"],
                }
            ]
        }
        routines = {"routines": []}
        migrated_exercises, _ = migrate_documents(exercises, routines)
        self.assertEqual(migrated_exercises, exercises)


if __name__ == "__main__":
    unittest.main()
