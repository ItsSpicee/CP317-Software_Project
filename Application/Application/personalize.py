import reflex as rx
import json
from pathlib import Path


PARENT_DIR = Path(__file__).resolve().parent.parent
USER_DATA_FOLDER = PARENT_DIR / "User Data"

PRIORITY_MACRO = ["Protein", "Carbs", "Fat"]

DIETS = ["Vegetarian", "Vegan", "Keto", "Gluten Free", "Carnivore", "Animal Based"]
# Only goals with a defined target calculation are offered here.
GOALS = ["Weight Gain", "Weight Loss", "Main Gain"]

FOOD_ALLERGIES = [
    "Eggs",
    "Milk",
    "Mustard",
    "Peanuts",
    "Crustaceans",
    "Fish",
    "Sesame seeds",
    "Soy",
    "Sulphites",
    "Tree nuts"
]

class PersonalizationState(rx.State):
    allergies: list[str] = []
    diet_types: list[str] = []
    fiber: float = 30.0

    @rx.event
    def load_saved_fiber(self):
        try:
            with open(USER_DATA_FOLDER / "user_personalization_data.json", "r", encoding="utf-8") as f:
                saved_data = json.load(f)
            value = float(saved_data.get("fiber", 30)) if isinstance(saved_data, dict) else 30.0
            self.fiber = min(max(value, 0.0), 100.0)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            self.fiber = 30.0

    @rx.event
    def toggle_allergy(self, allergy: str, checked: bool):
        if checked and allergy not in self.allergies:
            self.allergies.append(allergy)
        elif not checked and allergy in self.allergies:
            self.allergies.remove(allergy)

    @rx.event
    def toggle_diet(self, diet: str, checked: bool):
        if checked and diet not in self.diet_types:
            self.diet_types.append(diet)
        elif not checked and diet in self.diet_types:
            self.diet_types.remove(diet)

    @rx.event
    def set_fiber(self, value: list[int | float]):
        self.fiber = value[0]

    @rx.event
    def cancel(self):
        return rx.redirect("/")

    @rx.event
    def submit(self, form_data):
        try:
            calories = float(form_data.get("calories", ""))
            if not 0 <= calories <= 10_000:
                calories = ""
        except (TypeError, ValueError):
            calories = ""
        form_data["calories"] = calories
        self.fiber = min(max(float(self.fiber), 0.0), 100.0)
        form_data["allergies"] = list(self.allergies)
        form_data["diet_types"] = list(self.diet_types)
        form_data["fiber"] = self.fiber

        with open(USER_DATA_FOLDER / "user_personalization_data.json", "w", encoding="utf-8") as f:
            json.dump(form_data, f, indent=4)

        return rx.redirect("/targets")


def allergy_checkbox(allergy: str) -> rx.Component:
    return rx.checkbox(
        allergy,
        on_change=lambda checked: PersonalizationState.toggle_allergy(allergy, checked),
    )


def diet_checkbox(diet: str) -> rx.Component:
    return rx.checkbox(
        diet,
        on_change=lambda checked: PersonalizationState.toggle_diet(diet, checked),
    )

def personalize() -> rx.Component:
    return rx.container(
        rx.color_mode.button(position="top-right"),

        rx.form(
            rx.vstack(
                # Keep original horizontal layout.
                rx.flex(
                    rx.vstack(
                        rx.heading("Optional", size="8"),
                        rx.text("Let's personalize your nutrition plan."),
                        spacing="5",
                        justify="center",
                        min_height="85vh",
                    ),
                    rx.separator(
                        orientation = "vertical",
                        size = "4",
                        height="45vh",
                    ),
                    rx.vstack(
                        rx.heading("Further Personalization:", size="8"),
                        rx.flex(
                            rx.input(
                                placeholder="Calorie Target (optional)",
                                name="calories",
                                type="number",
                                min=0,
                                max=10_000,
                                step=1,
                                width="110%",
                            ),
                            rx.select(
                                PRIORITY_MACRO,
                                name="priority_macro",
                                placeholder="Priority Macro",
                            ),
                            rx.vstack(
                                rx.text(
                                    "Fiber Target ",
                                    PersonalizationState.fiber,
                                    " grams",
                                ),
                                rx.slider(
                                    name="fiber",
                                    value=[PersonalizationState.fiber],
                                    min_=0,
                                    max=100,
                                    on_change=PersonalizationState.set_fiber,
                                ),
                            ),
                            
                            rx.select(
                                GOALS,
                                name="current_goal",
                                placeholder="Current Goal",
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
                                *[
                                    allergy_checkbox(allergy)
                                    for allergy in FOOD_ALLERGIES
                                ],
                                spacing="2",
                                flex_wrap="wrap",
                                width="130%",
                                align = "center",
                            ),
                            rx.separator(),
                            rx.heading(
                                "Diet Types"
                            ),
                            rx.flex(
                                *[
                                    diet_checkbox(diet)
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
                    align = "center"
                    
                    
                ),

                # Keep the buttons horizontally aligned.
                rx.flex(
                    rx.link(
                        rx.button("Back", type="button"),
                        href="/onboarding",
                    ),
                    rx.button(
                        "Cancel",
                        type="button",
                        on_click=PersonalizationState.cancel,
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
            on_submit=PersonalizationState.submit,
            width="100%",
        ),
        width="100%",
    )
