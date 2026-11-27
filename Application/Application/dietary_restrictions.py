"""Shared religious food preferences and saved-value validation."""

RELIGIOUS_RESTRICTIONS = ("Halal", "Kosher", "Hindu vegetarian", "Jain vegetarian")


def get_religious_restrictions(preferences: dict) -> list[str]:
    choices = preferences.get("religious_restrictions", [])
    if not isinstance(choices, list) or any(
        not isinstance(choice, str) or choice not in RELIGIOUS_RESTRICTIONS
        for choice in choices
    ):
        raise ValueError("religious_restrictions must contain supported food practices.")
    return list(dict.fromkeys(choices))
