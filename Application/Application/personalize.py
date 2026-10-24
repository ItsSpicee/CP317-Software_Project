import reflex as rx
import json
from pathlib import Path

PARENT_DIR = Path(__file__).resolve().parent.parent
USER_DATA_FOLDER = PARENT_DIR / "User Data"

PRIORITY_MACRO = ["Protein", "Carbs", "Fat"]

DIETS = ["Vegetarian", "Vegan", "Keto", "Gluten Free", "Carnivore", "Animal Based"]
class LiveSliderState(rx.State):
    fiber: float = 30.0

    @rx.event
    def set_fiber(self, value: list[int | float]):
        self.fiber = value[0]
        print((self.fiber))

class ButtonEvent(rx.State):

    def cancel(self):
        return rx.redirect("/")

    def submit(self, form_data: dict):
        # Save the submitted information.
        with open(USER_DATA_FOLDER / "user_personalization_data.json", "w", encoding="utf-8") as f:
            json.dump(form_data, f, indent=4)

        # Redirect after processing the submitted data.
        return rx.redirect("/personalize")

def personalize() -> rx.Component:
    return rx.container(
        rx.color_mode.button(position="top-right"),

        rx.form(
            rx.vstack(
                # Keep your original horizontal layout.
                rx.flex(
                    rx.vstack(
                        rx.heading("Optional", size="8"),
                        rx.text("Let's personalize your nutrition plan."),
                        spacing="5",
                        justify="center",
                        min_height="85vh",
                    ),

                    rx.vstack(
                        rx.heading("Further Personalization:", size="8"),
                        rx.flex(
                            rx.input(
                                placeholder = "Calorie Target",
                                name = "calories",
                                input_mode = "numeric"
                            ),
                            rx.select(
                                PRIORITY_MACRO,
                                name="priority_macro",
                                placeholder="Priority Macro",
                            ),
                            rx.vstack(
                                rx.text(
                                    "Fiber Target ",
                                    LiveSliderState.fiber,
                                    " grams",
                                ),
                                rx.slider(
                                    name="fiber",
                                    value=[LiveSliderState.fiber],
                                    min_=0,
                                    max=100,
                                    on_change=LiveSliderState.set_fiber,
                                ),
                            ),
                            direction="column",
                            spacing="5",
                        ),
                        justify="center",
                    ),

                    rx.flex(
                        rx.vstack(
                            rx.heading(
                                "Allergies"
                            ),
                            rx.flex(
                                rx.foreach(
                                    rx.Var.range(4),
                                    lambda i: rx.checkbox(f"Food {i + 1}", width="15%"),
                                ),
                                spacing="2",
                                flex_wrap="wrap",
                                width="100%",
                                align = "center",
                            ),
                            rx.heading(
                                "Diet Types"
                            ),
                            rx.flex(
                                *[
                                    rx.checkbox(diet, name="diet_types", value=diet)
                                    for diet in DIETS
                                ],
                                spacing="2",
                                flex_wrap="wrap",
                                width="100%",
                                align = "center",
                            ),
                            spacing="2",
                            flex_wrap="wrap",
                            width="100%",
                            justify="center",
                            align = "center",
                        )
                    ),
                    justify="center",
                    spacing="9",
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