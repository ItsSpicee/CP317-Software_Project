"""Unit tests for the onboarding, personalization, and nutrition-target backends."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from Application import onboarding, personalize, target_calculations as tc


MALE_PROFILE = {
    "sex": "Male",
    "activity_level": "Medium",
    "height": 180.0,
    "weight": 75.0,
    "age": 26.0,
}


def mifflin(weight, height, age, sex):
    adjustment = {"male": 5, "female": -161}.get(sex, -78)
    return (10 * weight) + (6.25 * height) - (5 * age) + adjustment


def maintenance(weight, height, age, sex, activity):
    factors = {
        "none": 1.2,
        "low": 1.375,
        "medium": 1.55,
        "high": 1.725,
        "extreme": 1.9,
    }
    return mifflin(weight, height, age, sex) * factors[activity]


def baseline_macros(calories, weight):
    protein = min(weight * 1.0, calories * 0.25 / 4)
    fat = calories * 0.30 / 9
    carbs = max(0.0, (calories - protein * 4 - fat * 9) / 4)
    return {"protein": protein, "carbs": carbs, "fat": fat}


def shift_toward(macros, calories, priority, share, cap):
    kcal = {"protein": 4.0, "carbs": 4.0, "fat": 9.0}
    energy = {name: macros[name] * kcal[name] for name in macros}
    other = calories - energy[priority]
    increase = max(0.0, min(calories * share, calories * cap - energy[priority]))
    if other <= 0 or increase <= 0:
        return dict(macros)
    for name in macros:
        if name != priority:
            energy[name] -= increase * energy[name] / other
    energy[priority] += increase
    return {name: energy[name] / kcal[name] for name in macros}


class TempDataCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self._original = []
        for module in (onboarding, personalize, tc):
            self._original.append((module, module.USER_DATA_FOLDER))
            module.USER_DATA_FOLDER = self.folder

    def tearDown(self):
        for module, original in self._original:
            module.USER_DATA_FOLDER = original
        self.tmp.cleanup()

    def write_profile(self, data):
        (self.folder / "user_data.json").write_text(json.dumps(data), encoding="utf-8")

    def write_personalization(self, data):
        (self.folder / "user_personalization_data.json").write_text(
            json.dumps(data), encoding="utf-8"
        )

    def read_json(self, name):
        return json.loads((self.folder / name).read_text(encoding="utf-8"))


class TestOnboardingBackend(TempDataCase):
    def submit(self, form):
        return onboarding.ButtonEvent.submit.fn(None, dict(form))

    def test_metric_profile_is_saved(self):
        self.submit(
            {
                "sex": "Male",
                "activity_level": "Medium",
                "height": "180",
                "height_unit": "cm",
                "weight": "75",
                "weight_unit": "kg",
                "age": "26",
            }
        )
        saved = self.read_json("user_data.json")
        self.assertEqual(saved["sex"], "Male")
        self.assertEqual(saved["activity_level"], "Medium")
        self.assertAlmostEqual(saved["height"], 180.0)
        self.assertAlmostEqual(saved["weight"], 75.0)
        self.assertAlmostEqual(saved["age"], 26.0)
        self.assertNotIn("height_unit", saved)
        self.assertNotIn("weight_unit", saved)

    def test_imperial_values_convert_to_metric(self):
        self.submit(
            {
                "sex": "Female",
                "activity_level": "Low",
                "height": "65",
                "height_unit": "in",
                "weight": "150",
                "weight_unit": "lb",
                "age": "30",
            }
        )
        saved = self.read_json("user_data.json")
        self.assertAlmostEqual(saved["height"], 65 * 2.54)
        self.assertAlmostEqual(saved["weight"], 150 * 0.45359237)

    def test_out_of_range_measurements_are_cleared(self):
        self.submit(
            {
                "sex": "Male",
                "activity_level": "High",
                "height": "10",
                "height_unit": "cm",
                "weight": "900",
                "weight_unit": "kg",
                "age": "5",
            }
        )
        saved = self.read_json("user_data.json")
        self.assertEqual(saved["height"], "")
        self.assertEqual(saved["weight"], "")
        self.assertEqual(saved["age"], "")

    def test_boundary_measurements_are_kept(self):
        self.submit(
            {
                "sex": "Female",
                "activity_level": "None",
                "height": "90",
                "height_unit": "cm",
                "weight": "300",
                "weight_unit": "kg",
                "age": "120",
            }
        )
        saved = self.read_json("user_data.json")
        self.assertAlmostEqual(saved["height"], 90.0)
        self.assertAlmostEqual(saved["weight"], 300.0)
        self.assertAlmostEqual(saved["age"], 120.0)

    def test_blank_submission_does_not_crash(self):
        result = self.submit({})
        saved = self.read_json("user_data.json")
        self.assertEqual(saved["height"], "")
        self.assertEqual(saved["weight"], "")
        self.assertEqual(saved["age"], "")
        self.assertIsNotNone(result)


class TestPersonalizationBackend(TempDataCase):
    def submit(self, form, fiber=30.0, allergies=None, diets=None):
        bag = type("Bag", (), {})()
        bag.fiber = fiber
        bag.allergies = list(allergies or [])
        bag.diet_types = list(diets or [])
        return personalize.PersonalizationState.submit.fn(bag, dict(form))

    def test_choices_are_saved(self):
        self.submit(
            {
                "calories": "2200",
                "priority_macro": "Protein",
                "current_goal": "Weight Loss",
            },
            fiber=35,
            allergies=["Peanuts", "Milk"],
            diets=["Vegetarian"],
        )
        saved = self.read_json("user_personalization_data.json")
        self.assertAlmostEqual(saved["calories"], 2200.0)
        self.assertEqual(saved["priority_macro"], "Protein")
        self.assertEqual(saved["current_goal"], "Weight Loss")
        self.assertEqual(saved["allergies"], ["Peanuts", "Milk"])
        self.assertEqual(saved["diet_types"], ["Vegetarian"])
        self.assertAlmostEqual(saved["fiber"], 35.0)

    def test_calorie_bounds(self):
        self.submit({"calories": "0", "priority_macro": "", "current_goal": ""})
        self.assertAlmostEqual(self.read_json("user_personalization_data.json")["calories"], 0.0)

        self.submit({"calories": "10000"})
        self.assertAlmostEqual(self.read_json("user_personalization_data.json")["calories"], 10000.0)

        self.submit({"calories": "10001"})
        self.assertEqual(self.read_json("user_personalization_data.json")["calories"], "")

        self.submit({"calories": ""})
        self.assertEqual(self.read_json("user_personalization_data.json")["calories"], "")

        self.submit({})
        self.assertEqual(self.read_json("user_personalization_data.json")["calories"], "")

    def test_fiber_is_clamped_before_save(self):
        self.submit({"calories": ""}, fiber=150)
        self.assertAlmostEqual(self.read_json("user_personalization_data.json")["fiber"], 100.0)

        self.submit({"calories": ""}, fiber=-4)
        self.assertAlmostEqual(self.read_json("user_personalization_data.json")["fiber"], 0.0)


class TestNutritionTargets(TempDataCase):
    def test_activity_factors_and_sex_adjustment(self):
        expected = {
            "none": 2100.0,
            "low": 2406.25,
            "medium": 2712.5,
            "high": 3018.75,
            "extreme": 3325.0,
        }
        for activity, calories in expected.items():
            profile = dict(MALE_PROFILE, activity_level=activity)
            self.write_profile(profile)
            self.assertAlmostEqual(tc.calculate_targets(), calories, places=6, msg=activity)
            self.assertAlmostEqual(
                calories,
                maintenance(75, 180, 26, "male", activity),
                places=6,
            )

        self.write_profile(
            {
                "sex": "Female",
                "activity_level": "Low",
                "height": 165,
                "weight": 60,
                "age": 30,
            }
        )
        self.assertAlmostEqual(tc.calculate_targets(), 1815.34375, places=5)

        self.write_profile(
            {
                "sex": "Prefer not to disclose",
                "activity_level": "Low",
                "height": 180,
                "weight": 75,
                "age": 26,
            }
        )
        self.assertAlmostEqual(tc.calculate_targets(), 2292.125, places=5)

    def test_missing_or_invalid_profile_uses_documented_defaults(self):
        self.assertAlmostEqual(tc.AVERAGE_WEIGHT_KG["male"], 199.0 * 0.45359237, places=6)
        self.assertAlmostEqual(tc.AVERAGE_HEIGHT_CM["male"], 68.9 * 2.54, places=6)
        self.assertAlmostEqual(tc.AVERAGE_WEIGHT_KG["female"], 171.8 * 0.45359237, places=6)
        self.assertAlmostEqual(tc.AVERAGE_HEIGHT_CM["female"], 63.5 * 2.54, places=6)

        self.write_profile({"sex": "Male", "activity_level": "Medium"})
        male_default = maintenance(
            tc.AVERAGE_WEIGHT_KG["male"],
            tc.AVERAGE_HEIGHT_CM["male"],
            40,
            "male",
            "medium",
        )
        self.assertAlmostEqual(tc.calculate_targets(), male_default, places=6)

        self.write_profile(
            {
                "sex": "Female",
                "activity_level": "High",
                "height": 10,
                "weight": 1000,
                "age": 2,
            }
        )
        female_default = maintenance(
            tc.AVERAGE_WEIGHT_KG["female"],
            tc.AVERAGE_HEIGHT_CM["female"],
            40,
            "female",
            "high",
        )
        self.assertAlmostEqual(tc.calculate_targets(), female_default, places=6)

        (self.folder / "user_data.json").write_text("{not json", encoding="utf-8")
        fallback = maintenance(tc.DEFAULT_WEIGHT_KG, tc.DEFAULT_HEIGHT_CM, 40, "other", "low")
        self.assertAlmostEqual(tc.calculate_targets(), fallback, places=6)

        (self.folder / "user_data.json").write_text("[1, 2, 3]", encoding="utf-8")
        self.assertAlmostEqual(tc.calculate_targets(), fallback, places=6)

        self.write_profile({"sex": "MALE", "activity_level": "EXTREME", "height": 180, "weight": 75, "age": 26})
        self.assertAlmostEqual(tc.calculate_targets(), 3325.0, places=6)

    def test_baseline_and_priority_macros(self):
        self.write_profile(MALE_PROFILE)
        calories = 2712.5
        expected = baseline_macros(calories, 75)
        actual = tc.calculate_macro_targets(calories, "")
        for name in expected:
            self.assertAlmostEqual(actual[name], expected[name], places=6)

        shifted = tc.calculate_macro_targets(calories, "Protein")
        expected_shift = shift_toward(expected, calories, "protein", 0.10, 0.40)
        for name in expected_shift:
            self.assertAlmostEqual(shifted[name], expected_shift[name], places=6)
        self.assertGreater(shifted["protein"], actual["protein"])
        self.assertAlmostEqual(
            shifted["protein"] * 4 + shifted["carbs"] * 4 + shifted["fat"] * 9,
            calories,
            places=4,
        )
        self.assertLessEqual(shifted["protein"] * 4, calories * 0.40 + 1e-6)

        unrecognized = tc.calculate_macro_targets(calories, "not-a-macro")
        for name in expected:
            self.assertAlmostEqual(unrecognized[name], expected[name], places=6)

    def test_goals_and_manual_calorie_override(self):
        self.write_profile(MALE_PROFILE)
        estimated = 2712.5
        base = baseline_macros(estimated, 75)
        protein_priority = shift_toward(base, estimated, "protein", 0.10, 0.40)

        self.write_personalization(
            {"calories": "", "priority_macro": "", "current_goal": "", "fiber": 30}
        )
        values = tc._get_target_values()
        self.assertAlmostEqual(values["calories"], estimated, places=6)
        self.assertAlmostEqual(values["protein"], base["protein"], places=6)
        self.assertIn("maintenance", values["goal_description"].lower())

        self.write_personalization(
            {"calories": "", "priority_macro": "Protein", "current_goal": "Weight Gain", "fiber": 42}
        )
        values = tc._get_target_values()
        scale = (estimated + 200) / estimated
        self.assertAlmostEqual(values["calories"], estimated + 200, places=6)
        self.assertAlmostEqual(values["protein"], protein_priority["protein"] * scale, places=5)
        self.assertAlmostEqual(values["carbs"], protein_priority["carbs"] * scale, places=5)
        self.assertAlmostEqual(values["fat"], protein_priority["fat"] * scale, places=5)
        self.assertAlmostEqual(values["fiber"], 42.0)

        self.write_personalization(
            {"calories": "", "priority_macro": "", "current_goal": "Weight Loss", "fiber": 0}
        )
        values = tc._get_target_values()
        scale = (estimated - 200) / estimated
        self.assertAlmostEqual(values["calories"], estimated - 200, places=6)
        self.assertAlmostEqual(values["protein"], base["protein"] * scale, places=5)
        self.assertAlmostEqual(values["fiber"], 0.0)

        self.write_personalization(
            {"calories": "", "priority_macro": "Fat", "current_goal": "Main Gain", "fiber": 30}
        )
        values = tc._get_target_values()
        fat_priority = shift_toward(base, estimated, "fat", 0.10, 0.35)
        main_gain = shift_toward(fat_priority, estimated, "protein", 0.05, 0.40)
        self.assertAlmostEqual(values["calories"], estimated, places=6)
        self.assertAlmostEqual(values["protein"], main_gain["protein"], places=5)
        self.assertGreater(values["protein"], fat_priority["protein"])

        self.write_personalization(
            {"calories": 2500, "priority_macro": "", "current_goal": "Weight Gain", "fiber": 30}
        )
        values = tc._get_target_values()
        manual = baseline_macros(2500, 75)
        self.assertAlmostEqual(values["calories"], 2500.0, places=6)
        self.assertAlmostEqual(values["protein"], manual["protein"], places=5)
        self.assertIn("as entered", values["goal_description"].lower())

        self.write_personalization(
            {"calories": 2500, "priority_macro": "", "current_goal": "Main Gain", "fiber": 80}
        )
        values = tc._get_target_values()
        manual_gain = shift_toward(manual, 2500, "protein", 0.05, 0.40)
        self.assertAlmostEqual(values["calories"], 2500.0, places=6)
        self.assertAlmostEqual(values["protein"], manual_gain["protein"], places=5)
        self.assertAlmostEqual(values["fiber"], 80.0)

    def test_invalid_saved_targets_fall_back(self):
        self.write_profile(MALE_PROFILE)
        self.write_personalization(
            {"calories": "nope", "priority_macro": "", "current_goal": "Weight Loss", "fiber": 250}
        )
        values = tc._get_target_values()
        self.assertAlmostEqual(values["calories"], 2712.5 - 200, places=6)
        self.assertAlmostEqual(values["fiber"], 30.0)

        self.write_personalization({"calories": 0, "current_goal": "Weight Gain", "fiber": 100})
        values = tc._get_target_values()
        self.assertAlmostEqual(values["calories"], 0.0)
        self.assertAlmostEqual(values["protein"], 0.0)
        self.assertAlmostEqual(values["carbs"], 0.0)
        self.assertAlmostEqual(values["fat"], 0.0)
        self.assertAlmostEqual(values["fiber"], 100.0)


class TestSavedPrototypeData(unittest.TestCase):
    """Read-only check of the profile currently saved in User Data."""

    def test_current_files_produce_a_complete_target(self):
        values = tc._get_target_values()
        estimated = maintenance(75, 180, 26, "male", "medium")
        self.assertAlmostEqual(values["calories"], estimated, places=6)
        self.assertGreater(values["protein"], 0)
        self.assertGreater(values["carbs"], 0)
        self.assertGreater(values["fat"], 0)
        self.assertAlmostEqual(values["fiber"], 30.0)
        self.assertIn("protein", values["goal_description"].lower())
        energy = values["protein"] * 4 + values["carbs"] * 4 + values["fat"] * 9
        self.assertAlmostEqual(energy, estimated, delta=1.0)


class TestRoutesWired(unittest.TestCase):
    def test_backend_pages_are_registered(self):
        from Application.Application import app

        pages = app._unevaluated_pages
        self.assertEqual(pages["index"].route, "index")
        self.assertEqual(pages["onboarding"].route, "onboarding")
        self.assertEqual(pages["personalize"].route, "personalize")
        self.assertEqual(pages["targets"].route, "targets")
        self.assertIs(
            pages["personalize"].on_load.fn,
            personalize.PersonalizationState.load_saved_fiber.fn,
        )
        self.assertIs(
            pages["targets"].on_load.fn,
            tc.TargetState.load_targets.fn,
        )


if __name__ == "__main__":
    unittest.main()
