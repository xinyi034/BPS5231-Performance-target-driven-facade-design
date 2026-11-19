# NUS BPS5231 FacadeAI

Submission copy of the 160-case façade energy workflow. This repository contains the original working Grasshopper model, source input cases, provenance-aware results, and a configurable Windows runner. It does not include generated simulation folders.

## Contents

- `model/FacadeAI_Final_Model_v1.gh` and `.ghx`: original working model copies.
- `data/input/FacadeAI_Input_Cases.csv`: 160 input cases, indexed 0–159.
- `data/results/FacadeAI_Results_160.csv` and `.xlsx`: combined results with per-row provenance.
- `data/results/FacadeAI_Teammate_Results_AsProvided.csv`: unmodified teammate source results.
- `data/results/FacadeAI_Results_80_159_AsRun.csv`: unmodified automated-range source CSV.
- `scripts/`: configurable Rhino driver, single-case processor, SQL verification helpers, result assembler, and package validator.
- `SIMULATION_METHOD.md`: method, provenance and limitations.

## Windows requirements

- Windows 10/11, Rhino 8, and Grasshopper.
- Ladybug Tools / Honeybee 1.8.0 installed in Rhino with the dependencies used by the supplied GHX.
- OpenStudio 3.7.0 with EnergyPlus available through its `openstudio.exe`.
- Python 3.8 or newer with `openpyxl`; the local Rhino runtime must also support the GH script's IronPython 2.7 syntax.

Install Python dependencies from this folder:

```powershell
python -m pip install -r requirements.txt
Copy-Item config.example.json config.json
```

Edit `config.json` for the local Python and OpenStudio paths, the simulation output folder, and the inclusive `start_index` / `end_index`. Paths may be absolute or relative to this repository. The default range is 0–159. Keep generated simulation output outside a source-controlled folder if preferred.

Before opening Rhino, run the non-simulating validation:

```powershell
python scripts/validate_package.py --dry-run
```

Open Rhino 8 and run this command in its command line:

```text
_RunPythonScript "<repository-folder>\scripts\run_facadeai_rhino.py"
```

The driver opens the included GHX copy, sets the configured CSV path and per-case ModelToOSM output folder through existing panels, then processes the configured index range sequentially. Validated successes are skipped on resume. An actual export or simulation failure is logged and stops the run at that case; correct the cause and restart with the same range. Workbook lock errors do not cause a successful simulation to rerun.

To regenerate the packaged provenance-aware CSV/XLSX from the two source result files, use:

```powershell
python scripts/assemble_results.py
```

This verifies the automated 80–159 SQL files before labeling those rows successful. It does not run EnergyPlus.

## Result provenance

Index 0–79 is teammate-provided, not independently verified by this automation. It is never labeled as automation output. Index 80–159 is the automated result set and was SQL-verified at packaging time. See `SIMULATION_METHOD.md` for the EUI basis and reproducibility limitations.
