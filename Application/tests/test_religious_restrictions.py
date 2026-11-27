"""Religious preferences persist and reach both AI planners."""

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from Application import get_targets, grocery_planner, inventory, meal_planner, personalize
from Application.dietary_restrictions import get_religious_restrictions
from Application.home import OverviewState


class ReligiousRestrictionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        for module in (get_targets, grocery_planner, meal_planner, personalize):
            patcher = patch.object(module, "USER_DATA_FOLDER", self.folder)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.object(inventory, "INVENTORY_FILE", self.folder / "inventory.json")
        patcher.start()
        self.addCleanup(patcher.stop)
        meal_planner._save_json(self.folder / "user_data.json", {})
        meal_planner._save_json(self.folder / "user_personalization_data.json", {})

    def test_save_restore_clear_and_invalidate_suggestions(self):
        state = personalize.PersonalizationState(_reflex_internal_init=True)
        state.editing = True
        personalize.PersonalizationState.toggle_religious_restriction.fn(state, "Halal", True)
        personalize.PersonalizationState.toggle_religious_restriction.fn(state, "Halal", True)
        self.assertEqual(state.religious_restrictions, ["Halal"])
        meal_planner._save_json(meal_planner.suggestion_path("test"), {"old": True})
        history = meal_planner.made_meals_path("test")
        meal_planner._save_json(history, {"meals": []})
        personalize.PersonalizationState.submit.fn(state, {})
        self.assertFalse(meal_planner.suggestion_path("test").exists())
        self.assertTrue(history.exists())
        saved = meal_planner._read_json(self.folder / "user_personalization_data.json")
        self.assertEqual(saved["religious_restrictions"], ["Halal"])
        restored = personalize.PersonalizationState(_reflex_internal_init=True)
        personalize.PersonalizationState.load_editor.fn(restored)
        self.assertEqual(restored.religious_restrictions, ["Halal"])
        personalize.PersonalizationState.toggle_religious_restriction.fn(restored, "Halal", False)
        personalize.PersonalizationState.submit.fn(restored, {})
        self.assertEqual(meal_planner._read_json(self.folder / "user_personalization_data.json")["religious_restrictions"], [])

    def test_older_preferences_default_to_no_religious_restrictions(self):
        state = personalize.PersonalizationState(_reflex_internal_init=True)
        personalize.PersonalizationState.load_editor.fn(state)
        self.assertEqual(state.religious_restrictions, [])
        self.assertEqual(grocery_planner._planning_context([])["religious_restrictions"], [])
        self.assertEqual(meal_planner._meal_context("test")["religious_restrictions"], [])

    def test_generation_and_revision_payloads_include_restrictions(self):
        meal_planner._save_json(self.folder / "user_personalization_data.json", {"religious_restrictions": ["Kosher"]})
        inventory.add("Rice", 500, "dry_goods", session_id="test")
        item = {"name": "Rice", "quantity_g": 100, "grocery_type": "dry_goods", "preparation": "Cook rice.", "calories": 350, "protein": 7, "carbs": 80, "fat": 1, "fiber": 2}
        with patch.object(grocery_planner, "_request_suggestion", return_value={"items": [item], "notes": ""}) as request:
            grocery_planner.generate_weekly_plan("test")
            self.assertEqual(request.call_args.args[0]["religious_restrictions"], ["Kosher"])
            grocery_planner.revise_weekly_plan("More rice", "test")
            self.assertEqual(request.call_args.args[0]["religious_restrictions"], ["Kosher"])
        meal = {"name": "Rice breakfast", "description": "Rice", "meal_type": "Breakfast", "servings": 1,
                "ingredients": [{"name": "Rice", "quantity_g": 100}], "instructions": ["Cook rice."],
                **{key: item[key] for key in meal_planner.NUTRIENTS}}
        with patch.object(meal_planner, "_request_meals", return_value={"meals": [meal], "notes": ""}) as request:
            meal_planner.generate_meal_suggestions("Breakfast", session_id="test")
            self.assertEqual(request.call_args.args[0]["religious_restrictions"], ["Kosher"])

    def test_malformed_saved_restrictions_are_rejected(self):
        for value in ("Halal", [""], [1], ["Unsupported"], None):
            with self.subTest(value=value):
                meal_planner._save_json(self.folder / "user_personalization_data.json", {"religious_restrictions": value})
                with self.assertRaisesRegex(ValueError, "religious_restrictions"):
                    grocery_planner._planning_context([])
                with self.assertRaisesRegex(ValueError, "religious_restrictions"):
                    meal_planner._meal_context("test")
        self.assertEqual(get_religious_restrictions({"religious_restrictions": ["Halal", "Halal"]}), ["Halal"])

    def test_overview_shows_restrictions_without_changing_targets(self):
        baseline = get_targets.get_targets()
        meal_planner._save_json(self.folder / "user_personalization_data.json", {"religious_restrictions": ["Jain vegetarian"]})
        overview = SimpleNamespace(rx_router_session=SimpleNamespace(client_token="test"))
        OverviewState.load_overview.fn(overview)
        self.assertIn("Jain vegetarian", overview.chips)
        self.assertEqual(get_targets.get_targets(), baseline)


if __name__ == "__main__":
    unittest.main()
