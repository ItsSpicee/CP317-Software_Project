"""Intake charts from meals made today and daily nutrition targets."""

import json
import math

import reflex as rx

from . import meal_planner as planner
from .target_calculations import _get_target_values

MACRO_KEYS = ("protein", "carbs", "fat", "fiber", "calories")


class State(rx.State):
    """The app state."""


def _ring_progress(intake: float, goal: float) -> str:
    """0–1 fill ratio for SVG rings; caps visually at 100%."""
    if goal <= 0:
        return "0"
    return f"{min(1.0, intake / goal):.4f}"


def _made_macro_intake(session_id: str) -> dict[str, float]:
    """Sum nutrition from meals made today; missing history means zero."""
    totals = {key: 0.0 for key in MACRO_KEYS}
    try:
        data = {"meals": planner.get_made_meals(session_id)}
    except (OSError, ValueError, json.JSONDecodeError):
        return totals

    meals = data.get("meals", [])
    if not isinstance(meals, list):
        return totals

    for meal in meals:
        if not isinstance(meal, dict):
            continue
        for key in MACRO_KEYS:
            try:
                amount = float(meal.get(key, 0))
            except (TypeError, ValueError):
                continue
            if math.isfinite(amount) and amount > 0:
                totals[key] += amount
    return totals


class MacroIntakeState(rx.State):
    """Home nutrition totals from targets and today's dated meal record."""

    calories: str = "0"
    calorie_goal: str = "0"
    calorie_figure: str = "0 / 0 kcal"
    calorie_left: str = "0 kcal left"
    protein_progress: str = "0"
    protein_figure: str = "0 / 0 g"
    protein_left: str = "0 g left"
    carbs_progress: str = "0"
    carbs_figure: str = "0 / 0 g"
    carbs_left: str = "0 g left"
    fat_progress: str = "0"
    fat_figure: str = "0 / 0 g"
    fat_left: str = "0 g left"
    fiber_progress: str = "0"
    fiber_figure: str = "0 / 0 g"
    fiber_left: str = "0 g left"

    @rx.event
    def load_intake(self):
        # Use the Targets page's loader, including defaults for skipped setup.
        values = _get_target_values()
        intake = _made_macro_intake(self.rx_router_session.client_token or "")

        calorie_goal = max(0.0, float(values["calories"]))
        protein_goal = max(0.0, float(values["protein"]))
        carbs_goal = max(0.0, float(values["carbs"]))
        fat_goal = max(0.0, float(values["fat"]))
        fiber_goal = max(0.0, float(values["fiber"]))

        self.calories = f"{calorie_goal:,.0f}"
        self.calorie_goal = f"{calorie_goal:,.0f}"
        self.calorie_figure = f'{intake["calories"]:,.0f} / {calorie_goal:,.0f} kcal from meals made'
        self.calorie_left = f'{max(0.0, calorie_goal - intake["calories"]):,.0f} kcal left'

        self.protein_progress = _ring_progress(intake["protein"], protein_goal)
        self.protein_figure = f'{intake["protein"]:.0f} / {protein_goal:.0f} g'
        self.protein_left = f'{max(0.0, protein_goal - intake["protein"]):.0f} g left'

        self.carbs_progress = _ring_progress(intake["carbs"], carbs_goal)
        self.carbs_figure = f'{intake["carbs"]:.0f} / {carbs_goal:.0f} g'
        self.carbs_left = f'{max(0.0, carbs_goal - intake["carbs"]):.0f} g left'

        self.fat_progress = _ring_progress(intake["fat"], fat_goal)
        self.fat_figure = f'{intake["fat"]:.0f} / {fat_goal:.0f} g'
        self.fat_left = f'{max(0.0, fat_goal - intake["fat"]):.0f} g left'

        self.fiber_progress = _ring_progress(intake["fiber"], fiber_goal)
        self.fiber_figure = f'{intake["fiber"]:.0f} / {fiber_goal:.0f} g'
        self.fiber_left = f'{max(0.0, fiber_goal - intake["fiber"]):.0f} g left'

