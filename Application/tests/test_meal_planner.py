"""Unit tests for the Gemini meal suggestion backend."""

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

from Application import meal_planner as mp


def make_response(text, finish_reason=types.FinishReason.STOP):
    response = MagicMock()
    response.candidates = [MagicMock(finish_reason=finish_reason)]
    response.text = text
    return response


def make_client(mock_client, response):
    client = MagicMock()
    client.__enter__.return_value = client
    client.models.generate_content.return_value = response
    mock_client.return_value = client
    return client


class TestMealPlanner(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_folder = Path(self.temp_dir.name)

        self.folder_patcher = patch.object(
            mp, "USER_DATA_FOLDER", self.data_folder
        )
        self.folder_patcher.start()

        self.profile = {
            "age": 25,
            "weight": 65,
            "height": 170,
            "sex": "Female",
            "activity_level": "Moderately Active"
        }

        self.preferences = {
            "allergies": ["Peanuts"],
            "diet_types": ["Halal"],
            "current_goal": "Weight Loss",
            "muscle_gain": True
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

        self.meal = {
            "name": "Chicken Rice Bowl",
            "description": "Grilled chicken with brown rice and vegetables.",
            "meal_type": "Lunch",
            "servings": 1,
            "ingredients": ["150 g chicken breast", "100 g brown rice"],
            "instructions": ["Grill the chicken.", "Cook the rice."],
            "calories": 550,
            "protein": 45,
            "carbs": 60,
            "fat": 12,
            "fiber": 6
        }

        self.valid_response = {
            "meals": [self.meal],
            "notes": "Fiber comes mostly from the rice and vegetables."
        }

    def tearDown(self):
        self.folder_patcher.stop()
        self.temp_dir.cleanup()

    def write_json(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")

    def response_with(self, **changes):
        """Copy of the valid response with one meal field changed."""
        response = json.loads(json.dumps(self.valid_response))
        response["meals"][0].update(changes)
        return response

    # -------------------------
    # JSON READING TESTS
    # -------------------------

    def test_read_json_returns_dictionary(self):
        path = self.data_folder / "test.json"
        self.write_json(path, {"name": "Test"})

        self.assertEqual(mp._read_json(path), {"name": "Test"})

    def test_read_json_rejects_non_dictionary(self):
        path = self.data_folder / "test.json"
        self.write_json(path, ["item1", "item2"])

        with self.assertRaises(ValueError):
            mp._read_json(path)

    def test_read_json_rejects_corrupted_file(self):
        path = self.data_folder / "test.json"
        path.write_text("{not json", encoding="utf-8")

        with self.assertRaises(json.JSONDecodeError):
            mp._read_json(path)

    # -------------------------
    # MEAL CONTEXT TESTS
    # -------------------------

    @patch.object(mp, "get_targets")
    def test_meal_context_returns_correct_data(self, mock_targets):
        mock_targets.return_value = self.targets

        result = mp._meal_context()

        self.assertEqual(result["daily_targets"], self.targets)
        self.assertEqual(result["goal"], "Weight Loss")
        self.assertTrue(result["muscle_gain"])
        self.assertEqual(result["allergies"], ["Peanuts"])
        self.assertEqual(result["diet_types"], ["Halal"])
        mock_targets.assert_called_once_with(self.profile, self.preferences)

    @patch.object(mp, "get_targets")
    def test_meal_context_keeps_only_nutrient_targets(self, mock_targets):
        mock_targets.return_value = {
            **self.targets,
            "goal_description": "Extra field"
        }

        result = mp._meal_context()

        self.assertEqual(
            set(result["daily_targets"]),
            set(mp.NUTRIENTS)
        )

    @patch.object(mp, "get_targets")
    def test_meal_context_uses_defaults_for_missing_preferences(
        self, mock_targets
    ):
        mock_targets.return_value = self.targets
        self.write_json(
            self.data_folder / "user_personalization_data.json",
            {}
        )

        result = mp._meal_context()

        self.assertEqual(result["goal"], "Maintenance")
        self.assertFalse(result["muscle_gain"])
        self.assertEqual(result["allergies"], [])
        self.assertEqual(result["diet_types"], [])

    @patch.object(mp, "get_targets")
    def test_meal_context_rejects_invalid_allergies(self, mock_targets):
        self.preferences["allergies"] = ["Peanuts", "  "]
        self.write_json(
            self.data_folder / "user_personalization_data.json",
            self.preferences
        )

        with self.assertRaises(ValueError):
            mp._meal_context()

        mock_targets.assert_not_called()

    @patch.object(mp, "get_targets")
    def test_meal_context_rejects_invalid_diet_types(self, mock_targets):
        self.preferences["diet_types"] = "Halal"
        self.write_json(
            self.data_folder / "user_personalization_data.json",
            self.preferences
        )

        with self.assertRaises(ValueError):
            mp._meal_context()

        mock_targets.assert_not_called()

    @patch.object(mp, "get_targets")
    def test_meal_context_rejects_non_string_allergy(self, mock_targets):
        self.preferences["allergies"] = ["Peanuts", 5]
        self.write_json(
            self.data_folder / "user_personalization_data.json",
            self.preferences
        )

        with self.assertRaises(ValueError):
            mp._meal_context()

    @patch.object(mp, "get_targets")
    def test_meal_context_requires_positive_calories(self, mock_targets):
        invalid_targets = self.targets.copy()
        invalid_targets["calories"] = 0
        mock_targets.return_value = invalid_targets

        with self.assertRaises(ValueError):
            mp._meal_context()

    @patch.object(mp, "get_targets")
    def test_meal_context_requires_profile_file(self, mock_targets):
        (self.data_folder / "user_data.json").unlink()

        with self.assertRaises(FileNotFoundError):
            mp._meal_context()

        mock_targets.assert_not_called()

    # -------------------------
    # MEAL VALIDATION TESTS
    # -------------------------

    def test_validate_meals_accepts_valid_response(self):
        mp._validate_meals(self.valid_response)

    def test_validate_meals_accepts_every_meal_type(self):
        for meal_type in ("Breakfast", "Lunch", "Dinner", "Snack", "Dessert"):
            with self.subTest(meal_type=meal_type):
                mp._validate_meals(self.response_with(meal_type=meal_type))

    def test_validate_meals_accepts_decimal_nutrients(self):
        mp._validate_meals(self.response_with(protein=45.5))

    def test_validate_meals_rejects_non_dictionary(self):
        with self.assertRaises(ValueError):
            mp._validate_meals(["not", "a", "dictionary"])

    def test_validate_meals_rejects_missing_meals(self):
        with self.assertRaises(ValueError):
            mp._validate_meals({"notes": "No meals"})

    def test_validate_meals_rejects_empty_meals(self):
        with self.assertRaises(ValueError):
            mp._validate_meals({"meals": [], "notes": "No meals"})

    def test_validate_meals_rejects_missing_notes(self):
        response = self.valid_response.copy()
        response.pop("notes")

        with self.assertRaises(ValueError):
            mp._validate_meals(response)

    def test_validate_meals_rejects_non_dictionary_meal(self):
        with self.assertRaises(ValueError):
            mp._validate_meals({"meals": ["Chicken"], "notes": ""})

    def test_validate_meals_rejects_invalid_text_fields(self):
        for field in ("name", "description", "meal_type"):
            for value in ("", "   ", None, 5):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValueError):
                        mp._validate_meals(self.response_with(**{field: value}))

    def test_validate_meals_rejects_invalid_meal_type(self):
        for meal_type in ("Brunch", "lunch"):
            with self.subTest(meal_type=meal_type):
                with self.assertRaises(ValueError):
                    mp._validate_meals(self.response_with(meal_type=meal_type))

    def test_validate_meals_rejects_invalid_servings(self):
        for servings in (0, -1, 1.5, "2", True, None):
            with self.subTest(servings=servings):
                with self.assertRaises(ValueError):
                    mp._validate_meals(self.response_with(servings=servings))

    def test_validate_meals_rejects_invalid_ingredients(self):
        for value in ([], ["Rice", ""], ["Rice", 5], "Rice"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    mp._validate_meals(self.response_with(ingredients=value))

    def test_validate_meals_rejects_invalid_instructions(self):
        for value in ([], ["Cook", "  "], None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    mp._validate_meals(self.response_with(instructions=value))

    def test_validate_meals_rejects_negative_nutrients(self):
        for nutrient in mp.NUTRIENTS:
            with self.subTest(nutrient=nutrient):
                with self.assertRaises(ValueError):
                    mp._validate_meals(self.response_with(**{nutrient: -1}))

    def test_validate_meals_accepts_zero_nutrients(self):
        mp._validate_meals(self.response_with(fiber=0))

    def test_validate_meals_rejects_non_numeric_nutrients(self):
        for value in (True, "500", None, float("nan"), float("inf")):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    mp._validate_meals(self.response_with(calories=value))

    # -------------------------
    # SESSION AND PATH TESTS
    # -------------------------

    def test_suggestion_path_uses_default_folder(self):
        self.assertEqual(
            mp.suggestion_path(),
            self.data_folder / "meal_suggestions.json"
        )

    def test_selected_meals_path_uses_default_folder(self):
        self.assertEqual(
            mp.selected_meals_path(),
            self.data_folder / "selected_meals.json"
        )

    def test_session_paths_are_separate(self):
        first_path = mp.suggestion_path("session1")
        second_path = mp.suggestion_path("session2")

        self.assertNotEqual(first_path, second_path)
        self.assertTrue(first_path.parent.exists())
        self.assertTrue(second_path.parent.exists())

    def test_session_id_is_sanitized(self):
        result = mp.suggestion_path("../session/123")

        self.assertEqual(result.parent.name, "session123")
        self.assertEqual(
            result.parent.parent,
            self.data_folder / "sessions"
        )

    def test_invalid_session_id_is_rejected(self):
        with self.assertRaises(ValueError):
            mp.suggestion_path("///")

    # -------------------------
    # SAVING TESTS
    # -------------------------

    def test_save_json_leaves_no_temporary_files(self):
        path = self.data_folder / "output.json"

        mp._save_json(path, {"value": 1})

        self.assertEqual(mp._read_json(path), {"value": 1})
        self.assertEqual(
            list(self.data_folder.glob("*.tmp.json")),
            []
        )

    def test_save_json_rejects_nan_without_overwriting(self):
        path = self.data_folder / "output.json"
        mp._save_json(path, {"value": 1})

        with self.assertRaises(ValueError):
            mp._save_json(path, {"value": float("nan")})

        self.assertEqual(mp._read_json(path), {"value": 1})

    def test_save_meals_keeps_only_meals_and_notes(self):
        response = {**self.valid_response, "extra": "ignored"}

        result = mp._save_meals(response)

        self.assertEqual(result, self.valid_response)
        self.assertEqual(
            mp._read_json(mp.suggestion_path()),
            self.valid_response
        )

    def test_save_meals_uses_session_folder(self):
        mp._save_meals(self.valid_response, session_id="test_session")

        self.assertTrue(mp.suggestion_path("test_session").exists())
        self.assertFalse(mp.suggestion_path().exists())

    # -------------------------
    # SELECT MEAL TESTS
    # -------------------------

    def test_select_meal_saves_meal(self):
        result = mp.select_meal(self.meal)

        self.assertTrue(result["selected"])
        self.assertEqual(result["name"], "Chicken Rice Bowl")

        saved = mp._read_json(mp.selected_meals_path())
        self.assertEqual(saved, {"meals": [result]})

    def test_select_meal_does_not_change_original_meal(self):
        mp.select_meal(self.meal)

        self.assertNotIn("selected", self.meal)

    def test_select_meal_appends_to_existing_meals(self):
        second_meal = {**self.meal, "name": "Oatmeal", "meal_type": "Breakfast"}

        mp.select_meal(self.meal)
        mp.select_meal(second_meal)

        saved = mp._read_json(mp.selected_meals_path())
        self.assertEqual(
            [meal["name"] for meal in saved["meals"]],
            ["Chicken Rice Bowl", "Oatmeal"]
        )

    def test_select_meal_rejects_invalid_meal(self):
        invalid = {**self.meal, "servings": 0}

        with self.assertRaises(ValueError):
            mp.select_meal(invalid)

        self.assertFalse(mp.selected_meals_path().exists())

    def test_select_meal_rejects_corrupted_saved_meals(self):
        self.write_json(mp.selected_meals_path(), {"meals": "not a list"})

        with self.assertRaises(ValueError):
            mp.select_meal(self.meal)

    def test_select_meal_handles_saved_file_without_meals(self):
        self.write_json(mp.selected_meals_path(), {})

        mp.select_meal(self.meal)

        saved = mp._read_json(mp.selected_meals_path())
        self.assertEqual(len(saved["meals"]), 1)

    def test_select_meal_uses_session_folder(self):
        mp.select_meal(self.meal, session_id="session1")

        self.assertTrue(mp.selected_meals_path("session1").exists())
        self.assertFalse(mp.selected_meals_path().exists())

    # -------------------------
    # GENERATION TESTS
    # -------------------------

    @patch.object(mp, "_request_meals")
    @patch.object(mp, "get_targets")
    def test_generate_meal_suggestions_saves_meals(
        self, mock_targets, mock_request
    ):
        mock_targets.return_value = self.targets
        mock_request.return_value = self.valid_response

        result = mp.generate_meal_suggestions()

        mock_request.assert_called_once()
        self.assertEqual(result, self.valid_response)
        self.assertTrue(mp.suggestion_path().exists())

    @patch.object(mp, "_request_meals")
    @patch.object(mp, "get_targets")
    def test_generate_meal_suggestions_sends_correct_payload(
        self, mock_targets, mock_request
    ):
        mock_targets.return_value = self.targets
        mock_request.return_value = self.valid_response

        mp.generate_meal_suggestions(3)

        payload = mock_request.call_args.args[0]
        self.assertEqual(payload["number_of_meals"], 3)
        self.assertEqual(payload["daily_targets"], self.targets)
        self.assertEqual(payload["allergies"], ["Peanuts"])
        self.assertEqual(
            mock_request.call_args.kwargs["system_prompt"],
            mp.MEAL_GENERATION_PROMPT
        )

    @patch.object(mp, "_request_meals")
    @patch.object(mp, "get_targets")
    def test_generate_meal_suggestions_defaults_to_five(
        self, mock_targets, mock_request
    ):
        mock_targets.return_value = self.targets
        mock_request.return_value = self.valid_response

        mp.generate_meal_suggestions()

        payload = mock_request.call_args.args[0]
        self.assertEqual(payload["number_of_meals"], 5)

    @patch.object(mp, "_request_meals")
    @patch.object(mp, "get_targets")
    def test_generate_meal_suggestions_accepts_boundaries(
        self, mock_targets, mock_request
    ):
        mock_targets.return_value = self.targets
        mock_request.return_value = self.valid_response

        for number in (1, 10):
            with self.subTest(number=number):
                mp.generate_meal_suggestions(number)

        self.assertEqual(mock_request.call_count, 2)

    @patch.object(mp, "_request_meals")
    def test_generate_meal_suggestions_rejects_invalid_count(
        self, mock_request
    ):
        for number in (0, 11, -1, 5.0, "5", True, None):
            with self.subTest(number=number):
                with self.assertRaises(ValueError):
                    mp.generate_meal_suggestions(number)

        mock_request.assert_not_called()

    @patch.object(mp, "_request_meals")
    @patch.object(mp, "get_targets")
    def test_generate_meal_suggestions_uses_session(
        self, mock_targets, mock_request
    ):
        mock_targets.return_value = self.targets
        mock_request.return_value = self.valid_response

        mp.generate_meal_suggestions(session_id="user123")

        self.assertTrue(mp.suggestion_path("user123").exists())
        self.assertFalse(mp.suggestion_path().exists())

    @patch.object(mp, "_request_meals")
    @patch.object(mp, "get_targets")
    def test_generate_meal_suggestions_stops_on_invalid_context(
        self, mock_targets, mock_request
    ):
        invalid_targets = self.targets.copy()
        invalid_targets["calories"] = 0
        mock_targets.return_value = invalid_targets

        with self.assertRaises(ValueError):
            mp.generate_meal_suggestions()

        mock_request.assert_not_called()
        self.assertFalse(mp.suggestion_path().exists())

    @patch.object(mp, "_request_meals")
    @patch.object(mp, "get_targets")
    def test_failed_generation_keeps_previous_suggestions(
        self, mock_targets, mock_request
    ):
        mp._save_meals(self.valid_response)
        mock_targets.return_value = self.targets
        mock_request.side_effect = ValueError("Gemini failed")

        with self.assertRaises(ValueError):
            mp.generate_meal_suggestions()

        self.assertEqual(
            mp._read_json(mp.suggestion_path()),
            self.valid_response
        )

    # -------------------------
    # GEMINI REQUEST TESTS
    # -------------------------

    @patch.object(mp, "dotenv_values", return_value={})
    @patch.dict("os.environ", {}, clear=True)
    def test_request_meals_requires_api_key(self, mock_dotenv):
        with self.assertRaises(ValueError):
            mp._request_meals({})

    @patch.object(mp, "dotenv_values", return_value={
        "GEMINI_API_KEY": "   ",
        "GEMINI_MODEL": "test-model"
    })
    @patch.dict("os.environ", {}, clear=True)
    def test_request_meals_rejects_blank_api_key(self, mock_dotenv):
        with self.assertRaises(ValueError):
            mp._request_meals({})

    @patch.object(mp, "dotenv_values", return_value={
        "GEMINI_API_KEY": "test-key"
    })
    @patch.dict("os.environ", {}, clear=True)
    def test_request_meals_requires_model(self, mock_dotenv):
        with self.assertRaises(ValueError):
            mp._request_meals({})

    @patch.object(mp, "dotenv_values", return_value={
        "GEMINI_API_KEY": "test-key",
        "GEMINI_MODEL": "test-model"
    })
    @patch.dict("os.environ", {}, clear=True)
    @patch.object(mp.genai, "Client")
    def test_request_meals_returns_valid_response(
        self, mock_client, mock_dotenv
    ):
        client = make_client(
            mock_client, make_response(json.dumps(self.valid_response))
        )

        result = mp._request_meals({"number_of_meals": 1})

        self.assertEqual(result, self.valid_response)
        client.models.generate_content.assert_called_once()

        call = client.models.generate_content.call_args.kwargs
        self.assertEqual(call["model"], "test-model")
        self.assertEqual(
            json.loads(call["contents"]),
            {"number_of_meals": 1}
        )
        self.assertEqual(
            call["config"].system_instruction,
            mp.MEAL_GENERATION_PROMPT
        )
        mock_client.assert_called_once()
        self.assertEqual(
            mock_client.call_args.kwargs["api_key"],
            "test-key"
        )

    @patch.object(mp, "dotenv_values", return_value={
        "GEMINI_API_KEY": "file-key",
        "GEMINI_MODEL": "file-model"
    })
    @patch.dict("os.environ", {
        "GEMINI_API_KEY": "env-key",
        "GEMINI_MODEL": "env-model"
    }, clear=True)
    @patch.object(mp.genai, "Client")
    def test_request_meals_prefers_environment_variables(
        self, mock_client, mock_dotenv
    ):
        client = make_client(
            mock_client, make_response(json.dumps(self.valid_response))
        )

        mp._request_meals({})

        self.assertEqual(mock_client.call_args.kwargs["api_key"], "env-key")
        self.assertEqual(
            client.models.generate_content.call_args.kwargs["model"],
            "env-model"
        )

    @patch.object(mp, "dotenv_values", return_value={
        "GEMINI_API_KEY": "test-key",
        "GEMINI_MODEL": "test-model"
    })
    @patch.dict("os.environ", {}, clear=True)
    @patch.object(mp.genai, "Client")
    def test_request_meals_rejects_unfinished_response(
        self, mock_client, mock_dotenv
    ):
        make_client(
            mock_client,
            make_response(
                json.dumps(self.valid_response),
                types.FinishReason.MAX_TOKENS
            )
        )

        with self.assertRaises(ValueError):
            mp._request_meals({})

    @patch.object(mp, "dotenv_values", return_value={
        "GEMINI_API_KEY": "test-key",
        "GEMINI_MODEL": "test-model"
    })
    @patch.dict("os.environ", {}, clear=True)
    @patch.object(mp.genai, "Client")
    def test_request_meals_rejects_no_candidates(
        self, mock_client, mock_dotenv
    ):
        response = make_response(json.dumps(self.valid_response))
        response.candidates = []
        make_client(mock_client, response)

        with self.assertRaises(ValueError):
            mp._request_meals({})

    @patch.object(mp, "dotenv_values", return_value={
        "GEMINI_API_KEY": "test-key",
        "GEMINI_MODEL": "test-model"
    })
    @patch.dict("os.environ", {}, clear=True)
    @patch.object(mp.genai, "Client")
    def test_request_meals_rejects_invalid_json(
        self, mock_client, mock_dotenv
    ):
        make_client(mock_client, make_response("not valid json"))

        with self.assertRaises(ValueError):
            mp._request_meals({})

    @patch.object(mp, "dotenv_values", return_value={
        "GEMINI_API_KEY": "test-key",
        "GEMINI_MODEL": "test-model"
    })
    @patch.dict("os.environ", {}, clear=True)
    @patch.object(mp.genai, "Client")
    def test_request_meals_rejects_missing_text(
        self, mock_client, mock_dotenv
    ):
        make_client(mock_client, make_response(None))

        with self.assertRaises(ValueError):
            mp._request_meals({})

    @patch.object(mp, "dotenv_values", return_value={
        "GEMINI_API_KEY": "test-key",
        "GEMINI_MODEL": "test-model"
    })
    @patch.dict("os.environ", {}, clear=True)
    @patch.object(mp.genai, "Client")
    def test_request_meals_validates_returned_meals(
        self, mock_client, mock_dotenv
    ):
        invalid = self.response_with(calories=-100)
        make_client(mock_client, make_response(json.dumps(invalid)))

        with self.assertRaises(ValueError):
            mp._request_meals({})

    # -------------------------
    # SCHEMA TESTS
    # -------------------------

    def test_schema_requires_every_meal_field(self):
        meal_schema = mp.MEAL_RESPONSE_SCHEMA["properties"]["meals"]["items"]

        self.assertEqual(
            set(meal_schema["required"]),
            set(mp.MEAL_PROPERTIES)
        )
        for nutrient in mp.NUTRIENTS:
            self.assertIn(nutrient, meal_schema["required"])


if __name__ == "__main__":
    unittest.main()