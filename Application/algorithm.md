# Nutrition Target Calculation

This document describes how the application turns the saved profile and preferences into daily calorie and macro targets. It reflects the current implementation in `Application/target_calculations.py`, `Application/onboarding.py`, and `Application/personalize.py`.

## 1. Profile inputs and missing values

The onboarding form stores height in centimetres and weight in kilograms, converting from inches or pounds when selected. The target calculation reads `User Data/user_data.json`.

The profile fields are handled as follows:

| Field | Accepted values | Value used when missing or invalid |
| --- | --- | --- |
| Sex | Male or Female, case-insensitive | Other-sex adjustment (`-78`); use the average of the male and female default height and weight |
| Height | 90-250 cm | Sex-specific average for Male or Female; otherwise the overall average |
| Weight | 30-300 kg | Sex-specific average for Male or Female; otherwise the overall average |
| Age | 13-120 years | 40 years |
| Activity | None, Low, Medium, High, Extreme, case-insensitive | Low |

Missing, blank, nonnumeric, non-finite, and out-of-range height, weight, or age values use the corresponding default. A missing or unreadable JSON file, malformed JSON, or a JSON value that is not an object is treated as an empty profile, so all profile defaults apply.

The sex-specific averages are converted from the source values in the code:

- Male: 199 lb and 68.9 in.
- Female: 171.8 lb and 63.5 in.
- Other or undisclosed sex: the arithmetic mean of the male and female converted averages.

## 2. Estimated maintenance calories

The application uses the Mifflin-St Jeor equation with weight in kilograms, height in centimetres, and age in years:

```text
base = 10 * weight_kg + 6.25 * height_cm - 5 * age_years + sex_adjustment
maintenance_calories = base * activity_multiplier
```

The sex adjustment is `+5` for Male, `-161` for Female, and `-78` otherwise. Activity multipliers are:

| Activity | Multiplier |
| --- | ---: |
| None | 1.2 |
| Low | 1.375 |
| Medium | 1.55 |
| High | 1.725 |
| Extreme | 1.9 |

An unknown activity value uses Low. The resulting maintenance estimate is not rounded during calculation.

## 3. Preferences and missing values

The target calculation reads `User Data/user_personalization_data.json`.

| Preference | Behavior when absent or invalid |
| --- | --- |
| Calorie target | No manual target; calculate from the profile |
| Goal | Maintenance |
| Muscle Gain | Off |
| Fiber | 30 g |

A manual calorie target is valid from 0 through 10,000 inclusive. Missing, blank, nonnumeric, non-finite, or out-of-range values are treated as absent by the target calculation. The preference form accepts whole-number targets; entering 0 is a valid manual target and produces zero calorie-based macros.

Fiber is accepted from 0 through 100 g. A missing, invalid, non-finite, or out-of-range saved fiber value falls back to 30 g in the target calculation. The preference slider is limited to this range and the saved fiber preference is clamped when it is loaded or submitted.

The goal must be Maintenance, Weight Gain, or Weight Loss. Missing or unrecognized saved goals fall back to Maintenance.

### Legacy preference files

For saved files without a `muscle_gain` boolean, the old `Main Gain` goal or a `Protein` priority macro is interpreted as Muscle Gain enabled. The old `Main Gain` goal is treated as Maintenance. If a saved file has a `muscle_gain` boolean, that value takes precedence over those legacy fields. Old Carbs and Fat priorities have no equivalent in the current interface or calculation and are ignored.

## 4. Goal and manual-calorie precedence

When no manual calorie target is present:

| Goal | Daily calorie target |
| --- | --- |
| Maintenance | Estimated maintenance calories |
| Weight Gain | Estimated maintenance calories + 200 kcal |
| Weight Loss | Estimated maintenance calories - 200 kcal, with a floor of 0 kcal |

The baseline macros are calculated at maintenance. If Muscle Gain is enabled, its protein shift is applied at maintenance. For Weight Gain or Weight Loss, all three macro amounts are then scaled by `goal_calories / maintenance_calories`, preserving the macro proportions.

When a manual calorie target is present, it is used as entered and the Weight Gain or Weight Loss calorie adjustment is skipped. Baseline macros are calculated from the manual target, and the Muscle Gain protein shift is still applied if enabled.

## 5. Baseline macro calculation

For a calorie target `C` and selected profile weight `W` in kilograms, the baseline macro amounts are:

```text
protein_g = min(W, (C * 0.25) / 4)
fat_g     = (C * 0.30) / 9
carbs_g   = max(0, (C - 4 * protein_g - 9 * fat_g) / 4)
```

The calculation uses 4 kcal per gram for protein and carbohydrates and 9 kcal per gram for fat. Baseline protein is capped at 25% of the calorie target; fat is set to 30%; carbohydrates use the remaining calories. A zero-calorie target results in zero grams for all three macros.

## 6. Muscle Gain adjustment

When enabled, Muscle Gain shifts calories from carbohydrates and fat toward protein while keeping total calories unchanged:

1. Increase protein energy by up to 5% of the calorie target.
2. Do not let protein exceed 40% of the calorie target.
3. Remove the increase proportionally from the existing carbohydrate and fat energy shares.
4. Convert the resulting energy amounts back into grams.

If the calorie target is zero, no shift is applied. Muscle Gain is independent of the selected calorie goal.

## 7. Displayed values

The target page displays calories and each macro rounded to whole numbers. It displays fiber rounded to a whole gram. Macro share percentages are calculated from the macro energy amounts and adjusted for rounding so the displayed shares sum to 100%; if all macro amounts are zero, each share displays as 0%.
