import reflex as rx
import json
from pathlib import Path

from .ui import actions, entry, field, go, menu, page, press, steps

PARENT_DIR = Path(__file__).resolve().parent.parent
USER_DATA_FOLDER = PARENT_DIR / "User Data"

SEX = ["Male", "Female", "Prefer not to disclose"]
ACTIVITY_LEVELS = ["None", "Low", "Medium", "High", "Extreme"]
HEIGHT_UNITS = ["cm", "in"]
WEIGHT_UNITS = ["kg", "lb"]

class ButtonEvent(rx.State):
    sex_error: str = ""
    activity_error: str = ""
    height_error: str = ""
    weight_error: str = ""
    age_error: str = ""

    def cancel(self):
        return rx.redirect("/")

    def submit(self, form_data: dict):
        self.sex_error = ""
        self.activity_error = ""
        self.height_error = ""
        self.weight_error = ""
        self.age_error = ""

        sex = form_data.get("sex", "")
        if sex and sex not in SEX:
            self.sex_error = "Choose one of the listed options."

        activity = form_data.get("activity_level", "Low")
        if activity and activity not in ACTIVITY_LEVELS:
            self.activity_error = "Choose one of the listed options."

        # Blank measurements are optional; supplied values must be valid.
        raw_height = form_data.get("height", "")
        height = ""
        if raw_height not in (None, ""):
            try:
                height = float(raw_height)
                height_unit = form_data.get("height_unit", "cm")
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

        raw_weight = form_data.get("weight", "")
        weight = ""
        if raw_weight not in (None, ""):
            try:
                weight = float(raw_weight)
                weight_unit = form_data.get("weight_unit", "kg")
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

        raw_age = form_data.get("age", "")
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
        form_data["height"] = height
        form_data["weight"] = weight
        form_data["age"] = age

        form_data.pop("height_unit", None)
        form_data.pop("weight_unit", None)

        with open(USER_DATA_FOLDER / "user_data.json", "w", encoding="utf-8") as f:
            json.dump(form_data, f, indent=4)

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
                                default_value="Low",
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
                                    aria_invalid=ButtonEvent.height_error != "",
                                ),
                                menu(
                                    HEIGHT_UNITS,
                                    name="height_unit",
                                    default_value="cm",
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
                                    aria_invalid=ButtonEvent.weight_error != "",
                                ),
                                menu(
                                    WEIGHT_UNITS,
                                    name="weight_unit",
                                    default_value="kg",
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
