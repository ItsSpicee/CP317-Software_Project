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


#uses Mifflin-St Jeor Equation
def calculate_targets():
    try:
        with open(USER_DATA_FOLDER / "user_data.json", "r", encoding="utf-8") as f:
            user_data = json.load(f)
    except (OSError, json.JSONDecodeError):
        user_data = {}

    if not isinstance(user_data, dict):
        user_data = {}

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

    def get_positive_number(field: str, default: float) -> float:
        try:
            value = float(user_data.get(field, ""))
        except (TypeError, ValueError):
            return default
        return value if math.isfinite(value) and value > 0 else default

    weight = get_positive_number("weight", default_weight)
    height = get_positive_number("height", default_height)
    age = get_positive_number("age", DEFAULT_AGE)

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





        

def targets() -> rx.Component:
    target = calculate_targets()
    if target is None:
        result = rx.text(
            "Complete your profile to see your nutritional targets.",
            size="5",
        )
        next_step = rx.link(rx.button("Complete Profile"), href="/onboarding")
    else:
        result = rx.text(
            "We calculated your nutritional targets to be: ",
            f"{target:.0f}",
            " calories per day.",
            size="5",
        )
        next_step = rx.link(rx.button("Home"), href="/")

    return rx.container(
        rx.color_mode.button(position="top-right"),
        rx.vstack(
            rx.heading("Nutritional Targets", size="9"),
            result,
            next_step,
            spacing="5",
            justify="center",
            min_height="85vh",
        ),
    )
