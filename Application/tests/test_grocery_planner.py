"""Unit tests for the Gemini grocery planner backend."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from google.genai import types

from Application import grocery_planner as gp


class TestGroceryPlanner(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_folder = Path(self.temp_dir.name)

        self.folder_patcher = patch.object(
            gp, "USER_DATA_FOLDER", self.data_folder
        )
        self.folder_patcher.start()

        # Same format onboarding.py saves to user_data.json.
        self.profile = {
            "sex": "Female",
            "activity_level": "Medium",
            "height": 170.0,
            "weight": 65.0,
            "age": 25.0
        }

        # Same format personalize.py saves to user_personalization_data.json.
        self.preferences = {
            "calories": "",
            "current_goal": "Maintenance",
            "muscle_gain": False,
            "allergies": ["Peanuts"],
            "diet_types": ["Vegetarian"],
            "fiber": 30.0
        }

        self.targets = {
            "calories": 2000,
            "protein": 100,
            "carbs": 250,
            "fat": 65,
            "fiber": 30
        }

        self.write_json(
            self.data_folder / "user_data.json",
            self.profile
        )

        self.write_json(
            self.data_folder / "user_personalization_data.json",
            self.preferences
        )

        self.valid_suggestion = {
            "items": [
                {
                    "name": "Chicken Breast",
                    "grocery_type": "meat",
                    "quantity_g": 1000,
                    "preparation": "Raw weight",
                    "calories": 1200,
                    "protein": 230,
                    "carbs": 0,
                    "fat": 25,
                    "fiber": 0
                },
                {
                    "name": "Brown Rice",
                    "grocery_type": "dry_goods",
                    "quantity_g": 500,
                    "preparation": "Dry weight",
                    "calories": 1800,
                    "protein": 35,
                    "carbs": 375,
                    "fat": 15,
                    "fiber": 20
                }
            ],
            "notes": "A balanced grocery list for the week."
        }

    def tearDown(self):
        self.folder_patcher.stop()
        self.temp_dir.cleanup()

    def write_json(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")

    # -------------------------
    # JSON READING TESTS
    # -------------------------

    def test_read_json_returns_dictionary(self):
        path = self.data_folder / "test.json"
        self.write_json(path, {"name": "Test"})

        result = gp._read_json(path)

        self.assertEqual(result, {"name": "Test"})

    def test_read_json_rejects_non_dictionary(self):
        path = self.data_folder / "test.json"
        self.write_json(path, ["item1", "item2"])

        with self.assertRaises(ValueError):
            gp._read_json(path)

    # -------------------------
    # PLANNING CONTEXT TESTS
    # -------------------------

    @patch.object(gp, "get_targets")
    def test_planning_context_returns_correct_data(self, mock_targets):
        mock_targets.return_value = self.targets

        result = gp._planning_context()

        self.assertEqual(result["days"], 7)
        self.assertEqual(result["daily_targets"], self.targets)
        self.assertEqual(result["weekly_targets"]["calories"], 14000)
        self.assertEqual(result["weekly_targets"]["protein"], 700)
        self.assertEqual(result["allergies"], ["Peanuts"])
        self.assertEqual(result["diet_types"], ["Vegetarian"])

    @patch.object(gp, "get_targets")
    def test_planning_context_rejects_invalid_allergies(self, mock_targets):
        self.preferences["allergies"] = ["Peanuts", ""]
        self.write_json(
            self.data_folder / "user_personalization_data.json",
            self.preferences
        )

        with self.assertRaises(ValueError):
            gp._planning_context()

        mock_targets.assert_not_called()

    @patch.object(gp, "get_targets")
    def test_planning_context_rejects_invalid_diet_types(self, mock_targets):
        self.preferences["diet_types"] = "Vegetarian"
        self.write_json(
            self.data_folder / "user_personalization_data.json",
            self.preferences
        )

        with self.assertRaises(ValueError):
            gp._planning_context()

        mock_targets.assert_not_called()

    @patch.object(gp, "get_targets")
    def test_planning_context_requires_positive_calories(self, mock_targets):
        invalid_targets = self.targets.copy()
        invalid_targets["calories"] = 0
        mock_targets.return_value = invalid_targets

        with self.assertRaises(ValueError):
            gp._planning_context()

    # -------------------------
    # SUGGESTION VALIDATION TESTS
    # -------------------------

    def test_validate_suggestion_accepts_valid_suggestion(self):
        gp._validate_suggestion(self.valid_suggestion)

    def test_validate_suggestion_rejects_non_dictionary(self):
        with self.assertRaises(ValueError):
            gp._validate_suggestion(["not", "a", "dictionary"])

    def test_validate_suggestion_rejects_missing_items(self):
        with self.assertRaises(ValueError):
            gp._validate_suggestion({
                "notes": "No items"
            })

    def test_validate_suggestion_rejects_empty_items(self):
        with self.assertRaises(ValueError):
            gp._validate_suggestion({
                "items": [],
                "notes": "No items"
            })

    def test_validate_suggestion_rejects_missing_notes(self):
        suggestion = self.valid_suggestion.copy()
        suggestion.pop("notes")

        with self.assertRaises(ValueError):
            gp._validate_suggestion(suggestion)

    def test_validate_suggestion_rejects_invalid_grocery_type(self):
        suggestion = json.loads(json.dumps(self.valid_suggestion))
        suggestion["items"][0]["grocery_type"] = "frozen"

        with self.assertRaises(ValueError):
            gp._validate_suggestion(suggestion)

    def test_validate_suggestion_rejects_empty_item_name(self):
        suggestion = json.loads(json.dumps(self.valid_suggestion))
        suggestion["items"][0]["name"] = ""

        with self.assertRaises(ValueError):
            gp._validate_suggestion(suggestion)

    def test_validate_suggestion_rejects_zero_quantity(self):
        suggestion = json.loads(json.dumps(self.valid_suggestion))
        suggestion["items"][0]["quantity_g"] = 0

        with self.assertRaises(ValueError):
            gp._validate_suggestion(suggestion)

    def test_validate_suggestion_rejects_negative_nutrients(self):
        suggestion = json.loads(json.dumps(self.valid_suggestion))
        suggestion["items"][0]["protein"] = -10

        with self.assertRaises(ValueError):
            gp._validate_suggestion(suggestion)

    def test_validate_suggestion_rejects_boolean_values(self):
        suggestion = json.loads(json.dumps(self.valid_suggestion))
        suggestion["items"][0]["calories"] = True

        with self.assertRaises(ValueError):
            gp._validate_suggestion(suggestion)

    # -------------------------
    # SESSION AND PATH TESTS
    # -------------------------

    def test_suggestion_path_uses_default_folder(self):
        result = gp.suggestion_path()

        self.assertEqual(
            result,
            self.data_folder / "weekly_suggestion.json"
        )

    def test_inventory_path_uses_default_folder(self):
        result = gp.inventory_path()

        self.assertEqual(
            result,
            self.data_folder / "weekly_grocery_inventory.json"
        )

    def test_session_paths_are_separate(self):
        first_path = gp.suggestion_path("session1")
        second_path = gp.suggestion_path("session2")

        self.assertNotEqual(first_path, second_path)
        self.assertTrue(first_path.parent.exists())
        self.assertTrue(second_path.parent.exists())

    def test_session_id_is_sanitized(self):
        result = gp.suggestion_path("session/123")

        self.assertEqual(result.parent.name, "session123")

    def test_invalid_session_id_is_rejected(self):
        with self.assertRaises(ValueError):
            gp.suggestion_path("///")

    # -------------------------
    # SAVING TESTS
    # -------------------------

    def test_save_suggestion_calculates_weekly_totals(self):
        result = gp._save_suggestion(self.valid_suggestion)

        self.assertEqual(
            result["estimated_weekly_totals"]["calories"],
            3000
        )
        self.assertEqual(
            result["estimated_weekly_totals"]["protein"],
            265
        )

        saved = gp._read_json(gp.suggestion_path())
        self.assertEqual(saved, result)

    def test_save_suggestion_uses_session_folder(self):
        result = gp._save_suggestion(
            self.valid_suggestion,
            session_id="test_session"
        )

        saved = gp._read_json(
            gp.suggestion_path("test_session")
        )

        self.assertEqual(saved, result)
        self.assertTrue(
            gp.suggestion_path("test_session").exists()
        )

    def test_record_purchase_saves_inventory(self):
        result = gp.record_purchase(self.valid_suggestion)

        saved = gp._read_json(gp.inventory_path())

        self.assertEqual(result, self.valid_suggestion)
        self.assertEqual(saved, self.valid_suggestion)

    def test_record_purchase_rejects_invalid_suggestion(self):
        invalid = {
            "items": [],
            "notes": "Invalid"
        }

        with self.assertRaises(ValueError):
            gp.record_purchase(invalid)

        self.assertFalse(gp.inventory_path().exists())

    # -------------------------
    # GENERATION TESTS
    # -------------------------

    @patch.object(gp, "_request_suggestion")
    @patch.object(gp, "get_targets")
    def test_generate_weekly_plan_saves_suggestion(
        self, mock_targets, mock_request
    ):
        mock_targets.return_value = self.targets
        mock_request.return_value = self.valid_suggestion

        result = gp.generate_weekly_plan()

        mock_request.assert_called_once()
        self.assertEqual(
            result["estimated_weekly_totals"]["calories"],
            3000
        )
        self.assertTrue(gp.suggestion_path().exists())

    @patch.object(gp, "_request_suggestion")
    @patch.object(gp, "get_targets")
    def test_generate_weekly_plan_uses_session(
        self, mock_targets, mock_request
    ):
        mock_targets.return_value = self.targets
        mock_request.return_value = self.valid_suggestion

        gp.generate_weekly_plan(session_id="user123")

        self.assertTrue(
            gp.suggestion_path("user123").exists()
        )
        self.assertFalse(gp.suggestion_path().exists())

    # -------------------------
    # REVISION TESTS
    # -------------------------

    def test_revision_rejects_empty_feedback(self):
        with self.assertRaises(ValueError):
            gp.revise_weekly_plan("")

    def test_revision_rejects_non_string_feedback(self):
        with self.assertRaises(ValueError):
            gp.revise_weekly_plan(None)

    def test_revision_requires_saved_suggestion(self):
        with self.assertRaises(FileNotFoundError):
            gp.revise_weekly_plan("Add more vegetables")

    @patch.object(gp, "_request_suggestion")
    @patch.object(gp, "get_targets")
    def test_revision_updates_saved_suggestion(
        self, mock_targets, mock_request
    ):
        mock_targets.return_value = self.targets

        gp._save_suggestion(self.valid_suggestion)

        revised = json.loads(json.dumps(self.valid_suggestion))
        revised["notes"] = "Added more vegetables."

        mock_request.return_value = revised

        result = gp.revise_weekly_plan("Add more vegetables")

        mock_request.assert_called_once()
        self.assertEqual(
            result["notes"],
            "Added more vegetables."
        )

        saved = gp._read_json(gp.suggestion_path())
        self.assertEqual(saved, result)

    # -------------------------
    # INVALIDATION TESTS
    # -------------------------

    def test_invalidate_weekly_plan_removes_saved_files(self):
        gp._save_suggestion(self.valid_suggestion)
        gp.record_purchase(self.valid_suggestion)

        gp.invalidate_weekly_plan()

        self.assertFalse(gp.suggestion_path().exists())
        self.assertFalse(gp.inventory_path().exists())

    def test_invalidate_weekly_plan_removes_session_files(self):
        gp._save_suggestion(
            self.valid_suggestion,
            session_id="session1"
        )

        gp.record_purchase(
            self.valid_suggestion,
            session_id="session1"
        )

        gp.invalidate_weekly_plan()

        self.assertFalse(
            gp.suggestion_path("session1").exists()
        )
        self.assertFalse(
            gp.inventory_path("session1").exists()
        )

    # -------------------------
    # GEMINI REQUEST TESTS
    # -------------------------

    @patch.object(gp, "dotenv_values", return_value={})
    @patch.dict("os.environ", {}, clear=True)
    def test_request_suggestion_requires_api_key(self, mock_dotenv):
        with self.assertRaises(ValueError):
            gp._request_suggestion(
                {},
                system_prompt=gp.GENERATION_SYSTEM_PROMPT
            )

    @patch.object(gp, "dotenv_values", return_value={
        "GEMINI_API_KEY": "test-key"
    })
    @patch.dict("os.environ", {}, clear=True)
    def test_request_suggestion_requires_model(self, mock_dotenv):
        with self.assertRaises(ValueError):
            gp._request_suggestion(
                {},
                system_prompt=gp.GENERATION_SYSTEM_PROMPT
            )

    @patch.object(gp, "dotenv_values", return_value={
        "GEMINI_API_KEY": "test-key",
        "GEMINI_MODEL": "test-model"
    })
    @patch.object(gp.genai, "Client")
    def test_request_suggestion_returns_valid_response(
        self, mock_client, mock_dotenv
    ):
        response = MagicMock()
        response.candidates = [
            MagicMock(finish_reason=types.FinishReason.STOP)
        ]
        response.text = json.dumps(self.valid_suggestion)

        client = MagicMock()
        client.__enter__.return_value = client
        client.models.generate_content.return_value = response
        mock_client.return_value = client

        result = gp._request_suggestion(
            {"days": 7},
            system_prompt=gp.GENERATION_SYSTEM_PROMPT
        )

        self.assertEqual(result, self.valid_suggestion)
        client.models.generate_content.assert_called_once()

    @patch.object(gp, "dotenv_values", return_value={
        "GEMINI_API_KEY": "test-key",
        "GEMINI_MODEL": "test-model"
    })
    @patch.object(gp.genai, "Client")
    def test_request_suggestion_rejects_unfinished_response(
        self, mock_client, mock_dotenv
    ):
        response = MagicMock()
        response.candidates = [
            MagicMock(finish_reason=types.FinishReason.MAX_TOKENS)
        ]

        client = MagicMock()
        client.__enter__.return_value = client
        client.models.generate_content.return_value = response
        mock_client.return_value = client

        with self.assertRaises(ValueError):
            gp._request_suggestion(
                {},
                system_prompt=gp.GENERATION_SYSTEM_PROMPT
            )

    @patch.object(gp, "dotenv_values", return_value={
        "GEMINI_API_KEY": "test-key",
        "GEMINI_MODEL": "test-model"
    })
    @patch.object(gp.genai, "Client")
    def test_request_suggestion_rejects_invalid_json(
        self, mock_client, mock_dotenv
    ):
        response = MagicMock()
        response.candidates = [
            MagicMock(finish_reason=types.FinishReason.STOP)
        ]
        response.text = "not valid json"

        client = MagicMock()
        client.__enter__.return_value = client
        client.models.generate_content.return_value = response
        mock_client.return_value = client

        with self.assertRaises(ValueError):
            gp._request_suggestion(
                {},
                system_prompt=gp.GENERATION_SYSTEM_PROMPT
            )


if __name__ == "__main__":
    unittest.main()