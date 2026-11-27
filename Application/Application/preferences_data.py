"""Preference options and validation shared by the UI and planner backends."""

FOOD_ALLERGIES = (
    "Eggs", "Milk", "Mustard", "Peanuts", "Crustaceans", "Fish",
    "Sesame seeds", "Soy", "Sulphites", "Tree nuts",
)
DIETS = ("Vegetarian", "Vegan", "Keto", "Gluten Free", "Carnivore", "Animal Based")

RELIGIOUS_RESTRICTIONS = ("Halal", "Kosher", "Hindu vegetarian", "Jain vegetarian")


PREFERENCE_OPTIONS = {
    "allergies": FOOD_ALLERGIES,
    "diet_types": DIETS,
    "religious_restrictions": RELIGIOUS_RESTRICTIONS,
}


def get_dietary_preferences(preferences: dict, *, strict: bool = True) -> dict[str, list[str]]:
    """Validate planner inputs, or restore supported UI selections for editing.

    Missing fields default to empty lists for older saved preferences. The UI
    can recover invalid selections; planners must reject them rather than
    silently ignoring a dietary restriction.
    """
    result = {}
    for field, options in PREFERENCE_OPTIONS.items():
        choices = preferences.get(field, [])
        if not isinstance(choices, list):
            if strict:
                raise ValueError(f"{field} must be a list of supported options.")
            choices = []
        if strict and any(not isinstance(choice, str) or choice not in options for choice in choices):
            raise ValueError(f"{field} must contain supported nonempty strings.")
        result[field] = [option for option in options if option in choices]
    return result
