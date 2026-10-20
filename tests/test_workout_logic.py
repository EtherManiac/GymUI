"""Tests for shortened workouts, supersets, and session snapshots."""

import random
import unittest

from workout_app.workout_logic import (
    move_completed_units_to_end,
    new_workout_snapshot,
    select_slots,
    shuffle_snapshot,
)


class WorkoutLogicTests(unittest.TestCase):
    """Verify the non-splitting behavior documented for supersets."""

    def setUp(self) -> None:
        self.routine = {
            "slots": [
                {"id": "one", "order": 1, "priority": 1, "default_exercise_id": "ex-1", "superset_group_id": None},
                {"id": "two", "order": 2, "priority": 2, "default_exercise_id": "ex-2", "superset_group_id": "group-a"},
                {"id": "three", "order": 3, "priority": 2, "default_exercise_id": "ex-3", "superset_group_id": "group-a"},
                {"id": "four", "order": 4, "priority": 3, "default_exercise_id": "ex-4", "superset_group_id": None},
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

    def test_priority_is_independent_from_display_order(self) -> None:
        self.routine["slots"][0]["priority"] = 4
        self.routine["slots"][3]["priority"] = 1
        selected = select_slots(self.routine, 3)
        self.assertEqual([slot["id"] for slot in selected], ["two", "three", "four"])

    def test_routine_order_breaks_equal_priority_ties(self) -> None:
        for slot in self.routine["slots"]:
            slot["priority"] = 1
        selected = select_slots(self.routine, 1)
        self.assertEqual([slot["id"] for slot in selected], ["one"])

    def test_completed_single_moves_below_incomplete_units(self) -> None:
        snapshot = new_workout_snapshot(self.routine, 4)
        snapshot[0]["completed"] = True
        self.assertTrue(move_completed_units_to_end(snapshot))
        self.assertEqual(
            [row["slot"]["id"] for row in snapshot], ["two", "three", "four", "one"]
        )

    def test_partial_superset_stays_in_base_position(self) -> None:
        snapshot = new_workout_snapshot(self.routine, 4)
        snapshot[1]["completed"] = True
        self.assertFalse(move_completed_units_to_end(snapshot))
        self.assertEqual(
            [row["slot"]["id"] for row in snapshot], ["one", "two", "three", "four"]
        )

    def test_complete_superset_moves_as_one_unit(self) -> None:
        snapshot = new_workout_snapshot(self.routine, 4)
        snapshot[1]["completed"] = True
        snapshot[2]["completed"] = True
        self.assertTrue(move_completed_units_to_end(snapshot))
        self.assertEqual(
            [row["slot"]["id"] for row in snapshot], ["one", "four", "two", "three"]
        )

    def test_unchecking_restores_base_position(self) -> None:
        snapshot = new_workout_snapshot(self.routine, 4)
        snapshot[0]["completed"] = True
        move_completed_units_to_end(snapshot)
        snapshot[-1]["completed"] = False
        self.assertTrue(move_completed_units_to_end(snapshot))
        self.assertEqual(
            [row["slot"]["id"] for row in snapshot], ["one", "two", "three", "four"]
        )

    def test_lower_priority_group_can_fill_requested_count_exactly(self) -> None:
        """A later triset should replace skipped singles when it produces an exact count."""

        demo_routine = {
            "slots": [
                {
                    "id": "superset-a",
                    "order": 1,
                    "priority": 1,
                    "default_exercise_id": "a",
                    "superset_group_id": "superset",
                },
                {
                    "id": "superset-b",
                    "order": 2,
                    "priority": 1,
                    "default_exercise_id": "b",
                    "superset_group_id": "superset",
                },
                {
                    "id": "single-a",
                    "order": 3,
                    "priority": 2,
                    "default_exercise_id": "c",
                    "superset_group_id": None,
                },
                {
                    "id": "single-b",
                    "order": 4,
                    "priority": 3,
                    "default_exercise_id": "d",
                    "superset_group_id": None,
                },
                {
                    "id": "single-c",
                    "order": 5,
                    "priority": 4,
                    "default_exercise_id": "e",
                    "superset_group_id": None,
                },
                *[
                    {
                        "id": f"triset-{index}",
                        "order": 6 + index,
                        "priority": 5,
                        "default_exercise_id": f"triset-exercise-{index}",
                        "superset_group_id": "triset",
                    }
                    for index in range(3)
                ],
                *[
                    {
                        "id": f"giant-{index}",
                        "order": 9 + index,
                        "priority": 6,
                        "default_exercise_id": f"giant-exercise-{index}",
                        "superset_group_id": "giant-set",
                    }
                    for index in range(4)
                ],
            ]
        }

        selected = select_slots(demo_routine, 6)
        self.assertEqual(len(selected), 6)
        self.assertEqual(
            [slot["id"] for slot in selected],
            ["superset-a", "superset-b", "single-a", "triset-0", "triset-1", "triset-2"],
        )


if __name__ == "__main__":
    unittest.main()
