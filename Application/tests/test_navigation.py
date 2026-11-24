"""Setup ordering, editing, and destructive reset use isolated prototype data."""

import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from Application import get_targets, grocery_planner, meal_planner, navigation, onboarding, personalize
from Application.grocery import GroceryState
from Application.intake import MacroIntakeState
from Application.inventory_page import InventoryState
from Application.meals import MealState
from Application.target_calculations import TargetState


def redirect_path(event):
    return str(dict((str(key), value) for key, value in event.args)["path"]).strip('"')


class NavigationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        for module in (navigation, onboarding, personalize, get_targets, grocery_planner, meal_planner):
            patcher = patch.object(module, "USER_DATA_FOLDER", self.folder)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.nav = navigation.NavigationState(_reflex_internal_init=True)

    def write(self, name, data):
        path = self.folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")

    def test_setup_must_finish_before_entering_menu(self):
        for handler in (navigation.NavigationState.guard_menu, navigation.NavigationState.guard_preferences,
                        navigation.NavigationState.guard_targets, navigation.NavigationState.finish):
            self.assertEqual(redirect_path(handler.fn(self.nav)), "/onboarding")
        navigation.NavigationState.profile_saved.fn(self.nav)
        self.assertEqual(redirect_path(navigation.NavigationState.guard_menu.fn(self.nav)), "/personalize")
        navigation.NavigationState.preferences_saved.fn(self.nav)
        self.assertEqual(redirect_path(navigation.NavigationState.guard_menu.fn(self.nav)), "/setup-targets")
        self.assertEqual(redirect_path(navigation.NavigationState.finish.fn(self.nav)), "/overview")
        self.assertTrue(self.nav.complete)
        self.assertIsNone(navigation.NavigationState.guard_menu.fn(self.nav))
        self.assertEqual(redirect_path(navigation.NavigationState.start.fn(self.nav)), "/overview")

    def test_feature_routes_use_setup_guard(self):
        from Application.Application import app

        for route in ("overview", "profile", "preferences", "targets", "groceries", "inventory", "meals", "tracking", "progress", "settings"):
            on_load = app._unevaluated_pages[route].on_load
            first = on_load[0] if isinstance(on_load, list) else on_load
            self.assertIs(first.fn, navigation.NavigationState.guard_menu.fn)

    def test_entrypoint_and_setup_routes_are_connected(self):
        from Application.Application import app

        pages = app._unevaluated_pages
        self.assertIs(pages["index"].on_load.fn, navigation.NavigationState.start.fn)
        expected = {
            "onboarding": (navigation.NavigationState.guard_profile, onboarding.ButtonEvent.load_setup),
            "personalize": (navigation.NavigationState.guard_preferences, personalize.PersonalizationState.load_setup),
            "setup-targets": (navigation.NavigationState.guard_targets, TargetState.load_targets),
        }
        for route, handlers in expected.items():
            self.assertEqual([event.fn for event in pages[route].on_load], [event.fn for event in handlers])

    def test_intro_waits_for_get_started(self):
        from Application.Application import index

        self.assertIsNone(navigation.NavigationState.start.fn(self.nav))
        intro = str(index())
        self.assertIn("Get Started", intro)
        self.assertIn("/onboarding", intro)
        self.assertNotIn("ns-sidebar", intro)
        self.assertFalse(self.nav.initialized)

    def test_fresh_session_starts_with_blank_data_only_once(self):
        self.write("user_data.json", {"age": 50})
        navigation.NavigationState.guard_profile.fn(self.nav)
        self.assertFalse((self.folder / "user_data.json").exists())
        self.write("user_data.json", {"age": 30})
        navigation.NavigationState.guard_profile.fn(self.nav)
        self.assertTrue((self.folder / "user_data.json").exists())

    def test_edit_profile_loads_saved_values_and_updates_targets(self):
        self.write("user_data.json", {"sex": "Male", "height": 180, "weight": 75, "age": 30, "activity_level": "Low"})
        self.write("user_personalization_data.json", {})
        before = get_targets.get_targets()["calories"]
        state = onboarding.ButtonEvent(_reflex_internal_init=True)
        onboarding.ButtonEvent.load_editor.fn(state)
        self.assertTrue(state.editing)
        self.assertEqual(state.weight, "75")
        self.write("sessions/test/meal_suggestions.json", {"meals": []})
        result = onboarding.ButtonEvent.submit.fn(state, {"weight": "90"})
        self.assertEqual(redirect_path(result), "/overview")
        self.assertGreater(get_targets.get_targets()["calories"], before)
        self.assertFalse((self.folder / "sessions/test/meal_suggestions.json").exists())

    def test_edit_preferences_restores_values_and_recalculates(self):
        self.write("user_data.json", {})
        self.write("user_personalization_data.json", {"calories": 2000, "fiber": 42, "allergies": ["Milk"], "diet_types": ["Vegetarian"]})
        state = personalize.PersonalizationState(_reflex_internal_init=True)
        personalize.PersonalizationState.load_editor.fn(state)
        self.assertEqual(state.calories, "2000")
        self.assertEqual(state.allergies, ["Milk"])
        self.assertEqual(state.diet_types, ["Vegetarian"])
        self.assertEqual(state.fiber, 42)
        result = personalize.PersonalizationState.submit.fn(state, {"calories": "2400"})
        self.assertEqual(redirect_path(result), "/overview")
        self.assertEqual(get_targets.get_targets()["calories"], 2400)

    def test_reset_clears_all_json_and_screen_states(self):
        for name in ("inventory.json", "user_data.json", "user_personalization_data.json", "weekly_suggestion.json",
                     "weekly_grocery_inventory.json", "meal_suggestions.json", "selected_meals.json",
                     "sessions/browser-a/meal_suggestions.json", "sessions/browser-b/weekly_suggestion.json"):
            self.write(name, {})
        (self.folder / "keep.txt").write_text("keep", encoding="utf-8")
        states = {cls: cls(_reflex_internal_init=True) for cls in (
            onboarding.ButtonEvent, personalize.PersonalizationState, TargetState, GroceryState, MealState, MacroIntakeState, InventoryState)}
        states[InventoryState].selected = "Rice"
        states[InventoryState].rows = [{"name": "Rice"}]
        states[MealState]._meals = [{"name": "old meal"}]
        states[GroceryState].has_plan = True
        self.nav.complete = True
        self.nav.setup_step = 3
        fake = SimpleNamespace(complete=True, reset_confirmation=True, reset_error="", initialized=True,
                               get_state=AsyncMock(side_effect=lambda cls: states[cls]), reset=self.nav.reset)
        result = asyncio.run(navigation.NavigationState.reset_profile.fn(fake))
        self.assertEqual(redirect_path(result), "/")
        self.assertFalse(list(self.folder.rglob("*.json")))
        self.assertTrue((self.folder / "keep.txt").exists())
        self.assertFalse(states[GroceryState].has_plan)
        self.assertEqual(states[MealState]._meals, [])
        self.assertEqual(states[InventoryState].rows, [])
        self.assertEqual(states[InventoryState].selected, "")
        self.assertFalse(self.nav.complete)

    def test_reset_requires_confirmation(self):
        self.write("user_data.json", {"age": 25})
        fake = SimpleNamespace(complete=True, reset_confirmation=False)
        self.assertIsNone(asyncio.run(navigation.NavigationState.reset_profile.fn(fake)))
        self.assertTrue((self.folder / "user_data.json").exists())

    def test_reset_waits_for_inflight_requests(self):
        self.write("user_data.json", {"age": 25})
        groceries = SimpleNamespace(busy=True)
        meals = SimpleNamespace(busy=False)
        fake = SimpleNamespace(complete=True, reset_confirmation=True, reset_error="",
                               get_state=AsyncMock(side_effect=[groceries, meals]))
        self.assertIsNone(asyncio.run(navigation.NavigationState.reset_profile.fn(fake)))
        self.assertTrue((self.folder / "user_data.json").exists())
        self.assertIn("Wait", fake.reset_error)


if __name__ == "__main__":
    unittest.main()
