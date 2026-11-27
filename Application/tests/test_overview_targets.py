"""Overview and Targets agree when setup is skipped or preferences change."""

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from Application import get_targets, grocery_planner, inventory, meal_planner
from Application.home import OverviewState
from Application.intake import MacroIntakeState
from Application.target_calculations import TargetState


class OverviewTargetTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        for module in (get_targets, grocery_planner, meal_planner):
            patcher = patch.object(module, "USER_DATA_FOLDER", self.folder)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.object(inventory, "INVENTORY_FILE", self.folder / "inventory.json")
        patcher.start()
        self.addCleanup(patcher.stop)

    def screens(self):
        targets = SimpleNamespace()
        intake = SimpleNamespace(rx_router_session=SimpleNamespace(client_token="test"))
        overview = SimpleNamespace(rx_router_session=SimpleNamespace(client_token="test"))
        TargetState.load_targets.fn(targets)
        MacroIntakeState.load_intake.fn(intake)
        OverviewState.load_overview.fn(overview)
        return targets, intake, overview

    def assert_matching_empty_day(self):
        targets, intake, overview = self.screens()
        self.assertEqual(intake.calorie_goal, targets.calories)
        self.assertEqual(intake.calorie_left, f"{targets.calories} kcal left")
        self.assertIn(targets.calories, overview.intent_line)
        for nutrient in ("protein", "carbs", "fat", "fiber"):
            amount = getattr(targets, nutrient)
            self.assertEqual(getattr(intake, f"{nutrient}_left"), f"{amount} left")
            self.assertEqual(getattr(intake, f"{nutrient}_figure"), f"0 / {amount}")
            self.assertEqual(getattr(intake, f"{nutrient}_progress"), "0.0000")
        return targets, intake, overview

    def test_missing_profile_and_preferences_use_same_fallbacks(self):
        targets, intake, overview = self.assert_matching_empty_day()
        self.assertGreater(float(targets.calories.replace(",", "")), 0)
        self.assertEqual(targets.fiber, "30 g")
        self.assertEqual(overview.welcome, "Welcome")
        self.assertFalse(overview.has_chips)

    def test_purchased_list_is_hidden_and_new_list_appears(self):
        response = {"items": [{
            "name": "Rice", "quantity_g": 100, "grocery_type": "dry_goods",
            "preparation": "Cook rice.", "calories": 350, "protein": 7,
            "carbs": 80, "fat": 1, "fiber": 2,
        }], "notes": ""}
        first = grocery_planner._save_suggestion(response, [], "test")
        _, _, overview = self.screens()
        self.assertTrue(overview.has_grocery)
        self.assertEqual(overview.grocery_counts["dry_goods"], 1)
        self.assertFalse(overview.has_inventory)

        grocery_planner.record_purchase(first, "test")
        OverviewState.load_overview.fn(overview)
        self.assertFalse(overview.has_grocery)
        self.assertEqual(overview.grocery_summary, "")
        self.assertTrue(all(count == 0 for count in overview.grocery_counts.values()))
        self.assertTrue(overview.has_inventory)
        self.assertEqual(overview.inventory_counts["dry_goods"], 1)

        second = grocery_planner._save_suggestion(response, [], "test")
        self.assertNotEqual(first["plan_id"], second["plan_id"])
        OverviewState.load_overview.fn(overview)
        self.assertTrue(overview.has_grocery)
        self.assertEqual(overview.grocery_counts["dry_goods"], 1)

    def test_inventory_card_refreshes_each_overview_visit(self):
        _, _, overview = self.screens()
        self.assertFalse(overview.has_inventory)
        inventory.add("Milk", 500, "dairy", session_id="test")
        OverviewState.load_overview.fn(overview)
        self.assertEqual(overview.inventory_counts["dairy"], 1)
        self.assertEqual(overview.inventory_summary, "1 item in your kitchen")
        inventory.delete("Milk", session_id="test")
        OverviewState.load_overview.fn(overview)
        self.assertFalse(overview.has_inventory)
        self.assertEqual(overview.inventory_counts["dairy"], 0)

    def test_skipping_either_or_both_setup_steps(self):
        blank_profile = {"name": "", "sex": "", "height": "", "weight": "", "age": "", "activity_level": "Low"}
        blank_preferences = {"calories": "", "current_goal": "Maintenance", "fiber": 30, "allergies": [], "diet_types": []}
        populated_profile = {"sex": "Male", "height": 180, "weight": 75, "age": 30, "activity_level": "Medium"}
        populated_preferences = {"calories": 2400, "fiber": 35, "current_goal": "Weight Loss", "muscle_gain": True}
        for profile, preferences in (
            (blank_profile, blank_preferences),
            (blank_profile, populated_preferences),
            (populated_profile, blank_preferences),
        ):
            with self.subTest(profile=profile, preferences=preferences):
                meal_planner._save_json(self.folder / "user_data.json", profile)
                meal_planner._save_json(self.folder / "user_personalization_data.json", preferences)
                self.assert_matching_empty_day()

    def test_invalid_files_fall_back_in_both_screens(self):
        (self.folder / "user_data.json").write_text("invalid json", encoding="utf-8")
        (self.folder / "user_personalization_data.json").write_text("[]", encoding="utf-8")
        self.assert_matching_empty_day()

    def test_updated_targets_and_today_meals_recalculate_remaining(self):
        meal_planner._save_json(self.folder / "user_personalization_data.json", {"calories": 2400, "fiber": 35})
        meal_planner._save_json(meal_planner.made_meals_path("test"), {"meals": [{"name": "Lunch", "calories": 600, "protein": 20, "carbs": 60, "fat": 15, "fiber": 5}]})
        targets, intake, overview = self.screens()
        self.assertEqual(targets.calories, "2,400")
        self.assertEqual(intake.calorie_left, "1,800 kcal left")
        self.assertEqual(intake.fiber_left, "30 g left")
        self.assertEqual(overview.meal_names, ["Lunch"])
        meal_planner._save_json(self.folder / "user_personalization_data.json", {"calories": 2000, "fiber": 30})
        targets, intake, overview = self.screens()
        self.assertEqual(targets.calories, "2,000")
        self.assertEqual(intake.calorie_goal, targets.calories)
        self.assertEqual(intake.calorie_left, "1,400 kcal left")


if __name__ == "__main__":
    unittest.main()
