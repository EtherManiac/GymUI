"""Tests for copying profile data without linking the source and target."""

import unittest

from workout_app.sharing import copy_exercise_into_document


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


if __name__ == "__main__":
    unittest.main()
