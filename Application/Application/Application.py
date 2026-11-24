import reflex as rx
from rxconfig import config
from .grocery import GroceryState, grocery
from .meals import MealState, meals
from .onboarding import ButtonEvent, onboarding
from .personalize import PersonalizationState, personalize
from .target_calculations import TargetState, targets
from .navigation import NavigationState
from .home import OverviewState, overview, placeholder, settings
from .intake import MacroIntakeState
from .inventory_page import InventoryState, inventory_page
from .ui import home_splash, page, process


def index() -> rx.Component:
    return page(
        home_splash(),
        rx.el.ol(
            process("01", "Profile", "Sex, age, height, weight, and activity."),
            process("02", "Preferences", "Calorie goal, Muscle Gain, fiber, allergies, and diet."),
            process("03", "Targets", "Calories and grams for the day."),
            process("04", "Main menu", "Your overview, groceries, meals, and more."),
            class_name="ns-process",
        ),
        setup=True,
    )


app = rx.App(
    html_lang="en",
    stylesheets=[
        "https://fonts.googleapis.com/css2|family=Instrument+Sans:ital,wght@0,400;0,500;0,600;1,400&family=Instrument+Serif:ital@0;1&display=swap",
        "/styles.css",
    ],
    head_components=[rx.script(src="/scroll-charts.js")],
)
app.add_page(index, title="NutriSpoke", on_load=NavigationState.start)
app.add_page(onboarding, route="/onboarding", title="Set up profile | NutriSpoke",
             on_load=[NavigationState.guard_profile, ButtonEvent.load_setup])
app.add_page(personalize, route="/personalize", title="Set up preferences | NutriSpoke",
             on_load=[NavigationState.guard_preferences, PersonalizationState.load_setup])
app.add_page(lambda: targets(edit=False), route="/setup-targets", title="Your targets | NutriSpoke",
             on_load=[NavigationState.guard_targets, TargetState.load_targets])
app.add_page(overview, route="/overview", title="Overview | NutriSpoke",
             on_load=[NavigationState.guard_menu, OverviewState.load_overview, TargetState.load_targets, MacroIntakeState.load_intake])
app.add_page(lambda: onboarding(edit=True), route="/profile", title="Profile | NutriSpoke",
             on_load=[NavigationState.guard_menu, ButtonEvent.load_editor])
app.add_page(lambda: personalize(edit=True), route="/preferences", title="Preferences | NutriSpoke",
             on_load=[NavigationState.guard_menu, PersonalizationState.load_editor])
app.add_page(targets, route="/targets", title="Targets | NutriSpoke",
             on_load=[NavigationState.guard_menu, TargetState.load_targets])
app.add_page(grocery, route="/groceries", title="Groceries | NutriSpoke",
             on_load=[NavigationState.guard_menu, GroceryState.load_plan])
app.add_page(meals, route="/meals", title="Meals | NutriSpoke",
             on_load=[NavigationState.guard_menu, MealState.load_meals])
app.add_page(inventory_page, route="/inventory", title="Inventory | NutriSpoke",
             on_load=[NavigationState.guard_menu, InventoryState.load_inventory])
app.add_page(lambda: placeholder("Daily tracking", "tracking", "Your daily food and nutrition log will live here."),
             route="/tracking", title="Daily tracking | NutriSpoke", on_load=NavigationState.guard_menu)
app.add_page(lambda: placeholder("Progress", "progress", "Follow your nutrition habits over time. Progress tracking is coming soon."),
             route="/progress", title="Progress | NutriSpoke", on_load=NavigationState.guard_menu)
app.add_page(settings, route="/settings", title="Settings | NutriSpoke", on_load=NavigationState.guard_menu)
