import sys
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

APP_ROOT = Path(__file__).resolve().parents[1]

if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from Application import onboarding, personalize, target_calculations as tc


# ============================================================
# ADDITIONAL ONBOARDING TESTS
# ============================================================

class TestAdditionalOnboarding(unittest.TestCase):

    def setUp(self):
        # Create a temporary folder so tests do not change the
        # application's actual saved user data.
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)

        self.original_folder = onboarding.USER_DATA_FOLDER
        onboarding.USER_DATA_FOLDER = self.folder

    def tearDown(self):
        # Restore the original data folder after each test.
        onboarding.USER_DATA_FOLDER = self.original_folder
        self.tmp.cleanup()

    # Tests whether non-numeric height, weight, and age values
    # are rejected and saved as blank values.
    def test_non_numeric_measurements_are_cleared(self):
        onboarding.ButtonEvent.submit.fn(
            None,
            {
                "sex": "Female",
                "activity_level": "Medium",
                "height": "abc",
                "height_unit": "cm",
                "weight": "hello",
                "weight_unit": "kg",
                "age": "twenty",
            },
        )

        saved = json.loads(
            (self.folder / "user_data.json").read_text(encoding="utf-8")
        )

        self.assertEqual(saved["height"], "")
        self.assertEqual(saved["weight"], "")
        self.assertEqual(saved["age"], "")

    # Tests whether the application accepts valid measurements
    # while clearing an invalid measurement in the same submission.
    def test_valid_and_invalid_measurements(self):
        onboarding.ButtonEvent.submit.fn(
            None,
            {
                "sex": "Female",
                "activity_level": "Medium",
                "height": "175",
                "height_unit": "cm",
                "weight": "500",
                "weight_unit": "kg",
                "age": "20",
            },
        )

        saved = json.loads(
            (self.folder / "user_data.json").read_text(encoding="utf-8")
        )

        self.assertAlmostEqual(saved["height"], 175.0)
        self.assertEqual(saved["weight"], "")
        self.assertAlmostEqual(saved["age"], 20.0)

    # Tests whether an imperial height below the permitted metric
    # range is rejected after conversion from inches to centimetres.
    def test_imperial_height_below_valid_range_is_cleared(self):
        onboarding.ButtonEvent.submit.fn(
            None,
            {
                "sex": "Female",
                "activity_level": "Medium",
                "height": "30",
                "height_unit": "in",
                "weight": "60",
                "weight_unit": "kg",
                "age": "20",
            },
        )

        saved = json.loads(
            (self.folder / "user_data.json").read_text(encoding="utf-8")
        )

        self.assertEqual(saved["height"], "")
        self.assertEqual(saved["weight"], 60.0)

    # Tests whether an imperial weight above the permitted metric
    # range is rejected after conversion from pounds to kilograms.
    def test_imperial_weight_above_valid_range_is_cleared(self):
        onboarding.ButtonEvent.submit.fn(
            None,
            {
                "sex": "Male",
                "activity_level": "Medium",
                "height": "180",
                "height_unit": "cm",
                "weight": "700",
                "weight_unit": "lb",
                "age": "25",
            },
        )

        saved = json.loads(
            (self.folder / "user_data.json").read_text(encoding="utf-8")
        )

        self.assertAlmostEqual(saved["height"], 180.0)
        self.assertEqual(saved["weight"], "")

    # Tests whether a missing height is cleared while valid
    # weight and age values are still saved correctly.
    def test_missing_height_with_valid_weight_and_age(self):
        onboarding.ButtonEvent.submit.fn(
            None,
            {
                "sex": "Male",
                "activity_level": "Low",
                "height": "",
                "height_unit": "cm",
                "weight": "70",
                "weight_unit": "kg",
                "age": "22",
            },
        )

        saved = json.loads(
            (self.folder / "user_data.json").read_text(encoding="utf-8")
        )

        self.assertEqual(saved["height"], "")
        self.assertAlmostEqual(saved["weight"], 70.0)
        self.assertAlmostEqual(saved["age"], 22.0)


# ============================================================
# ADDITIONAL PERSONALIZATION TESTS
# ============================================================

class TestAdditionalPersonalization(unittest.TestCase):

    def setUp(self):
        # Use temporary storage so the tests do not overwrite
        # the application's actual personalization data.
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)

        self.original_folder = personalize.USER_DATA_FOLDER
        personalize.USER_DATA_FOLDER = self.folder

    def tearDown(self):
        # Restore the original folder after each test.
        personalize.USER_DATA_FOLDER = self.original_folder
        self.tmp.cleanup()

    # Tests whether a negative calorie target is rejected
    # by the actual personalization submission handler.
    def test_negative_calories_are_cleared(self):
        state = SimpleNamespace(
            allergies=[],
            diet_types=[],
            fiber=30.0
        )

        personalize.PersonalizationState.submit.fn(
            state,
            {
                "calories": "-500",
                "priority_macro": "Protein",
                "current_goal": "Weight Gain",
            },
        )

        saved = json.loads(
            (self.folder / "user_personalization_data.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(saved["calories"], "")

    # Tests whether a calorie target above 10,000 is rejected.
    def test_calories_above_maximum_are_cleared(self):
        state = SimpleNamespace(
            allergies=[],
            diet_types=[],
            fiber=30.0
        )
        personalize.PersonalizationState.submit.fn(
            state,
            {
                "calories": "12000",
                "priority_macro": "Protein",
                "current_goal": "Weight Gain",
            },
        )

        saved = json.loads(
            (self.folder / "user_personalization_data.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(saved["calories"], "")

    # Tests whether the minimum permitted calorie value of zero
    # is accepted and saved.
    def test_zero_calories_are_accepted(self):
        state = SimpleNamespace(
            allergies=[],
            diet_types=[],
            fiber=30.0
        )

        personalize.PersonalizationState.submit.fn(
            state,
            {
                "calories": "0",
                "priority_macro": "Protein",
                "current_goal": "Weight Gain",
            },
        )

        saved = json.loads(
            (self.folder / "user_personalization_data.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(saved["calories"], 0.0)

    # Tests whether the maximum permitted calorie value of 10,000
    # is accepted and saved.
    def test_maximum_calories_are_accepted(self):
        state = SimpleNamespace(
            allergies=[],
            diet_types=[],
            fiber=30.0
        )

        personalize.PersonalizationState.submit.fn(
            state,
            {
                "calories": "10000",
                "priority_macro": "Protein",
                "current_goal": "Weight Gain",
            },
        )

        saved = json.loads(
            (self.folder / "user_personalization_data.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(saved["calories"], 10000.0)

    # Tests whether selected allergies and diet preferences
    # are saved in the personalization JSON file.
    def test_allergies_and_diet_preferences_are_saved(self):
        state = SimpleNamespace(
            allergies=[],
            diet_types=[],
            fiber=30.0
        )
        state.allergies = ["Peanuts", "Milk"]
        state.diet_types = ["Vegetarian", "Gluten Free"]

        personalize.PersonalizationState.submit.fn(
            state,
            {
                "calories": "",
                "priority_macro": "Protein",
                "current_goal": "Weight Gain",
            },
        )

        saved = json.loads(
            (self.folder / "user_personalization_data.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(saved["allergies"], ["Peanuts", "Milk"])
        self.assertEqual(
            saved["diet_types"],
            ["Vegetarian", "Gluten Free"]
        )

    # Tests whether the application's available allergy and
    # diet options include the expected choices.
    def test_allergy_and_diet_options_are_defined(self):
        self.assertIn("Peanuts", personalize.FOOD_ALLERGIES)
        self.assertIn("Milk", personalize.FOOD_ALLERGIES)
        self.assertIn("Vegetarian", personalize.DIETS)
        self.assertIn("Vegan", personalize.DIETS)
        self.assertIn("Keto", personalize.DIETS)

    # Tests whether a saved fibre value is loaded correctly.
    def test_saved_fiber_is_loaded(self):
        with open(
            self.folder / "user_personalization_data.json",
            "w",
            encoding="utf-8",
        ) as f:
            json.dump({"fiber": 45}, f)

        state = SimpleNamespace(
            allergies=[],
            diet_types=[],
            fiber=30.0
        )
        personalize.PersonalizationState.load_saved_fiber.fn(state)

        self.assertEqual(state.fiber, 45.0)


# ============================================================
# ADDITIONAL NUTRITION CALCULATION TESTS
# ============================================================

class TestAdditionalNutritionCalculations(unittest.TestCase):

    def setUp(self):
        # Create temporary user data for testing nutrition calculations.
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)

        self.original_folder = tc.USER_DATA_FOLDER
        tc.USER_DATA_FOLDER = self.folder

    def tearDown(self):
        # Restore the original user data folder.
        tc.USER_DATA_FOLDER = self.original_folder
        self.tmp.cleanup()

    # Helper function that saves a test profile to the temporary folder.
    def write_profile(self, data):
        with open(
            self.folder / "user_data.json",
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(data, f)

    # Tests whether an invalid activity level falls back to
    # the application's default activity multiplier.
    def test_invalid_activity_level_uses_default(self):
        self.write_profile({
            "sex": "Female",
            "weight": 65,
            "height": 165,
            "age": 25,
            "activity_level": "Invalid",
        })

        result = tc.calculate_targets()

        self.write_profile({
            "sex": "Female",
            "weight": 65,
            "height": 165,
            "age": 25,
            "activity_level": "Low",
        })

        expected = tc.calculate_targets()

        self.assertAlmostEqual(result, expected)

    # Tests whether an invalid weight of zero is replaced
    # with the default weight for the user's sex.
    def test_zero_weight_uses_default(self):
        self.write_profile({
            "sex": "Male",
            "weight": 0,
            "height": 180,
            "age": 25,
            "activity_level": "Medium",
        })

        result = tc.calculate_targets()

        self.write_profile({
            "sex": "Male",
            "height": 180,
            "age": 25,
            "activity_level": "Medium",
        })

        expected = tc.calculate_targets()

        self.assertAlmostEqual(result, expected)

    # Tests whether the calories from protein, carbohydrates,
    # and fat add up to the specified calorie target.
    def test_macro_calories_add_up_to_total(self):
        self.write_profile({
            "sex": "Female",
            "weight": 65,
            "height": 165,
            "age": 25,
            "activity_level": "Medium",
        })

        calories = 2000
        macros = tc.calculate_macro_targets(calories)

        calculated_calories = (
            macros["protein"] * 4
            + macros["carbs"] * 4
            + macros["fat"] * 9
        )

        self.assertAlmostEqual(calculated_calories, calories)

    # Tests whether a zero-calorie target produces zero grams
    # of protein, carbohydrates, and fat.
    def test_zero_calories_produces_zero_macros(self):
        self.write_profile({
            "sex": "Female",
            "weight": 65,
        })

        macros = tc.calculate_macro_targets(0)

        self.assertEqual(macros["protein"], 0)
        self.assertEqual(macros["carbs"], 0)
        self.assertEqual(macros["fat"], 0)

    # Tests whether selecting protein as the priority macro
    # increases its calorie contribution compared with the baseline.
    def test_priority_macro_increases_protein_share(self):
        self.write_profile({
            "sex": "Female",
            "weight": 65,
        })

        baseline = tc.calculate_macro_targets(2000)
        priority = tc.calculate_macro_targets(2000, "Protein")

        baseline_protein_calories = baseline["protein"] * 4
        priority_protein_calories = priority["protein"] * 4

        self.assertGreater(
            priority_protein_calories,
            baseline_protein_calories,
        )


# ============================================================
# RUN TESTS
# ============================================================

if __name__ == "__main__":
    unittest.main()