#!/usr/bin/env python3
"""Verify or run one CSV case; checkpoint CSV before optional Excel sync."""
import argparse
import csv
import json
import os
import shutil
import stat
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import facadeai_pipeline as pipeline

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"
if not CONFIG_PATH.is_file():
    CONFIG_PATH = ROOT / "config.example.json"


def load_config():
    with CONFIG_PATH.open("r", encoding="utf-8") as stream:
        cfg = json.load(stream)
    def resolve(value):
        path = Path(value)
        return path if path.is_absolute() else (ROOT / path).resolve()
    return cfg, resolve


def read_result_rows(path, sources):
    saved = {}
    if Path(path).is_file():
        with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                if row.get("design_id"):
                    saved[row["design_id"].strip()] = row
    rows = []
    for index, source in enumerate(sources):
        design_id = source["design_id"].strip()
        row = {field: source.get(field, "") for field in pipeline.FIELDS}
        row.update({"csv_index": index, "design_id": design_id, "floor_area_m2": "",
                    "annual_site_energy_gj": "", "eui_kwh_m2_year": "", "status": "PENDING",
                    "run_origin": "", "error": "", "hbjson_path": "", "osw_path": "",
                    "sql_path": "", "updated_at": "", "provenance": "",
                    "source_status": ""})
        old = saved.get(design_id)
        if old and old.get("status") == "SUCCESS" and pipeline.verified_resume_row(old, source):
            row.update(old)
        elif old and old.get("status") in ("PROVIDED_UNVERIFIED", "NOT_PROVIDED", "INCOMPLETE_SOURCE_RECORD"):
            row.update(old)
        rows.append(row)
    return rows


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(pipeline.FIELDS) + ["provenance", "source_status"]
    fd, temp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temp, str(path))
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def workbook_path(cfg, resolve):
    return resolve(cfg["results_workbook"])


def sync_workbook(cfg, resolve, rows):
    from openpyxl import load_workbook

    target = workbook_path(cfg, resolve)
    template = resolve(cfg["workbook_template"])
    if not target.exists():
        if not template.is_file():
            raise FileNotFoundError("Workbook template missing: {}".format(template))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(template), str(target))
    workbook = load_workbook(str(target), data_only=False)
    required = {"design_id", "eui_simulated", "floor_area_m2", "simulation_status", "output_path"}
    sheet = None
    headers = None
    for candidate in workbook.worksheets:
        mapping = {str(cell.value).strip(): cell.column for cell in candidate[1] if cell.value is not None}
        if required.issubset(mapping):
            sheet, headers = candidate, mapping
            break
    if sheet is None:
        raise ValueError("Workbook results sheet is missing required columns")
    by_id = {row["design_id"]: row for row in rows}
    row_for_id = {}
    for row_num in range(2, sheet.max_row + 1):
        design_id = sheet.cell(row_num, headers["design_id"]).value
        if design_id in by_id:
            if design_id in row_for_id:
                raise ValueError("Duplicate workbook design_id: {}".format(design_id))
            row_for_id[design_id] = row_num
    for design_id, record in by_id.items():
        if design_id not in row_for_id:
            raise ValueError("Workbook is missing design_id {}".format(design_id))
        row_num = row_for_id[design_id]
        eui = record.get("eui_kwh_m2_year", "")
        area = record.get("floor_area_m2", "")
        sheet.cell(row_num, headers["eui_simulated"]).value = float(eui) if eui not in (None, "") else None
        sheet.cell(row_num, headers["floor_area_m2"]).value = float(area) if area not in (None, "") else None
        sheet.cell(row_num, headers["simulation_status"]).value = record.get("status", "PENDING")
        sheet.cell(row_num, headers["output_path"]).value = record.get("sql_path") or record.get("hbjson_path") or ""
        if "notes" in headers and record.get("provenance"):
            note = record["provenance"]
            if record.get("source_status"):
                note += "; source status: " + record["source_status"]
            sheet.cell(row_num, headers["notes"]).value = note

    temp = target.with_name(target.stem + ".tmp.xlsx")
    try:
        workbook.save(str(temp))
        workbook.close()
        if target.exists():
            target.chmod(target.stat().st_mode | stat.S_IWRITE)
        try:
            os.replace(str(temp), str(target))
            return target
        except PermissionError:
            fallback = target.with_name(target.stem + "_Sync.xlsx")
            try:
                os.replace(str(temp), str(fallback))
                return fallback
            except PermissionError:
                fallback = target.with_name("{}_Sync_{}.xlsx".format(
                    target.stem, datetime.now().strftime("%Y%m%d_%H%M%S_%f")))
                os.replace(str(temp), str(fallback))
                return fallback
    finally:
        try:
            workbook.close()
        except Exception:
            pass
        if temp.exists():
            temp.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=int)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--sync-workbook", action="store_true")
    parser.add_argument("--record-export-failure", action="store_true")
    parser.add_argument("--error", default="")
    args = parser.parse_args()
    cfg, resolve = load_config()
    input_csv = resolve(cfg["input_csv"])
    sim_root = resolve(cfg["simulation_root"])
    existing_root = resolve(cfg["existing_simulation_root"])
    result_path = resolve(cfg["results_csv"])
    openstudio = resolve(cfg["openstudio_exe"])
    sources = pipeline.read_cases(input_csv)
    rows = read_result_rows(result_path, sources)
    if args.sync_workbook:
        target = sync_workbook(cfg, resolve, rows)
        print("WORKBOOK SYNCHRONIZED: {}".format(target))
        return 0
    if args.index is None or not 0 <= args.index <= 159:
        parser.error("--index must be a CSV Index from 0 through 159")
    index = args.index
    source = sources[index]
    row = rows[index]
    design_id = source["design_id"].strip()
    if row.get("status") == "SUCCESS" and pipeline.verified_resume_row(row, source):
        print("SKIP VERIFIED {}".format(design_id))
        return 0
    prior_source_path = resolve(cfg["teammate_results_csv"])
    prior_source = pipeline.read_csv_map(prior_source_path)
    existing = pipeline.verified_existing(index, source, existing_root, prior_source)
    if existing:
        row.update(existing)
        row["provenance"] = "EXISTING_SQL_VERIFIED"
        write_csv(result_path, rows)
        try:
            target = sync_workbook(cfg, resolve, rows)
            print("SKIP VERIFIED EXISTING {}; workbook {}".format(design_id, target))
        except PermissionError as exc:
            print("WORKBOOK UPDATE DEFERRED; CSV/SQL verified: {}".format(exc), file=sys.stderr)
        return 0
    if args.check_only:
        print("NOT VERIFIED; export/simulation needed for {}".format(design_id))
        return 10
    if args.record_export_failure:
        row.update({"status": "FAILED", "error": args.error or "Grasshopper export failed",
                    "provenance": "AUTOMATION", "updated_at": datetime.now().astimezone().isoformat(timespec="seconds")})
        write_csv(result_path, rows)
        try:
            sync_workbook(cfg, resolve, rows)
        except Exception as exc:
            print("Workbook update deferred: {}".format(exc), file=sys.stderr)
        return 2
    if not openstudio.is_file():
        parser.error("OpenStudio not found: {}".format(openstudio))
    try:
        pipeline.run_case(index, source, row, sim_root, openstudio, 180 * 60)
    except Exception as exc:
        row.update({"status": "FAILED", "error": "{}: {}".format(type(exc).__name__, exc)})
    row.update({"provenance": "AUTOMATED_SQL_VERIFIED" if row.get("status") == "SUCCESS" else "AUTOMATION",
                "updated_at": datetime.now().astimezone().isoformat(timespec="seconds")})
    write_csv(result_path, rows)
    try:
        target = sync_workbook(cfg, resolve, rows)
        print("{} {} EUI={} floor_area={} workbook={}".format(
            row.get("status"), design_id, row.get("eui_kwh_m2_year", ""), row.get("floor_area_m2", ""), target))
    except Exception as exc:
        print("{} {}; workbook update deferred after CSV checkpoint: {}".format(
            row.get("status"), design_id, exc), file=sys.stderr)
    return 0 if row.get("status") == "SUCCESS" else 2


if __name__ == "__main__":
    sys.exit(main())
