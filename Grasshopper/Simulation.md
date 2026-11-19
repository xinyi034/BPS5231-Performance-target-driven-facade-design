# Grasshopper Simulation and Automation

This folder documents the parametric model and simulation workflow used to generate the façade EUI dataset.

## Simulation Dataset

The study evaluates 160 façade configurations:

- 10 glazing products, each with a paired U-value and SHGC.
- Four window-to-wall ratios: 30%, 40%, 50%, and 60%.
- Four shading depths: 0, 0.30, 0.60, and 0.90 m.

Building geometry, HVAC configuration, internal loads, operating schedules, and weather settings remain unchanged across the cases.

Eighty cases were simulated manually, and the remaining eighty cases were processed using an automated workflow.

## Grasshopper Model

The model files are:

- `model/FacadeAI_Final_Model_v1.gh`
- `model/FacadeAI_Final_Model_v1.ghx`

The model uses Rhino, Grasshopper, and Honeybee to prepare the building model for EnergyPlus simulation.

## Automated Simulation Workflow

The automation starts through Rhino's `RunPythonScript` command.

1. Read the façade parameter combinations from the input CSV.
2. Update the existing Grasshopper Case Index and select the corresponding parameters.
3. Export the HBJSON and OSW files.
4. Run OpenStudio and EnergyPlus through a separate Python process.
5. Check the simulation outputs and extract annual energy use and building area from the SQL results.
6. Calculate EUI and save the results to CSV and Excel.

Annual EUI is calculated as total annual site energy divided by Total Building Area, expressed in kWh/(m²·year).

## Python Scripts

| Script | Purpose |
|---|---|
| `run_facadeai_rhino.py` | Runs inside Rhino, controls the existing Grasshopper model, and exports each case. |
| `facadeai_case.py` | Processes an individual case, runs the simulation when needed, and saves results. |
| `facadeai_pipeline.py` | Provides shared functions for validation, SQL reading, and EUI calculation. |
| `assemble_results.py` | Combines the supplied first 80 results and the automated last 80 results by design ID. |
| `validate_package.py` | Checks package files, dependencies, and result records without starting EnergyPlus. |

## Input and Result Files

| File | Contents |
|---|---|
| `data/input/FacadeAI_Input_Cases.csv` | Input parameters for all 160 configurations. |
| `data/results/FacadeAI_Teammate_Results_AsProvided.csv` | Supplied results for the first 80 cases. |
| `data/results/FacadeAI_Results_80_159_AsRun.csv` | Results for the 80 automated cases. |
| `data/results/FacadeAI_Results_160.csv` | Combined results for all 160 cases. |
| `data/results/FacadeAI_Results_160.xlsx` | Excel version of the combined results. |

## Running the Workflow

The workflow requires Rhino 8, compatible Grasshopper/Honeybee components, OpenStudio, and Python dependencies.

Configure the local paths in `config.json`, using `config.example.json` as a reference. Then run `scripts/run_facadeai_rhino.py` through Rhino's `RunPythonScript` command.

See `README_CN.md` and `SIMULATION_METHOD.md` for detailed instructions and reproducibility limitations.

## Data Provenance

The first 80 results were supplied separately. The automation package preserves their original provenance and does not independently certify their original simulation outputs.

The package records the remaining 80 cases as verified against the original simulation files at packaging time. Raw SQL databases, simulation logs, weather files, and complete simulation folders are not included in this package. Reproduction requires the corresponding local dependencies and weather file, or a fresh simulation.
