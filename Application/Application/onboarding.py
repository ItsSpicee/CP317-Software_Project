import reflex as rx
import json
from pathlib import Path

PARENT_DIR = Path(__file__).resolve().parent.parent
USER_DATA_FOLDER = PARENT_DIR / "User Data"

GOALS = ["Micro-Nutrients", "Weight Loss", "Main Gain", "Cut"]
GENDERS = ["Male", "Female", "Non-Binary", "2-Spirit", "Prefer not to disclose"]
ACTIVITY_LEVELS = ["None", "Low", "Medium", "High", "Extreme"]

class ButtonEvent(rx.State):

    def cancel(self):
        return rx.redirect("/")

    def submit(self, form_data: dict):
        # Save the submitted information.
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

                    rx.vstack(
                        rx.heading("Your information:", size="8"),
                        rx.flex(
                            rx.select(
                                GENDERS,
                                name="gender",
                                placeholder="Gender",
                            ),
                            rx.input(
                                name="height",
                                placeholder="Height",
                            ),
                            rx.input(
                                name="weight",
                                placeholder="Weight",
                            ),
                            rx.select(
                                ACTIVITY_LEVELS,
                                name="activity_level",
                                placeholder="Activity Level",
                            ),
                            direction="column",
                            spacing="5",
                        ),
                        justify="center",
                    ),

                    rx.flex(
                        rx.select(
                            GOALS,
                            name="current_goal",
                            placeholder="Current Goal",
                        ),
                        direction="column",
                        justify="center",
                    ),

                    spacing="6",
                    width="100%",
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