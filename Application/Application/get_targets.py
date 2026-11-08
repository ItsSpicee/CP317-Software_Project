"""Daily nutrition targets, independent of Reflex and page formatting."""

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
def calculate_targets(user_data: dict | None = None) -> float:
    """Estimate maintenance calories from a profile or the saved profile."""
    if user_data is None:
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


def calculate_macro_targets(calories: float, user_data: dict | None = None) -> dict[str, float]:
    """Calculate baseline macro grams from the calorie target.

    The baseline uses 1.0 g protein per kg of body weight, capped so protein
    supplies at most 25% of calories. Fat supplies 30% of calories and carbs
    use the remainder. The optional Muscle Gain preference is applied later,
    independently of the calorie goal.
    """
    if user_data is None:
        user_data = _load_json(USER_DATA_FOLDER / "user_data.json")
    sex = str(user_data.get("sex", "")).strip().lower()
    weight_default = AVERAGE_WEIGHT_KG.get(sex, DEFAULT_WEIGHT_KG)
    weight = _bounded_number(user_data, "weight", weight_default, MIN_WEIGHT_KG, MAX_WEIGHT_KG)

    calories = min(max(float(calories), 0.0), MAX_CALORIES)
    # Use a moderate 1.0 g/kg protein target; cap it at 25% of energy.
    protein = min(weight * 1.0, calories * 0.25 / 4)
    fat = calories * 0.30 / 9
    carbs = max(0.0, (calories - protein * 4 - fat * 9) / 4)
    return {"protein": protein, "carbs": carbs, "fat": fat}


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


def get_targets(
    user_data: dict | None = None,
    personalization: dict | None = None,
) -> dict[str, float | bool | str]:
    """Return unrounded daily targets and the applied goal description.

    Supply dictionaries to calculate from an in-memory snapshot. Omitted
    arguments are loaded from their existing files in User Data.
    """
    if user_data is None:
        user_data = _load_json(USER_DATA_FOLDER / "user_data.json")
    if personalization is None:
        personalization = _load_json(USER_DATA_FOLDER / "user_personalization_data.json")
    calculated_calories = calculate_targets(user_data)
    manual_calories = _bounded_number(personalization, "calories", -1, 0, MAX_CALORIES)
    has_manual_target = manual_calories >= 0
    current_goal = str(personalization.get("current_goal", "Maintenance")).strip().lower()
    muscle_gain = personalization.get("muscle_gain", False)
    if current_goal not in {"maintenance", "weight gain", "weight loss"}:
        current_goal = "maintenance"

    if has_manual_target:
        # A directly specified calorie target takes precedence over calorie adjustments.
        calorie_target = manual_calories
        macros = calculate_macro_targets(calorie_target, user_data)
        if muscle_gain:
            macros = _increase_protein_share(macros, calorie_target)
        goal_description = "Your calorie target is used as entered."
        if current_goal in {"weight gain", "weight loss"}:
            goal_description += " The selected calorie adjustment is skipped."
    else:
        calorie_target = calculated_calories
        macros = calculate_macro_targets(calculated_calories, user_data)
        if muscle_gain:
            macros = _increase_protein_share(macros, calorie_target)
        if current_goal == "weight gain":
            calorie_target += 200
            macros = _scale_macros(macros, calorie_target / calculated_calories)
            goal_description = "Includes a 200-calorie daily surplus; macro proportions are preserved."
        elif current_goal == "weight loss":
            calorie_target = max(0.0, calculated_calories - 200)
            macros = _scale_macros(macros, calorie_target / calculated_calories)
            goal_description = "Includes a 200-calorie daily deficit; macro proportions are preserved."
        else:
            goal_description = "Based on estimated maintenance calories."

    if muscle_gain:
        goal_description += " Muscle Gain modestly increases protein share."

    fiber_target = _bounded_number(personalization, "fiber", 30, 0, 100)
    return {
        "calories": calorie_target,
        "protein": macros["protein"],
        "carbs": macros["carbs"],
        "fat": macros["fat"],
        "fiber": fiber_target,
        "has_manual_target": has_manual_target,
        "goal_description": goal_description,
    }
