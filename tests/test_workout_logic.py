"""Tests for shortened workouts, supersets, and session snapshots."""

import random
import unittest

from workout_app.workout_logic import (
    active_group_label,
    is_valid_weight_input,
    move_completed_units_to_end,
    new_workout_snapshot,
    remove_snapshot_slot,
    reorder_snapshot_units,
    select_slots,
    shuffle_snapshot,
    shuffle_snapshot_alternates,
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

    def test_shuffle_alternates_includes_default_with_equal_choice_pool(self) -> None:
        class PickLast:
            def __init__(self) -> None:
                self.pools: list[list[str]] = []

            def choice(self, options: list[str]) -> str:
                self.pools.append(options)
                return options[-1]

        self.routine["slots"][0]["alternative_exercise_ids"] = ["ex-1a", "ex-1b"]
        self.routine["slots"][1]["alternative_exercise_ids"] = []
        self.routine["slots"][2]["alternative_exercise_ids"] = ["ex-3a"]
        self.routine["slots"][3]["alternative_exercise_ids"] = ["ex-4a"]
        snapshot = new_workout_snapshot(self.routine, 4)
        randomizer = PickLast()

        shuffle_snapshot_alternates(snapshot, randomizer)  # type: ignore[arg-type]

        self.assertEqual(
            randomizer.pools,
            [
                ["ex-1", "ex-1a", "ex-1b"],
                ["ex-2"],
                ["ex-3", "ex-3a"],
                ["ex-4", "ex-4a"],
            ],
        )
        self.assertEqual(
            [row["selected_exercise_id"] for row in snapshot],
            ["ex-1b", "ex-2", "ex-3a", "ex-4a"],
        )

    def test_drag_reorder_moves_group_as_one_unit(self) -> None:
        snapshot = new_workout_snapshot(self.routine, 4)

        changed = reorder_snapshot_units(
            snapshot,
            ["slot:four", "group:group-a", "slot:one"],
        )

        self.assertTrue(changed)
        self.assertEqual(
            [row["slot"]["id"] for row in snapshot],
            ["four", "two", "three", "one"],
        )
        self.assertEqual([row["base_position"] for row in snapshot], [0, 1, 2, 3])

    def test_drag_reorder_rejects_incomplete_unit_order(self) -> None:
        snapshot = new_workout_snapshot(self.routine, 4)
        original_ids = [row["slot"]["id"] for row in snapshot]

        self.assertFalse(reorder_snapshot_units(snapshot, ["slot:four"]))
        self.assertEqual([row["slot"]["id"] for row in snapshot], original_ids)

    def test_snapshot_does_not_modify_routine(self) -> None:
        snapshot = new_workout_snapshot(self.routine, 1)
        snapshot[0]["completed"] = True
        self.assertNotIn("completed", self.routine["slots"][0])

    def test_removing_one_snapshot_slot_preserves_other_workout_state(self) -> None:
        snapshot = new_workout_snapshot(self.routine, 4)
        snapshot[0].update(completed=True, weight_used="75")
        snapshot[3]["selected_exercise_id"] = "ex-4a"

        self.assertTrue(remove_snapshot_slot(snapshot, "two"))

        self.assertEqual(
            [row["slot"]["id"] for row in snapshot], ["one", "three", "four"]
        )
        self.assertTrue(snapshot[0]["completed"])
        self.assertEqual(snapshot[0]["weight_used"], "75")
        self.assertEqual(snapshot[2]["selected_exercise_id"], "ex-4a")
        self.assertEqual([row["base_position"] for row in snapshot], [0, 1, 2])

    def test_last_snapshot_slot_cannot_be_removed(self) -> None:
        snapshot = new_workout_snapshot(self.routine, 1)

        self.assertFalse(remove_snapshot_slot(snapshot, "one"))
        self.assertEqual(len(snapshot), 1)

    def test_group_label_uses_remaining_active_members(self) -> None:
        grouped_routine = {
            "slots": [
                {
                    "id": f"group-member-{index}",
                    "order": index,
                    "priority": 1,
                    "default_exercise_id": f"exercise-{index}",
                    "superset_group_id": "group-a",
                }
                for index in range(1, 4)
            ]
        }
        snapshot = new_workout_snapshot(grouped_routine, 3)

        self.assertEqual(active_group_label(len(snapshot)), "Triset")
        self.assertTrue(remove_snapshot_slot(snapshot, "group-member-1"))
        self.assertEqual(active_group_label(len(snapshot)), "Superset")
        self.assertTrue(remove_snapshot_slot(snapshot, "group-member-2"))
        self.assertIsNone(active_group_label(len(snapshot)))

    def test_weight_used_is_session_only_and_follows_its_exercise(self) -> None:
        snapshot = new_workout_snapshot(self.routine, 4)
        snapshot[0]["weight_used"] = "75 lb"
        snapshot[0]["completed"] = True
        move_completed_units_to_end(snapshot)
        self.assertEqual(snapshot[-1]["weight_used"], "75 lb")
        self.assertNotIn("weight_used", self.routine["slots"][0])

    def test_weight_input_accepts_only_optional_positive_numbers(self) -> None:
        for value in ("", "0", "75", "75.5", ".5", "75."):
            self.assertTrue(is_valid_weight_input(value), value)
        for value in ("75 lb", "1.2.3", "-5", ".", " 75"):
            self.assertFalse(is_valid_weight_input(value), value)

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
