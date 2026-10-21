"""Tests for copying profile data without linking the source and target."""

import unittest

from workout_app.sharing import (
    copy_exercise_into_document,
    copy_routine_into_documents,
    missing_routine_exercises,
)


class SharingTests(unittest.TestCase):
    def test_imported_exercise_gets_new_id_and_is_independent(self) -> None:
        target = {"schema_version": 1, "exercises": []}
        source = {
            "id": "source-id",
            "name": "Cable row",
            "muscles_targeted": ["Back"],
            "tags": ["Pull"],
            "notes": "Control the return.",
            "demo_url": "",
        }

        updated = copy_exercise_into_document(target, source, "imported-id")

        self.assertEqual(target["exercises"], [])
        self.assertEqual(source["id"], "source-id")
        self.assertEqual(updated["exercises"][0]["id"], "imported-id")
        updated["exercises"][0]["tags"].append("Imported")
        self.assertEqual(source["tags"], ["Pull"])

    def test_routine_import_reuses_only_full_exercise_matches(self) -> None:
        exact_target = self._exercise("target-exact", "Cable row", notes="Same")
        same_name_target = self._exercise("target-name-only", "Curl", notes="Old")
        source_exact = self._exercise("source-exact", "Cable row", notes="Same")
        source_changed = self._exercise("source-changed", "Curl", notes="New")
        target_exercises = {
            "schema_version": 1,
            "exercises": [exact_target, same_name_target],
        }
        source_exercises = {
            "schema_version": 1,
            "exercises": [source_exact, source_changed],
        }
        source_routine = self._routine("source-exact", "source-changed")

        missing = missing_routine_exercises(
            target_exercises, source_exercises, source_routine
        )

        self.assertEqual([exercise["id"] for exercise in missing], ["source-changed"])

    def test_routine_import_copies_dependencies_and_remaps_all_ids(self) -> None:
        target_exercises = {
            "schema_version": 1,
            "exercises": [self._exercise("target-exact", "Cable row", notes="Same")],
        }
        target_routines = {"schema_version": 1, "routines": []}
        source_exercises = {
            "schema_version": 1,
            "exercises": [
                self._exercise("source-exact", "Cable row", notes="Same"),
                self._exercise("source-new", "Curl", notes="Different"),
                self._exercise("unused", "Squat"),
            ],
        }
        source_routine = self._routine("source-exact", "source-new")
        ids = iter(["new-exercise", "new-routine", "new-slot-1", "new-group", "new-slot-2"])

        updated_exercises, updated_routines, imported_routine_id = (
            copy_routine_into_documents(
                target_exercises,
                target_routines,
                source_exercises,
                source_routine,
                lambda: next(ids),
            )
        )

        self.assertEqual(imported_routine_id, "new-routine")
        self.assertEqual(
            [exercise["id"] for exercise in updated_exercises["exercises"]],
            ["target-exact", "new-exercise"],
        )
        imported = updated_routines["routines"][0]
        self.assertEqual(imported["id"], "new-routine")
        self.assertEqual(imported["slots"][0]["id"], "new-slot-1")
        self.assertEqual(imported["slots"][1]["id"], "new-slot-2")
        self.assertEqual(
            imported["slots"][0]["default_exercise_id"], "target-exact"
        )
        self.assertEqual(
            imported["slots"][0]["alternative_exercise_ids"], ["new-exercise"]
        )
        self.assertEqual(
            imported["slots"][1]["default_exercise_id"], "new-exercise"
        )
        self.assertEqual(
            imported["slots"][0]["superset_group_id"], "new-group"
        )
        self.assertEqual(
            imported["slots"][1]["superset_group_id"], "new-group"
        )
        self.assertEqual(target_exercises["exercises"][0]["id"], "target-exact")
        self.assertEqual(target_routines["routines"], [])

    @staticmethod
    def _exercise(
        exercise_id: str, name: str, *, notes: str = ""
    ) -> dict[str, object]:
        return {
            "id": exercise_id,
            "name": name,
            "muscles_targeted": ["Back"],
            "tags": ["Pull"],
            "notes": notes,
            "demo_url": "",
        }

    @staticmethod
    def _routine(default_id: str, alternate_id: str) -> dict[str, object]:
        return {
            "id": "source-routine",
            "name": "Imported day",
            "slots": [
                {
                    "id": "source-slot-1",
                    "order": 1,
                    "priority": 1,
                    "required_muscles": ["Back"],
                    "required_tags": ["Pull"],
                    "default_exercise_id": default_id,
                    "alternative_exercise_ids": [alternate_id],
                    "sets": "3",
                    "reps": "8-12",
                    "reference_weight": "100 lb",
                    "superset_group_id": "source-group",
                },
                {
                    "id": "source-slot-2",
                    "order": 2,
                    "priority": 1,
                    "required_muscles": ["Back"],
                    "required_tags": [],
                    "default_exercise_id": alternate_id,
                    "alternative_exercise_ids": [],
                    "sets": "3",
                    "reps": "10",
                    "reference_weight": "20 lb",
                    "superset_group_id": "source-group",
                },
            ],
        }


if __name__ == "__main__":
    unittest.main()
