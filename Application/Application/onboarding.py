import reflex as rx
import json
from pathlib import Path

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
    return rx.container(
        rx.color_mode.button(position="top-right"),

        rx.form(
            rx.vstack(
                # Keep your original horizontal layout.
                rx.flex(
                    rx.vstack(
                        rx.heading("Welcome to NutriSpoke!", size="8"),
                        rx.text("Tell us a little bit about yourself."),
                        spacing="5",
                        justify="center",
                        min_height="85vh",
                    ),
                    rx.separator(
                        orientation = "vertical",
                        size = "4",
                        height = "45vh"
                    ),
                    rx.vstack(
                        rx.heading("Your information:", size="8"),
                        rx.flex(
                            rx.select(
                                SEX,
                                name="sex",
                                placeholder="Sex",
                            ),
                            rx.select(
                                ACTIVITY_LEVELS,
                                name="activity_level",
                                default_value="Low",
                                placeholder="Activity Level",
                            ),
                            rx.hstack(
                                rx.input(
                                    name="height", placeholder="Height", type="number",
                                    min=35, max=250, step="any",
                                ),
                                rx.select(
                                    HEIGHT_UNITS,
                                    name="height_unit",
                                    default_value="cm",
                                    width="80px",
                                ),
                            ),
                            rx.hstack(
                                rx.input(
                                    name="weight", placeholder="Weight", type="number",
                                    min=30, max=660, step="any",
                                ),
                                rx.select(
                                    WEIGHT_UNITS,
                                    name="weight_unit",
                                    default_value="kg",
                                    width="80px",
                                ),
                            ),
                            rx.input(
                                name="age",
                                placeholder="Age",
                                type="number",
                                min=13,
                                max=120,
                                step=1,
                            ),
                            direction="column",
                            spacing="5",
                        ),
                        justify="center",
                    ),

                    

                    spacing="6",
                    width="100%",
                    align = "center"
                ),

                # Keep the buttons horizontally aligned.
                rx.flex(
                    rx.link(
                        rx.button("Back", type="button"),
                        href="/",
                    ),
                    rx.button(
                        "Cancel",
                        type="button",
                        on_click=ButtonEvent.cancel,
                    ),
                    rx.button(
                        "Skip",
                        type="submit",
                    ),
                    rx.button(
                        "Submit",
                        type="submit",
                    ),
                    direction="row",
                    spacing="5",
                    justify="end",
                    width="100%",
                ),

                width="100%",
                spacing="5",
            ),
            on_submit=ButtonEvent.submit,
            width="100%",
        ),
        width="100%",
    )
