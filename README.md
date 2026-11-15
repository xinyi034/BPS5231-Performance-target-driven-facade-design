# EUI-Targeted Inverse Design of Office Façades Using a Random Forest Surrogate

This BPS5231 project helps architects identify façade options for a Singapore reference office building during early design. Given a target annual energy use intensity (EUI) and an acceptable tolerance, the workflow ranks candidate designs and uses EnergyPlus results to check which options meet the target.

## Research Question

Which combinations of glazing product, window-to-wall ratio, and shading depth meet a specified EUI target for the reference office building?

## Design Variables and Performance Target

| Model input | Values used in the study |
|---|---|
| Window-to-wall ratio (WWR) | 30%, 40%, 50%, 60% |
| Glazing U-value [W/(m²·K)] | Product-specific value |
| Solar heat gain coefficient (SHGC) | Product-specific value |
| Shading depth [m] | 0.00, 0.30, 0.60, 0.90 |

Each of the 10 glazing products retained its documented U-value and SHGC as a pair. Combining 10 products with 4 WWRs and 4 shading depths yielded **160 façade configurations**.

The performance target is **annual whole-building EUI**, expressed in kWh/(m²·year). For example, a target of **145 ± 3 kWh/(m²·year)** accepts designs with an EUI between 142 and 148.

## Methodology

### Stage 1 — Generate the EnergyPlus dataset

A parametric reference office model was built in Grasshopper for Rhino and simulated using Honeybee and EnergyPlus. All 160 façade configurations were evaluated under the same building and operating assumptions. Simulated EUI ranged from **131.81 to 178.46 kWh/(m²·year)**.

### Stage 2 — Train and evaluate the forward surrogate

Linear regression and random forest regression were compared using five-fold cross-validation on 130 development cases. Both models predicted EUI from WWR, U-value, SHGC, and shading depth.

The random forest achieved the lower cross-validation error and was selected for façade screening. On 30 held-out cases, its mean absolute error was **1.83 kWh/(m²·year)**, compared with **2.97** for linear regression. Its test R² was **0.913**.

### Stage 3 — Screen façade options against a target EUI

1. Enter a target EUI and tolerance.
2. Predict EUI for each candidate façade configuration using the random forest.
3. Retain candidates within the target band and rank them by their absolute deviation from the target.
4. Compare the shortlisted designs with their EnergyPlus results to identify confirmed matches.

Each recommendation identifies a glazing product, WWR, and shading depth. The search is limited to the 160 configurations evaluated for the reference office.

## Data and Results

- [EnergyPlus simulation dataset — 160 façade configurations](./Data/Final%20160%20Result%20Data.xlsx)
- [Model evaluation figures and test metrics](./Results/Figure/README.md)
