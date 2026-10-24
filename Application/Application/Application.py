import reflex as rx
from rxconfig import config
from .onboarding import onboarding
from .personalize import PersonalizationState, personalize
from .target_calculations import TargetState, targets


class State(rx.State):
    """The app state."""


def index() -> rx.Component:
    # Welcome Page (Index)
    return rx.container(
        rx.color_mode.button(position="top-right"),
        rx.vstack(
            rx.heading("NutriSpoke", size="9"),
            rx.text(
                "Bespoke Nutrition Plans Powered by Intelligent Suggestions ",
                size="5",
            ),
            rx.link(
                rx.button("Get Started"),
                href="/onboarding"
            ),
            spacing="5",
            justify="center",
            min_height="85vh",
        ),
    )


app = rx.App()
app.add_page(index)
app.add_page(onboarding, route="/onboarding")
app.add_page(personalize, route="/personalize", on_load=PersonalizationState.load_saved_fiber)
app.add_page(targets, route="/targets", on_load=TargetState.load_targets)
