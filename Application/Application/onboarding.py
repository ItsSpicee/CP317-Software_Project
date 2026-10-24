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
            form_data["height"] = height
        except (TypeError, ValueError):
            form_data["height"] = ""

        try:
            weight = float(form_data.get("weight", ""))
            if form_data.get("weight_unit", "kg") == "lb":
                weight *= 0.45359237
            form_data["weight"] = weight
        except (TypeError, ValueError):
            form_data["weight"] = ""

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
                            rx.hstack(
                                rx.input(name="height", placeholder="Height"),
                                rx.select(
                                    HEIGHT_UNITS,
                                    name="height_unit",
                                    default_value="cm",
                                    width="80px",
                                ),
                            ),
                            rx.hstack(
                                rx.input(name="weight", placeholder="Weight"),
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
