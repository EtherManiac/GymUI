"""Tests for the repeating workout split transitions."""

from __future__ import annotations

import unittest

from workout_app.split_logic import (
    advance_split,
    current_split_routine_id,
    without_routine,
)


class SplitLogicTests(unittest.TestCase):
    def setUp(self) -> None:
        self.split = {
            "schema_version": 1,
            "routine_ids": ["push", "pull", "legs"],
            "current_index": 1,
        }

    def test_matching_completion_advances_and_wraps(self) -> None:
        advanced, did_advance = advance_split(self.split, "pull")
        wrapped, did_wrap = advance_split(
            {**self.split, "current_index": 2}, "legs"
        )

        self.assertTrue(did_advance)
        self.assertEqual(current_split_routine_id(advanced), "legs")
        self.assertTrue(did_wrap)
        self.assertEqual(current_split_routine_id(wrapped), "push")
        self.assertEqual(self.split["current_index"], 1)

    def test_out_of_order_completion_reanchors_the_cycle(self) -> None:
        updated, did_advance = advance_split(self.split, "legs")

        self.assertTrue(did_advance)
        self.assertEqual(current_split_routine_id(updated), "push")

    def test_routine_outside_split_does_not_change_position(self) -> None:
        unchanged, did_advance = advance_split(self.split, "cardio")

        self.assertFalse(did_advance)
        self.assertEqual(unchanged, self.split)

    def test_repeated_routine_uses_next_occurrence_from_current_position(self) -> None:
        updated, did_advance = advance_split(
            {
                "schema_version": 1,
                "routine_ids": ["push", "pull", "push", "legs"],
                "current_index": 1,
            },
            "push",
        )

        self.assertTrue(did_advance)
        self.assertEqual(current_split_routine_id(updated), "legs")

    def test_deleted_routine_is_removed_from_every_slot(self) -> None:
        updated = without_routine(
            {
                "schema_version": 1,
                "routine_ids": ["push", "pull", "push", "legs"],
                "current_index": 2,
            },
            "push",
        )

        self.assertEqual(updated["routine_ids"], ["pull", "legs"])
        self.assertEqual(updated["current_index"], 0)


if __name__ == "__main__":
    unittest.main()
