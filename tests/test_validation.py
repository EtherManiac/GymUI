"""Tests for validation failures that protect stored references."""

import unittest

from workout_app.validation import DataValidationError, validate_all


class ValidationTests(unittest.TestCase):
    """Exercise representative valid and invalid document combinations."""

    def setUp(self) -> None:
        self.exercises = {
            "schema_version": 1,
            "exercises": [
                {"id": "ex-1", "name": "Row", "tags": ["Pull"], "notes": "", "demo_url": ""}
            ],
        }
        self.routines = {
            "schema_version": 1,
            "routines": [
                {
                    "id": "routine-1",
                    "name": "Pull",
                    "slots": [
                        {
                            "id": "slot-1",
                            "order": 1,
                            "required_tags": ["Pull"],
                            "default_exercise_id": "ex-1",
                            "alternative_exercise_ids": [],
                            "sets": "3",
                            "reps": "8-12",
                            "reference_weight": "50 lb",
                            "superset_group_id": None,
                        }
                    ],
                }
            ],
        }

    def test_valid_documents_pass(self) -> None:
        validate_all(self.exercises, self.routines)

    def test_missing_reference_fails(self) -> None:
        self.routines["routines"][0]["slots"][0]["default_exercise_id"] = "missing"
        with self.assertRaisesRegex(DataValidationError, "missing default exercise"):
            validate_all(self.exercises, self.routines)

    def test_duplicate_exercise_id_fails(self) -> None:
        self.exercises["exercises"].append(dict(self.exercises["exercises"][0]))
        with self.assertRaisesRegex(DataValidationError, "duplicated"):
            validate_all(self.exercises, self.routines)


if __name__ == "__main__":
    unittest.main()

