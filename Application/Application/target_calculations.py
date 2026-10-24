import reflex as rx
import json
import math
from pathlib import Path

PARENT_DIR = Path(__file__).resolve().parent.parent
USER_DATA_FOLDER = PARENT_DIR / "User Data"

# CDC measured average adult body measurements, converted to the units used
# by the target formula (kg and cm).
AVERAGE_WEIGHT_KG = {
    "male": 199.0 * 0.45359237,
    "female": 171.8 * 0.45359237,
}
AVERAGE_HEIGHT_CM = {
    "male": 68.9 * 2.54,
    "female": 63.5 * 2.54,
}
DEFAULT_WEIGHT_KG = sum(AVERAGE_WEIGHT_KG.values()) / 2
DEFAULT_HEIGHT_CM = sum(AVERAGE_HEIGHT_CM.values()) / 2
DEFAULT_AGE = 40.0
DEFAULT_ACTIVITY_LEVEL = "low"
MIN_HEIGHT_CM = 90.0
MAX_HEIGHT_CM = 250.0
MIN_WEIGHT_KG = 30.0
MAX_WEIGHT_KG = 300.0
MIN_AGE = 13.0
MAX_AGE = 120.0
MAX_CALORIES = 10_000


def _load_json(path: Path) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            value = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _bounded_number(data: dict, field: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(data.get(field, ""))
    except (TypeError, ValueError):
        return default
    if not math.isfinite(value) or not minimum <= value <= maximum:
        return default
    return value


#uses Mifflin-St Jeor Equation
def calculate_targets():
    user_data = _load_json(USER_DATA_FOLDER / "user_data.json")

    sex = str(user_data.get("sex", "")).strip().lower()
    sex_adjustment = {
        "male": 5,
        "female": -161,
    }.get(sex, -78)

    if sex in AVERAGE_WEIGHT_KG:
        default_weight = AVERAGE_WEIGHT_KG[sex]
        default_height = AVERAGE_HEIGHT_CM[sex]
    else:
        default_weight = DEFAULT_WEIGHT_KG
        default_height = DEFAULT_HEIGHT_CM

    weight = _bounded_number(user_data, "weight", default_weight, MIN_WEIGHT_KG, MAX_WEIGHT_KG)
    height = _bounded_number(user_data, "height", default_height, MIN_HEIGHT_CM, MAX_HEIGHT_CM)
    age = _bounded_number(user_data, "age", DEFAULT_AGE, MIN_AGE, MAX_AGE)

    activity_multipliers = {
        "none": 1.2,
        "low": 1.375,
        "medium": 1.55,
        "high": 1.725,
        "extreme": 1.9,
    }
    activity_level = str(
        user_data.get("activity_level", DEFAULT_ACTIVITY_LEVEL)
    ).strip().lower()
    activity_multiplier = activity_multipliers.get(
        activity_level,
        activity_multipliers[DEFAULT_ACTIVITY_LEVEL],
    )

    basal_target = (10 * weight) + (6.25 * height) - (5 * age) + sex_adjustment
    return basal_target * activity_multiplier


def calculate_macro_targets(calories: float, priority_macro: str = "") -> dict[str, float]:
    """Calculate macro grams from the calorie target and optional priority.

    The baseline uses 1.0 g protein per kg of body weight, capped so protein
    supplies at most 25% of calories. Fat supplies 30% of calories and carbs
    use the remainder. A selected priority shifts up to 10% of calories toward
    that macro, subject to per-macro caps, while keeping total calories fixed.
    """
    user_data = _load_json(USER_DATA_FOLDER / "user_data.json")
    sex = str(user_data.get("sex", "")).strip().lower()
    weight_default = AVERAGE_WEIGHT_KG.get(sex, DEFAULT_WEIGHT_KG)
    weight = _bounded_number(user_data, "weight", weight_default, MIN_WEIGHT_KG, MAX_WEIGHT_KG)

    calories = min(max(float(calories), 0.0), MAX_CALORIES)
    # Use a moderate 1.0 g/kg protein target; cap it at 25% of energy.
    protein = min(weight * 1.0, calories * 0.25 / 4)
    fat = calories * 0.30 / 9
    carbs = max(0.0, (calories - protein * 4 - fat * 9) / 4)

    # Shift up to 10% of total calories toward the selected macro, taking it
    # proportionally from the other two. Caps keep the preference moderate.
    priority = str(priority_macro).strip().lower()
    grams = {"protein": protein, "carbs": carbs, "fat": fat}
    kcal_per_gram = {"protein": 4.0, "carbs": 4.0, "fat": 9.0}
    maximum_share = {"protein": 0.40, "carbs": 0.60, "fat": 0.35}
    if priority in grams and calories > 0:
        energy = {name: grams[name] * kcal_per_gram[name] for name in grams}
        other_energy = calories - energy[priority]
        increase = min(
            calories * 0.10,
            calories * maximum_share[priority] - energy[priority],
        )
        increase = max(0.0, increase)
        if other_energy > 0 and increase > 0:
            for name in grams:
                if name != priority:
                    energy[name] -= increase * energy[name] / other_energy
            energy[priority] += increase
            grams = {name: energy[name] / kcal_per_gram[name] for name in grams}

    return grams


def _increase_protein_share(macros: dict[str, float], calories: float, share: float = 0.05) -> dict[str, float]:
    """Move a small share of calories from carbs and fat to protein."""
    if calories <= 0:
        return macros

    kcal_per_gram = {"protein": 4.0, "carbs": 4.0, "fat": 9.0}
    energy = {name: macros[name] * kcal_per_gram[name] for name in macros}
    other_energy = calories - energy["protein"]
    increase = min(calories * share, calories * 0.40 - energy["protein"])
    increase = max(0.0, increase)
    if other_energy <= 0 or increase <= 0:
        return macros

    for name in ("carbs", "fat"):
        energy[name] -= increase * energy[name] / other_energy
    energy["protein"] += increase
    return {name: energy[name] / kcal_per_gram[name] for name in macros}


def _scale_macros(macros: dict[str, float], scale: float) -> dict[str, float]:
    return {name: grams * scale for name, grams in macros.items()}





        

def _get_target_values() -> dict[str, str | float]:
    calculated_calories = calculate_targets()
    personalization = _load_json(USER_DATA_FOLDER / "user_personalization_data.json")
    manual_calories = _bounded_number(personalization, "calories", -1, 0, MAX_CALORIES)
    has_manual_target = manual_calories >= 0
    priority_macro = str(personalization.get("priority_macro", ""))
    current_goal = str(personalization.get("current_goal", "")).strip().lower()

    if has_manual_target:
        # A directly specified calorie target takes precedence over calorie adjustments.
        calorie_target = manual_calories
        macros = calculate_macro_targets(calorie_target, priority_macro)
        if current_goal in {"main gain", "muscle gain"}:
            macros = _increase_protein_share(macros, calorie_target)
            goal_description = "Your calorie target is used as entered; Main Gain modestly increases protein share."
        elif current_goal in {"weight gain", "weight loss"}:
            goal_description = "Your calorie target is used as entered; the goal's calorie adjustment is skipped."
        else:
            goal_description = "Your specified calorie target is used as entered."
    elif current_goal == "weight gain":
        calorie_target = calculated_calories + 200
        macros = _scale_macros(
            calculate_macro_targets(calculated_calories, priority_macro),
            calorie_target / calculated_calories,
        )
        goal_description = "Includes a 200-calorie daily surplus; macro proportions are preserved."
    elif current_goal == "weight loss":
        calorie_target = max(0.0, calculated_calories - 200)
        macros = _scale_macros(
            calculate_macro_targets(calculated_calories, priority_macro),
            calorie_target / calculated_calories,
        )
        goal_description = "Includes a 200-calorie daily deficit; macro proportions are preserved."
    else:
        calorie_target = calculated_calories
        macros = calculate_macro_targets(calorie_target, priority_macro)
        if current_goal in {"main gain", "muscle gain"}:
            macros = _increase_protein_share(macros, calorie_target)
            goal_description = "Stays at maintenance calories with a modest increase in protein share."
        else:
            goal_description = "Based on estimated maintenance calories."

    fiber_target = _bounded_number(personalization, "fiber", 30, 0, 100)

    calorie_copy = "Your calorie target" if has_manual_target else "Estimated daily calorie target"
    return {
        "calories": calorie_target,
        "calorie_copy": calorie_copy,
        "protein": macros["protein"],
        "carbs": macros["carbs"],
        "fat": macros["fat"],
        "fiber": fiber_target,
        "goal_description": goal_description,
    }


class TargetState(rx.State):
    calories: str = "0"
    calorie_copy: str = ""
    protein: str = "0"
    carbs: str = "0"
    fat: str = "0"
    fiber: str = "30"
    goal_description: str = ""

    @rx.event
    def load_targets(self):
        values = _get_target_values()
        self.calories = f"{float(values['calories']):.0f}"
        self.calorie_copy = str(values["calorie_copy"])
        self.protein = f"{float(values['protein']):.0f}"
        self.carbs = f"{float(values['carbs']):.0f}"
        self.fat = f"{float(values['fat']):.0f}"
        self.fiber = f"{float(values['fiber']):.0f}"
        self.goal_description = str(values["goal_description"])


def targets() -> rx.Component:
    result = rx.vstack(
        rx.text(TargetState.calorie_copy, ": ", TargetState.calories, " calories per day.", size="5"),
        rx.heading("Daily macro and fiber targets", size="6"),
        rx.text("Protein: ", TargetState.protein, " g"),
        rx.text("Carbohydrates: ", TargetState.carbs, " g"),
        rx.text("Fat: ", TargetState.fat, " g"),
        rx.text("Fiber: ", TargetState.fiber, " g"),
        rx.text(TargetState.goal_description, size="3"),
        align="center",
        spacing="2",
    )
    navigation = rx.hstack(
        rx.link(rx.button("Back"), href="/personalize"),
        rx.link(rx.button("Home"), href="/"),
        spacing="4",
    )

    return rx.container(
        rx.color_mode.button(position="top-right"),
        rx.vstack(
            rx.heading("Nutritional Targets", size="9"),
            result,
            navigation,
            spacing="5",
            justify="center",
            min_height="85vh",
        ),
    )
