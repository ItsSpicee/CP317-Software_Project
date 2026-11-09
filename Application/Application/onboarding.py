import json
import math
from pathlib import Path

import reflex as rx

from .grocery_planner import invalidate_weekly_plan
from .ui import actions, entry, field, go, menu, page, press, steps

PARENT_DIR = Path(__file__).resolve().parent.parent
USER_DATA_FOLDER = PARENT_DIR / "User Data"

SEX = ["Male", "Female", "Prefer not to disclose"]
ACTIVITY_LEVELS = ["None", "Low", "Medium", "High", "Extreme"]
HEIGHT_UNITS = ["cm", "in"]
WEIGHT_UNITS = ["kg", "lb"]


def _format_number(value) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if not math.isfinite(number):
        return ""
    if number.is_integer():
        return str(int(number))
    return f"{number:g}"


class ButtonEvent(rx.State):
    sex: str = ""
    activity_level: str = "Low"
    height: str = ""
    height_unit: str = "cm"
    weight: str = ""
    weight_unit: str = "kg"
    age: str = ""
    sex_error: str = ""
    activity_error: str = ""
    height_error: str = ""
    weight_error: str = ""
    age_error: str = ""

    @rx.event
    def load_saved_profile(self):
        try:
            with open(USER_DATA_FOLDER / "user_data.json", "r", encoding="utf-8") as f:
                saved = json.load(f)
        except (OSError, json.JSONDecodeError):
            saved = {}
        if not isinstance(saved, dict):
            saved = {}

        sex = str(saved.get("sex", "") or "")
        self.sex = sex if sex in SEX else ""

        activity = str(saved.get("activity_level", "Low") or "Low")
        self.activity_level = activity if activity in ACTIVITY_LEVELS else "Low"

        self.height = _format_number(saved.get("height", ""))
        self.height_unit = "cm"
        self.weight = _format_number(saved.get("weight", ""))
        self.weight_unit = "kg"
        self.age = _format_number(saved.get("age", ""))

        self.sex_error = ""
        self.activity_error = ""
        self.height_error = ""
        self.weight_error = ""
        self.age_error = ""

    @rx.event
    def set_sex(self, value: str):
        self.sex = value

    @rx.event
    def set_activity_level(self, value: str):
        self.activity_level = value

    @rx.event
    def set_height(self, value: str):
        self.height = value

    @rx.event
    def set_height_unit(self, value: str):
        self.height_unit = value

    @rx.event
    def set_weight(self, value: str):
        self.weight = value

    @rx.event
    def set_weight_unit(self, value: str):
        self.weight_unit = value

    @rx.event
    def set_age(self, value: str):
        self.age = value

    @rx.event
    def cancel(self):
        return rx.redirect("/")

    @rx.event
    def submit(self, form_data: dict):
        self.sex_error = ""
        self.activity_error = ""
        self.height_error = ""
        self.weight_error = ""
        self.age_error = ""

        sex = form_data.get("sex", self.sex) or self.sex
        if sex and sex not in SEX:
            self.sex_error = "Choose one of the listed options."

        activity = form_data.get("activity_level", self.activity_level) or self.activity_level or "Low"
        if activity and activity not in ACTIVITY_LEVELS:
            self.activity_error = "Choose one of the listed options."

        # Blank measurements are optional; supplied values must be valid.
        raw_height = form_data.get("height", self.height)
        height = ""
        if raw_height not in (None, ""):
            try:
                height = float(raw_height)
                height_unit = form_data.get("height_unit", self.height_unit) or self.height_unit
                if height_unit not in HEIGHT_UNITS:
                    self.height_error = "Choose cm or in for the height unit."
                elif height_unit == "in":
                    height *= 2.54
                if not self.height_error and not 90 <= height <= 250:
                    self.height_error = "Enter a height from 90 to 250 cm after conversion."
            except (TypeError, ValueError):
                self.height_error = "Enter a valid height, or leave it blank."
            if self.height_error:
                height = ""

        raw_weight = form_data.get("weight", self.weight)
        weight = ""
        if raw_weight not in (None, ""):
            try:
                weight = float(raw_weight)
                weight_unit = form_data.get("weight_unit", self.weight_unit) or self.weight_unit
                if weight_unit not in WEIGHT_UNITS:
                    self.weight_error = "Choose kg or lb for the weight unit."
                elif weight_unit == "lb":
                    weight *= 0.45359237
                if not self.weight_error and not 30 <= weight <= 300:
                    self.weight_error = "Enter a weight from 30 to 300 kg after conversion."
            except (TypeError, ValueError):
                self.weight_error = "Enter a valid weight, or leave it blank."
            if self.weight_error:
                weight = ""

        raw_age = form_data.get("age", self.age)
        age = ""
        if raw_age not in (None, ""):
            try:
                age = float(raw_age)
                if not 13 <= age <= 120 or not age.is_integer():
                    self.age_error = "Enter an age from 13 to 120, or leave it blank."
            except (TypeError, ValueError):
                self.age_error = "Enter a valid age, or leave it blank."
            if self.age_error:
                age = ""

        if any((self.sex_error, self.activity_error, self.height_error, self.weight_error, self.age_error)):
            return

        # Store height and weight in metric units for the rest of the app.
        payload = {
            "sex": sex,
            "activity_level": activity,
            "height": height,
            "weight": weight,
            "age": age,
        }

        profile_path = USER_DATA_FOLDER / "user_data.json"
        try:
            previous = json.loads(profile_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            previous = None
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4)
        if previous != payload:
            invalidate_weekly_plan()

        self.sex = sex if sex in SEX else ""
        self.activity_level = activity if activity in ACTIVITY_LEVELS else "Low"
        self.height = _format_number(height)
        self.height_unit = "cm"
        self.weight = _format_number(weight)
        self.weight_unit = "kg"
        self.age = _format_number(age)

        # Redirect after processing the submitted data.
        return rx.redirect("/personalize")


def onboarding() -> rx.Component:
    return page(
        rx.el.div(
            steps(1),
            rx.el.p("Step 1", class_name="ns-kicker"),
            rx.el.h1("About you", class_name="ns-title"),
            rx.el.p(
                "Sex, age, size, and activity set the maintenance estimate. Leave something blank and a typical adult value is used.",
                class_name="ns-lede",
            ),
            rx.form(
                rx.el.div(
                    rx.el.div(
                        field(
                            "Sex",
                            menu(
                                SEX,
                                name="sex",
                                id="sex",
                                value=ButtonEvent.sex,
                                on_change=ButtonEvent.set_sex,
                                placeholder="Select",
                                aria_invalid=ButtonEvent.sex_error != "",
                            ),
                            for_id="sex",
                            error=ButtonEvent.sex_error,
                        ),
                        field(
                            "Activity",
                            menu(
                                ACTIVITY_LEVELS,
                                name="activity_level",
                                id="activity_level",
                                value=ButtonEvent.activity_level,
                                on_change=ButtonEvent.set_activity_level,
                                aria_invalid=ButtonEvent.activity_error != "",
                            ),
                            "Low is the default.",
                            for_id="activity_level",
                            error=ButtonEvent.activity_error,
                        ),
                        class_name="ns-row",
                    ),
                    rx.el.div(
                        field(
                            "Height",
                            rx.el.div(
                                entry(
                                    name="height",
                                    id="height",
                                    type="number",
                                    min=35,
                                    max=250,
                                    step="any",
                                    value=ButtonEvent.height,
                                    on_change=ButtonEvent.set_height,
                                    aria_invalid=ButtonEvent.height_error != "",
                                ),
                                menu(
                                    HEIGHT_UNITS,
                                    name="height_unit",
                                    value=ButtonEvent.height_unit,
                                    on_change=ButtonEvent.set_height_unit,
                                    custom_attrs={"aria-label": "Height unit"},
                                ),
                                class_name="ns-unit",
                            ),
                            "90–250 cm after conversion.",
                            for_id="height",
                            error=ButtonEvent.height_error,
                        ),
                        field(
                            "Weight",
                            rx.el.div(
                                entry(
                                    name="weight",
                                    id="weight",
                                    type="number",
                                    min=30,
                                    max=660,
                                    step="any",
                                    value=ButtonEvent.weight,
                                    on_change=ButtonEvent.set_weight,
                                    aria_invalid=ButtonEvent.weight_error != "",
                                ),
                                menu(
                                    WEIGHT_UNITS,
                                    name="weight_unit",
                                    value=ButtonEvent.weight_unit,
                                    on_change=ButtonEvent.set_weight_unit,
                                    custom_attrs={"aria-label": "Weight unit"},
                                ),
                                class_name="ns-unit",
                            ),
                            "30–300 kg after conversion.",
                            for_id="weight",
                            error=ButtonEvent.weight_error,
                        ),
                        class_name="ns-row",
                    ),
                    field(
                        "Age",
                        entry(
                            name="age",
                            id="age",
                            type="number",
                            min=13,
                            max=120,
                            step=1,
                            value=ButtonEvent.age,
                            on_change=ButtonEvent.set_age,
                            aria_invalid=ButtonEvent.age_error != "",
                        ),
                        "13–120 years.",
                        for_id="age",
                        class_name="ns-field-half",
                        error=ButtonEvent.age_error,
                    ),
                    actions(
                        [
                            go("Back", "/"),
                            press("Cancel", "ghost", type="button", on_click=ButtonEvent.cancel),
                        ],
                        [
                            press("Skip", "secondary", type="submit"),
                            press("Submit", "primary", type="submit"),
                        ],
                    ),
                    class_name="ns-stack",
                ),
                on_submit=ButtonEvent.submit,
                no_validate=True,
            ),
            class_name="ns-sheet",
        ),
        current="profile",
    )
