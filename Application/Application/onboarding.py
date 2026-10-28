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

    def cancel(self):
        return rx.redirect("/")

    def submit(self, form_data: dict):
        # Store height and weight in metric units for the rest of the app.
        try:
            height = float(form_data.get("height", ""))
            if form_data.get("height_unit", "cm") == "in":
                height *= 2.54
            if not 90 <= height <= 250:
                height = ""
        except (TypeError, ValueError):
            height = ""
        form_data["height"] = height

        try:
            weight = float(form_data.get("weight", ""))
            if form_data.get("weight_unit", "kg") == "lb":
                weight *= 0.45359237
            if not 30 <= weight <= 300:
                weight = ""
        except (TypeError, ValueError):
            weight = ""
        form_data["weight"] = weight

        try:
            age = float(form_data.get("age", ""))
            if not 13 <= age <= 120:
                age = ""
        except (TypeError, ValueError):
            age = ""
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
                            menu(SEX, name="sex", id="sex", placeholder="Select"),
                            for_id="sex",
                        ),
                        field(
                            "Activity",
                            menu(
                                ACTIVITY_LEVELS,
                                name="activity_level",
                                id="activity_level",
                                default_value="Low",
                            ),
                            "Low is the default.",
                            for_id="activity_level",
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
                        ),
                        "13–120 years.",
                        for_id="age",
                        class_name="ns-field-half",
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
            ),
            class_name="ns-sheet",
        ),
        current="profile",
    )
