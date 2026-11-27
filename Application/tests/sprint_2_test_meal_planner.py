"""Single-meal generation, inventory enforcement, and reversible daily history."""

import copy
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from Application import inventory
from Application import meal_planner as mp
from google.genai import types


class TestMealPlanner(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for target, field, value in (
            (mp, "USER_DATA_FOLDER", self.root),
            (inventory, "INVENTORY_FILE", self.root / "inventory.json"),
        ):
            patcher = patch.object(target, field, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.meal = dict(
            name="Rice bowl", description="Warm rice", meal_type="Lunch", servings=1,
            ingredients=[{"name": "Rice", "quantity_g": 100}],
            instructions=["Cook rice."], calories=350, protein=7, carbs=80, fat=1, fiber=2,
        )
        self.response = {"meals": [self.meal], "notes": "Estimated nutrition."}
        mp._save_json(self.root / "user_data.json", {})
        mp._save_json(self.root / "user_personalization_data.json", {})

    def stock(self, amount=500, session="a"):
        return inventory.add("Rice", amount, "dry_goods", session_id=session)

    def save(self, meal=None, session="a"):
        return mp._save_meals({"meals": [meal or self.meal], "notes": ""}, session)["meals"][0]

    def make(self, meal=None, session="a"):
        suggestion = self.save(meal, session)
        return mp.mark_meal_made(suggestion["meal_id"], session_id=session)["meal"]

    def test_only_one_requested_type_and_single_saved_suggestion(self):
        self.stock()
        with patch.object(mp, "_request_meals", return_value=self.response) as request:
            first = mp.generate_meal_suggestions("Lunch", session_id="a")
            payload = request.call_args.args[0]
            self.assertEqual(payload["meal_type"], "Lunch")
            self.assertEqual(payload["number_of_meals"], 1)
            self.assertEqual(payload["available_ingredients"][0]["quantity_g"], 500)
            second = mp.generate_meal_suggestions("Lunch", session_id="a")
        saved = mp._read_json(mp.suggestion_path("a"))
        self.assertEqual(saved, second)
        self.assertEqual(len(saved["meals"]), 1)
        self.assertNotEqual(first["meals"][0]["meal_id"], second["meals"][0]["meal_id"])
        self.assertEqual(list(mp._session_dir("a").glob("meal_suggestions*.json")), [mp.suggestion_path("a")])

    def test_empty_inventory_never_calls_ai(self):
        with patch.object(mp, "_request_meals") as request:
            with self.assertRaisesRegex(mp.InsufficientInventoryError, "empty"):
                mp.generate_meal_suggestions("Lunch", session_id="a")
            request.assert_not_called()
        self.assertFalse(mp.suggestion_path("a").exists())

    def test_ai_can_report_insufficient_inventory(self):
        self.stock()
        with patch.object(mp, "_request_meals", return_value={"meals": [], "notes": "No suitable recipe."}):
            with self.assertRaises(mp.InsufficientInventoryError):
                mp.generate_meal_suggestions("Dinner", session_id="a")
        self.assertFalse(mp.suggestion_path("a").exists())

    def test_rejects_wrong_type_and_multiple_meals(self):
        self.stock()
        for response in (self.response, {"meals": [self.meal, self.meal], "notes": ""}):
            with patch.object(mp, "_request_meals", return_value=response):
                with self.assertRaises(ValueError):
                    mp.generate_meal_suggestions("Dinner", session_id="a")
        self.assertFalse(mp.suggestion_path("a").exists())

    def test_invalid_type_and_session(self):
        for kind, session in (("Brunch", "a"), ("Lunch", "")):
            with self.assertRaises(ValueError):
                mp.generate_meal_suggestions(kind, session_id=session)

    def test_missing_excess_and_repeated_ingredients_are_rejected(self):
        self.stock(100)
        for ingredients in (
            [{"name": "Chicken", "quantity_g": 10}],
            [{"name": "Rice", "quantity_g": 101}],
            [{"name": "Rice", "quantity_g": 60}, {"name": "rice", "quantity_g": 60}],
            [{"name": "Rice", "quantity_g": 99.5}],
        ):
            with self.assertRaises(mp.InsufficientInventoryError):
                self.save({**self.meal, "ingredients": ingredients})
        self.assertFalse(mp.suggestion_path("a").exists())

    def test_daily_history_appends_and_undo_restores_fully_used_item(self):
        self.stock(200)
        first = self.make()
        second = self.make()
        path = mp.made_meals_path("a")
        self.assertEqual(len(list(path.parent.glob("*.json"))), 1)
        self.assertEqual(len(mp.get_made_meals("a")), 2)
        self.assertEqual(inventory.get_inventory(session_id="a"), [])
        mp.unmark_meal_made(first["meal_id"], session_id="a")
        self.assertEqual(inventory.get_inventory(session_id="a"), [{"name": "Rice", "quantity_g": 100, "grocery_type": "dry_goods"}])
        self.assertEqual([row["meal_id"] for row in mp.get_made_meals("a")], [second["meal_id"]])
        with self.assertRaises(ValueError):
            mp.unmark_meal_made(first["meal_id"], session_id="a")
        self.assertEqual(inventory.get_inventory(session_id="a")[0]["quantity_g"], 100)

    def test_duplicate_make_and_reload_and_remake_after_undo(self):
        self.stock(200)
        meal = self.make()
        self.assertTrue(mp.load_meal_suggestion("a")["meals"][0]["made"])
        with self.assertRaisesRegex(ValueError, "already"):
            mp.mark_meal_made(meal["meal_id"], session_id="a")
        mp.unmark_meal_made(meal["meal_id"], session_id="a")
        self.assertFalse(mp.load_meal_suggestion("a")["meals"][0]["made"])
        mp.mark_meal_made(meal["meal_id"], session_id="a")
        self.assertEqual(len(mp.get_made_meals("a")), 1)
        self.assertEqual(inventory.get_inventory(session_id="a")[0]["quantity_g"], 100)

    def test_stock_is_rechecked_at_completion(self):
        self.stock(200)
        meal = self.save()
        inventory.remove("Rice", 150, session_id="a")
        with self.assertRaises(mp.InsufficientInventoryError):
            mp.mark_meal_made(meal["meal_id"], session_id="a")
        self.assertEqual(mp.get_made_meals("a"), [])
        self.assertEqual(inventory.get_inventory(session_id="a")[0]["quantity_g"], 50)

    def test_concurrent_make_and_undo_only_change_inventory_once(self):
        self.stock(200)
        meal = self.save()
        def attempt(action):
            try:
                action(meal["meal_id"], session_id="a")
                return True
            except ValueError:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, [mp.mark_meal_made, mp.mark_meal_made]))
        self.assertEqual(sum(results), 1)
        self.assertEqual(inventory.get_inventory(session_id="a")[0]["quantity_g"], 100)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, [mp.unmark_meal_made, mp.unmark_meal_made]))
        self.assertEqual(sum(results), 1)
        self.assertEqual(inventory.get_inventory(session_id="a")[0]["quantity_g"], 200)

    def test_undo_restores_actual_deduction_after_inventory_rounding(self):
        self.stock(10)
        meal = self.make({**self.meal, "ingredients": [{"name": "Rice", "quantity_g": 0.1234}]})
        mp.unmark_meal_made(meal["meal_id"], session_id="a")
        self.assertEqual(inventory.get_inventory(session_id="a")[0]["quantity_g"], 10)

    def test_preferences_changes_preserve_made_meals(self):
        from Application import grocery_planner
        self.stock()
        self.make()
        with patch.object(grocery_planner, "USER_DATA_FOLDER", self.root):
            grocery_planner.invalidate_weekly_plan()
        self.assertEqual(len(mp.get_made_meals("a")), 1)
        self.assertFalse(mp.suggestion_path("a").exists())

    def test_day_rollover_and_session_isolation(self):
        self.stock(300)
        with patch.object(mp, "datetime") as clock:
            clock.strptime = datetime.strptime
            clock.now.return_value.astimezone.return_value = datetime(2026, 11, 26, 12, tzinfo=timezone.utc)
            first = self.make()
            clock.now.return_value.astimezone.return_value = datetime(2026, 11, 27, 12, tzinfo=timezone.utc)
            self.make()
        self.assertEqual(len(mp.get_made_meals("a", "2026-11-26")), 1)
        self.assertEqual(len(mp.get_made_meals("a", "2026-11-27")), 1)
        self.assertEqual(mp.get_made_meals("b", "2026-11-26"), [])
        with self.assertRaises(ValueError):
            mp.unmark_meal_made(first["meal_id"], session_id="b")
        mp.unmark_meal_made(first["meal_id"], session_id="a")
        self.assertEqual(mp.get_made_meals("a", "2026-11-26"), [])
        self.assertEqual(inventory.get_inventory(session_id="a")[0]["quantity_g"], 200)

    def test_failed_history_write_rolls_back_inventory(self):
        self.stock(200)
        suggestion = self.save()
        with patch.object(mp, "_save_json", side_effect=OSError("Disk unavailable")):
            with self.assertRaises(OSError):
                mp.mark_meal_made(suggestion["meal_id"], session_id="a")
        self.assertEqual(inventory.get_inventory(session_id="a")[0]["quantity_g"], 200)
        meal = mp.mark_meal_made(suggestion["meal_id"], session_id="a")["meal"]
        with patch.object(mp, "_save_json", side_effect=OSError("Disk unavailable")):
            with self.assertRaises(OSError):
                mp.unmark_meal_made(meal["meal_id"], session_id="a")
        self.assertEqual(inventory.get_inventory(session_id="a")[0]["quantity_g"], 100)
        self.assertEqual(len(mp.get_made_meals("a")), 1)

    def test_today_totals_change_on_make_and_undo(self):
        from Application.intake import _made_macro_intake
        self.stock()
        self.save()
        self.assertEqual(_made_macro_intake("a")["calories"], 0)
        meal = self.make()
        self.assertEqual(_made_macro_intake("a")["calories"], 350)
        mp.unmark_meal_made(meal["meal_id"], session_id="a")
        self.assertEqual(_made_macro_intake("a")["calories"], 0)

    def test_validation_rejects_bad_quantities_and_nutrition(self):
        for amount in (-1, 0, True, float("nan"), float("inf")):
            invalid = copy.deepcopy(self.response)
            invalid["meals"][0]["ingredients"][0]["quantity_g"] = amount
            with self.assertRaises(ValueError):
                mp._validate_meals(invalid)
        for amount in (-1, True, float("nan")):
            invalid = copy.deepcopy(self.response)
            invalid["meals"][0]["calories"] = amount
            with self.assertRaises(ValueError):
                mp._validate_meals(invalid)

    @patch.object(mp.genai, "Client")
    @patch.object(mp, "dotenv_values", return_value={"GEMINI_API_KEY": "test", "GEMINI_MODEL": "test"})
    def test_request_accepts_empty_response_for_inventory_warning(self, settings, mock_client):
        response = MagicMock()
        response.candidates = [MagicMock(finish_reason=types.FinishReason.STOP)]
        response.text = '{"meals": [], "notes": "Not enough food"}'
        mock_client.return_value.__enter__.return_value.models.generate_content.return_value = response
        self.assertEqual(mp._request_meals({})["meals"], [])


if __name__ == "__main__":
    unittest.main()
