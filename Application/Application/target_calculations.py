import math

import reflex as rx

from . import get_targets as nutrition
from .ui import actions, energy_bar, go, macro_line, page, steps


def _energy_shares(macros: dict[str, float]) -> dict[str, int]:
    energy = {
        "protein": max(float(macros["protein"]), 0.0) * 4,
        "carbs": max(float(macros["carbs"]), 0.0) * 4,
        "fat": max(float(macros["fat"]), 0.0) * 9,
    }
    total = sum(energy.values())
    if total <= 0:
        return {name: 0 for name in energy}
    shares = {name: int(round(amount / total * 100)) for name, amount in energy.items()}
    drift = 100 - sum(shares.values())
    if drift:
        largest = max(shares, key=shares.get)
        shares[largest] += drift
    return shares


def _profile_line(user_data: dict) -> str:
    parts: list[str] = []
    sex = str(user_data.get("sex", "")).strip()
    if sex:
        parts.append(sex)
    try:
        age = float(user_data.get("age", ""))
        if math.isfinite(age) and nutrition.MIN_AGE <= age <= nutrition.MAX_AGE:
            parts.append(f"{age:.0f} years")
    except (TypeError, ValueError):
        pass
    activity = str(user_data.get("activity_level", "")).strip()
    if activity:
        parts.append(f"{activity} activity")
    return " · ".join(parts)


def _detail_line(personalization: dict) -> str:
    parts: list[str] = []
    goal = str(personalization.get("current_goal", "Maintenance")).strip()
    if goal:
        parts.append(goal)
    muscle_gain = personalization.get("muscle_gain", False)
    if muscle_gain:
        parts.append("Muscle Gain")
    return " · ".join(parts)


def _get_target_values() -> dict[str, str | float]:
    user_data = nutrition._load_json(nutrition.USER_DATA_FOLDER / "user_data.json")
    personalization = nutrition._load_json(
        nutrition.USER_DATA_FOLDER / "user_personalization_data.json"
    )
    values = nutrition.get_targets(user_data, personalization)
    shares = _energy_shares(values)

    return {
        "calories": values["calories"],
        "calorie_copy": (
            "Your calorie target" if values["has_manual_target"]
            else "Estimated daily calorie target"
        ),
        "protein": values["protein"],
        "carbs": values["carbs"],
        "fat": values["fat"],
        "fiber": values["fiber"],
        "goal_description": values["goal_description"],
        "protein_width": f"{shares['protein']}%",
        "carbs_width": f"{shares['carbs']}%",
        "fat_width": f"{shares['fat']}%",
        "protein_note": f"{shares['protein']}% of calories",
        "carbs_note": f"{shares['carbs']}% of calories",
        "fat_note": f"{shares['fat']}% of calories",
        "profile_line": _profile_line(user_data),
        "detail_line": _detail_line(personalization),
    }


class TargetState(rx.State):
    calories: str = "0"
    calorie_copy: str = ""
    protein: str = "0 g"
    carbs: str = "0 g"
    fat: str = "0 g"
    fiber: str = "30 g"
    protein_note: str = ""
    carbs_note: str = ""
    fat_note: str = ""
    protein_width: str = "0%"
    carbs_width: str = "0%"
    fat_width: str = "0%"
    goal_description: str = ""
    profile_line: str = ""
    detail_line: str = ""

    @rx.event
    def load_targets(self):
        values = _get_target_values()
        self.calories = f"{float(values['calories']):,.0f}"
        self.calorie_copy = str(values["calorie_copy"])
        self.protein = f"{float(values['protein']):.0f} g"
        self.carbs = f"{float(values['carbs']):.0f} g"
        self.fat = f"{float(values['fat']):.0f} g"
        self.fiber = f"{float(values['fiber']):.0f} g"
        self.protein_note = str(values["protein_note"])
        self.carbs_note = str(values["carbs_note"])
        self.fat_note = str(values["fat_note"])
        self.protein_width = str(values["protein_width"])
        self.carbs_width = str(values["carbs_width"])
        self.fat_width = str(values["fat_width"])
        self.goal_description = str(values["goal_description"])
        self.profile_line = str(values["profile_line"])
        self.detail_line = str(values["detail_line"])


def targets() -> rx.Component:
    return page(
        rx.el.div(
            steps(3),
            rx.el.p("Step 3", class_name="ns-kicker"),
            rx.el.h1("Your targets", class_name="ns-title"),
            rx.el.p(TargetState.calories, class_name="ns-calorie"),
            rx.el.p("kcal / day", class_name="ns-unit-label"),
            rx.el.p(TargetState.calorie_copy, class_name="ns-lede ns-lede-tight"),
            rx.cond(
                TargetState.profile_line != "",
                rx.el.p(TargetState.profile_line, class_name="ns-meta"),
            ),
            rx.cond(
                TargetState.detail_line != "",
                rx.el.p(TargetState.detail_line, class_name="ns-meta"),
            ),
            energy_bar(
                TargetState.protein_width,
                TargetState.carbs_width,
                TargetState.fat_width,
            ),
            rx.el.div(
                macro_line("Protein", TargetState.protein, TargetState.protein_note, "ns-p"),
                macro_line("Carbohydrates", TargetState.carbs, TargetState.carbs_note, "ns-c"),
                macro_line("Fat", TargetState.fat, TargetState.fat_note, "ns-f"),
                macro_line("Fiber", TargetState.fiber, "Selected", "ns-fiber"),
                class_name="ns-macro-list",
            ),
            rx.el.div(
                rx.el.p(TargetState.goal_description),
                class_name="ns-callout",
            ),
            actions(
                [go("Back", "/personalize")],
                [go("Home", "/", "primary")],
            ),
            class_name="ns-sheet ns-sheet-narrow",
        ),
        current="targets",
    )
