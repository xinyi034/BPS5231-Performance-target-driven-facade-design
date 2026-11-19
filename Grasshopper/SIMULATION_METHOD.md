# Simulation method and limitations

## Model and varied inputs

The submission includes byte-for-byte copies of the supplied working GH and GHX. The Rhino 8 driver opens the GHX copy and changes the existing Case Index, CSV path panel, and existing ModelToOSM output-folder panel in memory. It does not add components or save changes to the model. The input CSV selects the façade variables for each case. Geometry, orientation, floor representation and multiplier, HVAC, efficiencies, occupancy, schedules, internal loads, weather, and simulation settings remain those in the supplied model.

## Export and simulation validation

For each unverified case the driver recomputes Grasshopper, checks the selected design ID and façade values against the CSV, triggers the existing ModelToOSM write input, and waits for stable, fresh HBJSON/OSW files with a bounded timeout. It verifies HBJSON identity and that the OSW references that HBJSON before starting OpenStudio. OpenStudio/EnergyPlus runs sequentially. A case is recorded as successful only when the EnergyPlus completion marker is present, the SQL is fresh and readable, no Severe/Fatal EnergyPlus errors are found, and annual area/energy values can be extracted.

EUI is reported as annual total site energy divided by SQL Total Building Area, converted to kWh/m²·year. EnergyPlus SQL tabular schema variants are handled by the pipeline. CSV is checkpointed before Excel; a workbook lock defers workbook synchronization and does not invalidate a successful simulation.

## Provenance

- CSV Index 0–79: imported from the teammate-provided `FacadeAI_Results.csv`. Those entries are labeled `PROVIDED_UNVERIFIED` or `NOT_PROVIDED`; their original `simulation_status` and notes are preserved as source provenance. The package audit did not independently validate these rows against matching HBJSON, OSW, completion logs, and SQL, so they are not represented as results produced by this automation.
- CSV Index 80–159: imported from `FacadeAI_Results_80_159.csv`. All 80 were verified against their design identity, HBJSON, OSW, EnergyPlus completion/error logs, SQL, EUI, and floor area on the source Windows project at packaging time. Their provenance is `AUTOMATED_SQL_VERIFIED`.

The included workbook is keyed by `design_id`; unverified teammate records remain visibly marked. Source output paths are retained as provenance but may refer to the original E: project.

## Reproducibility limits

Simulation folders, SQL databases, EnergyPlus logs, weather files, and other large/generated artifacts are intentionally excluded from the GitHub package. Re-running or validating the historical results on another machine therefore requires the exact weather/model dependencies and original outputs, or a fresh full simulation. The teammate's first 80 results cannot be reproduced or certified from the package alone. Rhino/GH execution was not run during packaging; runtime compatibility depends on Rhino 8, compatible Ladybug Tools/Honeybee plug-ins, and the configured OpenStudio/Python installations.
