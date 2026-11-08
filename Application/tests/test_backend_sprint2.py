"""Sprint 2 regressions for reusable targets and preference persistence."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from Application import get_targets as nutrition
from Application import personalize


MALE_PROFILE = {
    "sex": "Male",
    "activity_level": "Medium",
    "height": 180.0,
    "weight": 75.0,
    "age": 26.0,
}


class TempDataCase(unittest.TestCase):
    def setUp(self):
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        for module in (personalize, nutrition):
            self.enterContext(patch.object(module, "USER_DATA_FOLDER", self.folder))

    def write_profile(self, data):
        (self.folder / "user_data.json").write_text(json.dumps(data), encoding="utf-8")

    def write_personalization(self, data):
        (self.folder / "user_personalization_data.json").write_text(
            json.dumps(data), encoding="utf-8"
        )

    def read_json(self, name):
        return json.loads((self.folder / name).read_text(encoding="utf-8"))


class TestPersonalizationPersistence(TempDataCase):
    def test_saved_allergies_and_diets_survive_revisit_and_resubmit(self):
        self.write_personalization({
            "fiber": 35,
            "allergies": ["Milk", "Peanuts"],
            "diet_types": ["Vegetarian", "Gluten Free"],
        })
        state = SimpleNamespace(allergies=[], diet_types=[])
        personalize.PersonalizationState.load_saved_preferences.fn(state)
        self.assertEqual(state.allergies, ["Milk", "Peanuts"])
        self.assertEqual(state.diet_types, ["Vegetarian", "Gluten Free"])

        personalize.PersonalizationState.submit.fn(state, {"calories": ""})
        saved = self.read_json("user_personalization_data.json")
        self.assertEqual(saved["allergies"], ["Milk", "Peanuts"])
        self.assertEqual(saved["diet_types"], ["Vegetarian", "Gluten Free"])

        personalize.PersonalizationState.toggle_allergy.fn(state, "Milk", False)
        personalize.PersonalizationState.toggle_diet.fn(state, "Gluten Free", False)
        personalize.PersonalizationState.submit.fn(state, {"calories": ""})
        personalize.PersonalizationState.load_saved_preferences.fn(state)
        self.assertEqual(state.allergies, ["Peanuts"])
        self.assertEqual(state.diet_types, ["Vegetarian"])

    def test_invalid_fiber_does_not_discard_saved_restrictions(self):
        for fiber in ("invalid", None, float("nan"), float("inf")):
            with self.subTest(fiber=fiber):
                self.write_personalization({
                    "fiber": fiber,
                    "muscle_gain": True,
                    "allergies": ["Milk"],
                    "diet_types": ["Vegan"],
                })
                state = SimpleNamespace()
                personalize.PersonalizationState.load_saved_preferences.fn(state)
                self.assertEqual(state.fiber, 30)
                self.assertTrue(state.muscle_gain)
                self.assertEqual(state.allergies, ["Milk"])
                self.assertEqual(state.diet_types, ["Vegan"])

    def test_malformed_choice_lists_are_not_treated_as_selections(self):
        for allergies, diets in (("Milk", {"Vegan": True}), (None, 10)):
            with self.subTest(allergies=allergies, diets=diets):
                self.write_personalization({"allergies": allergies, "diet_types": diets})
                state = SimpleNamespace(allergies=["Milk"], diet_types=["Vegan"])
                personalize.PersonalizationState.load_saved_preferences.fn(state)
                self.assertEqual(state.allergies, [])
                self.assertEqual(state.diet_types, [])

    def test_missing_or_corrupt_preferences_reset_stale_state(self):
        path = self.folder / "user_personalization_data.json"
        for contents in (None, "{invalid", "[]", "{}"):
            with self.subTest(contents=contents):
                if contents is not None:
                    path.write_text(contents, encoding="utf-8")
                state = SimpleNamespace(
                    fiber=55, muscle_gain=True, allergies=["Milk"], diet_types=["Vegan"]
                )
                personalize.PersonalizationState.load_saved_preferences.fn(state)
                self.assertEqual(state.fiber, 30)
                self.assertFalse(state.muscle_gain)
                self.assertEqual(state.allergies, [])
                self.assertEqual(state.diet_types, [])


class TestGetTargets(TempDataCase):
    def test_get_targets_accepts_explicit_data_without_reading_files(self):
        personalization = {"calories": 2500, "muscle_gain": True, "fiber": 42}
        with patch.object(nutrition, "_load_json", side_effect=AssertionError("Unexpected file read")):
            values = nutrition.get_targets(dict(MALE_PROFILE), personalization)
            defaults = nutrition.get_targets({}, {})
        self.assertEqual(values["calories"], 2500)
        self.assertEqual(values["fiber"], 42)
        self.assertTrue(values["has_manual_target"])
        self.assertGreater(values["protein"], 75)
        self.assertAlmostEqual(
            values["protein"] * 4 + values["carbs"] * 4 + values["fat"] * 9, 2500
        )
        self.assertFalse(defaults["has_manual_target"])
        self.assertEqual(defaults["fiber"], 30)

    def test_get_targets_loads_each_saved_file_once(self):
        personalization = {"calories": 2200, "fiber": 35}
        self.write_profile(MALE_PROFILE)
        self.write_personalization(personalization)
        with patch.object(nutrition, "_load_json", wraps=nutrition._load_json) as loader:
            values = nutrition.get_targets()
        self.assertEqual(loader.call_count, 2)
        self.assertEqual(values, nutrition.get_targets(MALE_PROFILE, personalization))


if __name__ == "__main__":
    unittest.main()
