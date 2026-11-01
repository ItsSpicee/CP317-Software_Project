# NutriSpoke Implementation Summary

## What was built

- A Reflex web prototype with a three-step flow: profile, optional preferences, and daily targets.
- Profile inputs: sex, age, height, weight, and activity; height and weight accept metric or imperial units.
- Preference inputs: calorie target, goal, Muscle Gain setting, fiber target, allergies, and diet types.
- A results page showing daily calorie, protein, carbohydrate, fat, and fiber targets.
- Fixed choices for activity, goal, allergies, and diet types. Open-ended forms are a later-sprint stretch goal to limit current input-validation complexity.
- Profile and preference data stored in two JSON files. JSON meets current save-and-load needs; SQLite or another database can be considered if later requirements need database features.

## How the calculation works

- **Normalize and validate inputs:** Imperial height is converted to centimetres (`in x 2.54`); imperial weight to kilograms (`lb x 0.45359237`). Measurements are stored in metric. Valid ranges are height 90-250 cm, weight 30-300 kg, and age 13-120 years. Blank values are accepted; invalid supplied values show an error.
- **Fill missing values independently:**
  - Height and weight fall back to measured averages for U.S. adults age 20 and older, from CDC/NCHS NHANES 2021-2023: men, 68.9 in and 199.0 lb; women, 63.5 in and 171.8 lb.
  - These values are converted to metric in the app. When sex is missing or unrecognized, it uses the mean of the male and female values: about 168.1 cm and 84.1 kg. These are population-average fallbacks, not estimates of the individual user. [CDC/NCHS source](https://www.cdc.gov/nchs/fastats/body-measurements.htm)
  - Age defaults to 40 and activity defaults to Low. These are application choices, not NHANES averages.
  - Sex adjustment is +5 for Male, -161 for Female, and -78 when missing or unrecognized.
- **Estimate maintenance calories** using Mifflin-St Jeor:
  - `BMR = 10 x weight_kg + 6.25 x height_cm - 5 x age_years + sex_adjustment`
  - `Maintenance = BMR x activity_multiplier`
  - Activity multipliers: None 1.20, Low 1.375, Medium 1.55, High 1.725, Extreme 1.90. Unknown activity uses Low.
- **Apply calorie preferences:** A valid manual target from 0 to 10,000 kcal replaces the estimate and overrides Weight Gain/Loss adjustments. Without one, Weight Gain adds 200 kcal; Weight Loss subtracts 200 kcal, with a zero floor. Blank or invalid manual targets are treated as absent; an invalid or missing goal defaults to Maintenance.
- **Apply Muscle Gain:** The optional setting shifts up to 5% of calories from carbohydrates and fat proportionally to protein, capped at 40% of calories.
- **Calculate macros:** Protein is the smaller of 1 g per kg body weight and 25% of calories (4 kcal/g). Fat supplies 30% of calories (9 kcal/g); carbohydrates use the remaining calories (4 kcal/g). Weight Gain/Loss scale the macro amounts with adjusted calories, preserving proportions. Displayed amounts are rounded to whole numbers.
- **Handle fiber separately:** Users select 0-100 g; the default is 30 g. Fiber is not estimated from profile data.

## Graphical design

- Warm off-white backgrounds, dark pine accents, and muted green and gold macro colors.
- Instrument Sans body text and Instrument Serif headings, with simple navigation, spacious cards, a three-step progress indicator, and a segmented macro bar.

## Technical issues and resolutions

- **Opt-in data versus useful output:** Profile measurements and manual calories can be blank, and preferences can be skipped. Documented fallbacks let the app calculate targets without requiring every personal input.
- **Missing or malformed saved data:** Missing, unreadable, or malformed JSON is treated as an empty record; missing, invalid, or out-of-range fields use defaults rather than crashing the calculation.
- **Mixed units and invalid submissions:** Inputs are converted to metric before range checks and storage. Values are handled independently, so a blank optional field does not discard other valid entries; invalid supplied values show field errors.
- **Persistence scope:** JSON was chosen over SQLite because the prototype stores a small set of values and does not need database-specific features. Database persistence remains a future-sprint option.
- **Backend unit tests cover:** conversions, blank and invalid inputs, defaults, range boundaries, target logic, preference precedence, and route registration. Open-ended input and database persistence are not implemented.
