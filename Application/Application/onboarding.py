import reflex as rx


class ButtonEvent(rx.State):
    gender: str = ""
    height: str = ""
    weight: str = ""
    activity_level: str = ""
    current_goal: str = ""

    def cancel(self):
        return rx.redirect("/")

    def submit(self, form_data: dict):
        self.gender = form_data.get("gender", "")
        self.height = form_data.get("height", "")
        self.weight = form_data.get("weight", "")
        self.activity_level = form_data.get("activity_level", "")
        self.current_goal = form_data.get("current_goal", "")

        # Inspect the submitted information.
        print(form_data)

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
                        rx.text("Let's personalize your nutrition plan."),
                        spacing="5",
                        justify="center",
                        min_height="85vh",
                    ),

                    rx.vstack(
                        rx.heading("Your information:", size="8"),
                        rx.flex(
                            rx.select(
                                ["Male", "Female", "Non-Binary", "2-Spirit",
                                 "Prefer not to disclose"],
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
                                ["None", "Low", "Medium", "High", "Extreme"],
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
                            ["Micro-Nutrients", "Weight Loss", "Main Gain", "Cut"],
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