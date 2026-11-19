# Surrogate Model Training and Evaluation

This folder contains `EUI_Compare_Colab.ipynb`, the Google Colab notebook used to develop and evaluate EUI prediction models for the façade inverse design project. It compares Linear Regression and Random Forest using EnergyPlus simulation results and exports the trained Random Forest model for use in the web prototype.

## Dataset and Inputs

The notebook uses an Excel dataset containing 160 façade configurations across 10 glazing options. Each configuration is represented by four input features:

| Feature | Description | Unit |
| --- | --- | --- |
| `wwr` | Window-to-wall ratio | Fraction (0–1) |
| `u_value` | Glazing U-value | W/(m²·K) |
| `shgc` | Solar heat gain coefficient | Fraction (0–1) |
| `shading_depth_m` | Shading depth | m |

The prediction target is `eui_simulated`, the annual EnergyPlus EUI in kWh/(m²·year).

The input file must also include `design_id`, `glazing_id`, `model_version`, and `simulation_status`. In final mode, all 160 cases must have valid positive EUI values, the selected model version, and a simulation status of `成功`.

## Modelling Workflow

1. Check the dataset for missing inputs, duplicate configurations, and inconsistent case counts.
2. Reserve three cases from each glazing group, giving 130 development cases and 30 held-out test cases.
3. Compare Linear Regression and Random Forest using five-fold cross-validation on the development set.
4. Evaluate both models on the held-out test set using MAE, RMSE, and R².
5. Generate predicted-versus-simulated EUI plots and export case-level predictions.
6. Train and export the Random Forest model using the 130 development cases, then reload it and verify that it reproduces the saved test predictions.

The Random Forest uses 300 trees and a random seed of 42. The held-out test cases are excluded from model training.

## How to Run

1. Open `EUI_Compare_Colab.ipynb` in Google Colab.
2. Run the first cell and upload the simulation results Excel file. The notebook reads its first worksheet.
3. Check that `VERSION` matches the dataset’s `model_version`. The supplied setting is `VAV_v1`.
4. Keep `FINAL = True` to run the complete evaluation and model export workflow.
5. Run the remaining cells in order and download the generated ZIP files.

The notebook analyses existing EnergyPlus results; it does not run building energy simulations.

## Outputs

**`eui_final.zip` — evaluation results**

- `split.csv`: development and test set assignments.
- `metrics.csv`: MAE, RMSE, and R² for both models.
- `development_cv_predictions.csv`: cross-validation predictions and absolute errors.
- `heldout_test_predictions.csv`: independent test predictions and absolute errors.
- `development_cv.png` and `heldout_test.png`: model comparison plots.

**`facade_rf_v1.zip` — trained model package**

- `random_forest.joblib`: saved Random Forest model.
- `model_info.json`: feature order, units, model metadata, and software versions.
- `requirements.txt`: package versions for loading and using the exported model.

## Scope

The model applies to the façade parameter space and reference building represented by the simulation dataset. Its predictions support candidate screening; the corresponding EnergyPlus results are used to confirm whether a design meets the target EUI tolerance.
