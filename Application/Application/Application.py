import reflex as rx
from rxconfig import config
from .onboarding import onboarding
from .personalize import PersonalizationState, personalize
from .target_calculations import TargetState, targets
from .ui import go, illustration, page, process


class State(rx.State):
    """The app state."""


def index() -> rx.Component:
    return page(
        rx.el.section(
            rx.el.div(
                rx.el.p("Daily nutrition", class_name="ns-kicker"),
                rx.el.h1(
                    "Your daily targets, estimated.",
                    class_name="ns-display",
                ),
                rx.el.p(
                    "A short profile sets maintenance calories. A goal and a priority macro can adjust them. You leave with protein, carbohydrates, fat, and fiber.",
                    class_name="ns-lede",
                ),
                rx.el.div(
                    go("Get Started", "/onboarding", "primary"),
                    class_name="ns-hero-actions",
                ),
            ),
            illustration(),
            class_name="ns-hero",
        ),
        rx.el.ol(
            process("01", "Profile", "Sex, age, height, weight, and activity."),
            process(
                "02",
                "Preferences",
                "Goal, priority macro, fiber, allergies, and diet.",
            ),
            process("03", "Targets", "Calories and grams for the day."),
            class_name="ns-process",
        ),
    )


app = rx.App(
    html_lang="en",
    stylesheets=[
        "https://fonts.googleapis.com/css2?family=Instrument+Sans:ital,wght@0,400;0,500;0,600;1,400&family=Instrument+Serif:ital@0;1&display=swap",
        "/styles.css",
    ],
)
app.add_page(index, title="NutriSpoke", description="Estimated daily calorie and macro targets.")
app.add_page(onboarding, route="/onboarding", title="Profile · NutriSpoke")
app.add_page(
    personalize,
    route="/personalize",
    title="Preferences · NutriSpoke",
    on_load=PersonalizationState.load_saved_fiber,
)
app.add_page(targets, route="/targets", title="Targets · NutriSpoke", on_load=TargetState.load_targets)
