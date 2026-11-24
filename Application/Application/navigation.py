"""Session-only setup flow and prototype data reset."""

from pathlib import Path

import reflex as rx

USER_DATA_FOLDER = Path(__file__).resolve().parent.parent / "User Data"


def clear_saved_data() -> None:
    """Delete app JSON data, including every browser session's generated plans."""
    root = USER_DATA_FOLDER.resolve()
    if not root.is_dir():
        return
    paths = list(root.rglob("*.json"))
    for path in paths:
        if not path.resolve().is_relative_to(root):
            raise ValueError("Saved data must remain inside User Data.")
    for path in paths:
        path.unlink(missing_ok=True)


class NavigationState(rx.State):
    initialized: bool = False
    setup_step: int = 1
    complete: bool = False
    reset_confirmation: bool = False
    reset_error: str = ""

    def _setup_route(self) -> str:
        return {1: "/onboarding", 2: "/personalize", 3: "/setup-targets"}[self.setup_step]

    @rx.event
    def start(self):
        """Keep the intro visible until Get Started; completed sessions use the hub."""
        if self.complete:
            return rx.redirect("/overview")

    @rx.event
    def guard_profile(self):
        if self.complete:
            return rx.redirect("/profile")
        if not self.initialized:
            clear_saved_data()
            USER_DATA_FOLDER.mkdir(parents=True, exist_ok=True)
            self.initialized = True

    @rx.event
    def guard_preferences(self):
        if self.complete:
            return rx.redirect("/preferences")
        if self.setup_step < 2:
            return rx.redirect("/onboarding")

    @rx.event
    def guard_targets(self):
        if self.complete:
            return rx.redirect("/targets")
        if self.setup_step < 3:
            return rx.redirect(self._setup_route())

    @rx.event
    def guard_menu(self):
        if not self.complete:
            return rx.redirect(self._setup_route())

    @rx.event
    def profile_saved(self):
        self.setup_step = max(self.setup_step, 2)
        return rx.redirect("/personalize")

    @rx.event
    def preferences_saved(self):
        self.setup_step = 3
        return rx.redirect("/setup-targets")

    @rx.event
    def finish(self):
        if self.setup_step < 3:
            return rx.redirect(self._setup_route())
        self.complete = True
        return rx.redirect("/overview")

    @rx.event
    def ask_reset(self):
        self.reset_confirmation = True
        self.reset_error = ""

    @rx.event
    def cancel_reset(self):
        self.reset_confirmation = False
        self.reset_error = ""

    @rx.event
    async def reset_profile(self):
        from .grocery import GroceryState
        from .intake import MacroIntakeState
        from .inventory_page import InventoryState
        from .meals import MealState
        from .onboarding import ButtonEvent
        from .personalize import PersonalizationState
        from .target_calculations import TargetState

        if not self.complete or not self.reset_confirmation:
            return
        groceries = await self.get_state(GroceryState)
        meals = await self.get_state(MealState)
        if groceries.busy or meals.busy:
            self.reset_error = "Wait for generation to finish before resetting."
            return
        try:
            clear_saved_data()
        except OSError:
            self.reset_error = "Could not clear saved data. Try resetting again."
            return
        for state_type in (ButtonEvent, PersonalizationState, TargetState, GroceryState, MealState, MacroIntakeState, InventoryState):
            state = await self.get_state(state_type)
            state.reset()
        meals._meals = []
        self.reset()
        self.initialized = True
        return rx.redirect("/")
