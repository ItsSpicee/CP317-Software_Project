import reflex as rx

def onboarding() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("Welcome to NutriSpoke!", size="8"),
            rx.text("Let's personalize your nutrition plan."),
            rx.button("Continue"),
            spacing="5",
            justify="center",
            min_height="85vh",
        ),
    )