#!/usr/bin/env python3
"""Static/dependency/path checks and a non-simulating case-range dry run."""
import argparse
import importlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Validate configured range and exports; never run EnergyPlus")
    args = parser.parse_args()
    cfg_path = ROOT / "config.json"
    if not cfg_path.is_file():
        cfg_path = ROOT / "config.example.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    def resolve(key):
        p = Path(cfg[key])
        return p if p.is_absolute() else (ROOT / p).resolve()

    required = [ROOT / "model/FacadeAI_Final_Model_v1.gh", ROOT / "model/FacadeAI_Final_Model_v1.ghx",
                resolve("input_csv"), ROOT / "scripts/facadeai_pipeline.py", ROOT / "scripts/facadeai_case.py",
                ROOT / "scripts/run_facadeai_rhino.py", ROOT / "scripts/assemble_results.py"]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit("Missing package files:\n  " + "\n  ".join(missing))
    sys.path.insert(0, str(ROOT / "scripts"))
    import openpyxl  # noqa: F401
    import sqlite3  # noqa: F401
    for module in ("facadeai_pipeline", "facadeai_case", "assemble_results"):
        importlib.import_module(module)
    import facadeai_pipeline as pipeline
    cases = pipeline.read_cases(resolve("input_csv"))
    start, end = int(cfg.get("start_index", 0)), int(cfg.get("end_index", 159))
    if not 0 <= start <= end <= 159:
        raise SystemExit("Configured range must satisfy 0 <= start <= end <= 159")
    model_text = (ROOT / "model/FacadeAI_Final_Model_v1.ghx").read_text(encoding="utf-8", errors="ignore")
    for guid in ("4ed78ee6-3346-4f20-aebc-c8eb2711a867", "02fd4665-5fa3-4eef-ab6b-3b8e347eeba7",
                 "228461f8-bdea-47ff-9f41-6f32565f843d", "e6abb2a6-9ec8-4027-9778-671888281ae8"):
        if guid not in model_text:
            raise SystemExit("Original GHX is missing expected existing component: " + guid)
    print("Syntax/dependency/file-reference checks passed; input rows=160; Index 80={}.".format(cases[80]["design_id"]))
    print("Grasshopper copy: {}".format(resolve("grasshopper_model")))
    results_path = resolve("results_csv")
    workbook_path = resolve("results_workbook")
    if results_path.is_file() and workbook_path.is_file():
        import csv
        from openpyxl import load_workbook
        with results_path.open("r", encoding="utf-8-sig", newline="") as stream:
            result_rows = list(csv.DictReader(stream))
        if len(result_rows) != 160 or len(set(row["design_id"] for row in result_rows)) != 160:
            raise SystemExit("Results CSV must contain one unique row per input design_id")
        workbook = load_workbook(str(workbook_path), data_only=True, read_only=True)
        sheet = next((s for s in workbook.worksheets if s.cell(1, 1).value == "design_id"), None)
        if sheet is None:
            raise SystemExit("Results workbook has no design_id result sheet")
        headers = {sheet.cell(1, c).value: c for c in range(1, sheet.max_column + 1)
                   if sheet.cell(1, c).value is not None}
        excel_rows = {}
        for row_num in range(2, sheet.max_row + 1):
            design_id = sheet.cell(row_num, headers["design_id"]).value
            if design_id:
                excel_rows[design_id] = row_num
        mismatches = []
        for record in result_rows:
            row_num = excel_rows.get(record["design_id"])
            if row_num is None:
                mismatches.append(record["design_id"])
                continue
            status = sheet.cell(row_num, headers["simulation_status"]).value
            eui = sheet.cell(row_num, headers["eui_simulated"]).value
            if status != record["status"]:
                mismatches.append(record["design_id"])
            elif record.get("eui_kwh_m2_year") and (eui is None or abs(float(eui) - float(record["eui_kwh_m2_year"])) > 1e-6):
                mismatches.append(record["design_id"])
        workbook.close()
        if mismatches:
            raise SystemExit("CSV/workbook mismatch: " + ", ".join(mismatches[:10]))
        print("Results CSV/workbook identity, status and EUI reconciliation passed (160 designs).")
    if args.dry_run:
        saved = pipeline.read_csv_map(results_path)
        skips, needs_export = [], []
        for i in range(start, end + 1):
            row = saved.get(cases[i]["design_id"].strip(), {})
            if row and pipeline.verified_resume_row(row, cases[i]):
                skips.append(cases[i]["design_id"].strip())
            else:
                needs_export.append((i, cases[i]["design_id"].strip()))
        print("DRY RUN ONLY: verified skip={} ; export/simulation needed={}. No simulation started.".format(len(skips), len(needs_export)))
        if needs_export:
            print("First cases needing export: {}".format(", ".join("{}:{}".format(*item) for item in needs_export[:5])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
