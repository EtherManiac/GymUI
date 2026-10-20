"""Tests for shortened workouts, supersets, and session snapshots."""

import random
import unittest

from workout_app.workout_logic import new_workout_snapshot, select_slots, shuffle_snapshot


class WorkoutLogicTests(unittest.TestCase):
    """Verify the non-splitting behavior documented for supersets."""

    def setUp(self) -> None:
        self.routine = {
            "slots": [
                {"id": "one", "order": 1, "default_exercise_id": "ex-1", "superset_group_id": None},
                {"id": "two", "order": 2, "default_exercise_id": "ex-2", "superset_group_id": "group-a"},
                {"id": "three", "order": 3, "default_exercise_id": "ex-3", "superset_group_id": "group-a"},
                {"id": "four", "order": 4, "default_exercise_id": "ex-4", "superset_group_id": None},
            ]
        }

    def test_short_selection_skips_oversized_superset(self) -> None:
        selected = select_slots(self.routine, 2)
        self.assertEqual([slot["id"] for slot in selected], ["one", "four"])

    def test_selection_includes_complete_superset(self) -> None:
        selected = select_slots(self.routine, 3)
        self.assertEqual([slot["id"] for slot in selected], ["one", "two", "three"])

    def test_shuffle_keeps_superset_adjacent(self) -> None:
        snapshot = new_workout_snapshot(self.routine, 4)
        shuffle_snapshot(snapshot, random.Random(4))
        identifiers = [row["slot"]["id"] for row in snapshot]
        self.assertEqual(abs(identifiers.index("two") - identifiers.index("three")), 1)

    def test_snapshot_does_not_modify_routine(self) -> None:
        snapshot = new_workout_snapshot(self.routine, 1)
        snapshot[0]["completed"] = True
        self.assertNotIn("completed", self.routine["slots"][0])


if __name__ == "__main__":
    unittest.main()

