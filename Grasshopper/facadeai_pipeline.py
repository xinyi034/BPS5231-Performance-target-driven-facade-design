#!/usr/bin/env python3
"""Shared CSV, HBJSON/OSW, EnergyPlus and SQL validation helpers for FacadeAI."""
from __future__ import print_function

import argparse
import csv
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path


FIRST_INDEX = 0
LAST_INDEX = 159
EXPECTED_INDEX_80_ID = "G12_W30_S00"
RANGE_IDS = set(range(FIRST_INDEX, LAST_INDEX + 1))
REQUIRED = ("design_id", "glazing_id", "wwr", "u_value", "shgc", "shading_depth_m", "glazing_name")
FIELDS = ["csv_index", "design_id", "building_id", "model_version", "glazing_id", "wwr", "u_value",
          "shgc", "shading_depth_m", "glazing_name", "floor_area_m2", "annual_site_energy_gj",
          "eui_kwh_m2_year", "status", "run_origin", "error", "hbjson_path", "osw_path", "sql_path",
          "updated_at"]


def read_cases(path):
    with open(str(path), "r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = [col for col in REQUIRED if col not in (reader.fieldnames or [])]
        if missing:
            raise ValueError("Input CSV missing columns: " + ", ".join(missing))
        rows = list(reader)
    if len(rows) != 160:
        raise ValueError("Expected 160 input rows, found {}".format(len(rows)))
    ids = [row["design_id"].strip() for row in rows]
    if len(set(ids)) != len(ids) or any(not x for x in ids):
        raise ValueError("Input CSV contains empty or duplicate design_id values")
    if ids[80] != EXPECTED_INDEX_80_ID:
        raise ValueError("Safety stop: CSV Index 80 is '{}', expected '{}'".format(ids[80], EXPECTED_INDEX_80_ID))
    return rows


def read_csv_map(path):
    result = {}
    if not path or not Path(path).is_file():
        return result
    with open(str(path), "r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row.get("design_id"):
                result[row["design_id"].strip()] = row
    return result


def write_results(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temp_name, str(path))
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def normalized_path(path):
    return os.path.normcase(os.path.abspath(str(path)))


def workflow_references(osw_path, hbjson_path):
    try:
        with open(str(osw_path), "r", encoding="utf-8") as stream:
            workflow = json.load(stream)
    except Exception:
        return False
    refs = []
    for step in workflow.get("steps", []):
        if step.get("measure_dir_name") == "from_honeybee_model":
            ref = step.get("arguments", {}).get("model_json")
            if ref:
                candidate = Path(ref)
                if not candidate.is_absolute():
                    candidate = Path(osw_path).parent / candidate
                refs.append(candidate)
    return len(refs) == 1 and normalized_path(refs[0]) == normalized_path(hbjson_path)


def read_hbjson_identity(path, expected_id):
    try:
        with open(str(path), "r", encoding="utf-8") as stream:
            model = json.load(stream)
        return model.get("identifier") == expected_id and bool(model.get("rooms"))
    except Exception:
        return False


def extract_sql(sql_path):
    """EnergyPlus 23.2 SQL (TabularData) and newer SQL (TabularDataWithStrings)."""
    con = sqlite3.connect(str(Path(sql_path).resolve()))
    try:
        tables = {row[0].lower() for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "strings" not in tables:
            raise ValueError("EnergyPlus SQL lacks Strings table")
        report_filter = "lower(replace(replace(trim(s1.Value),' ',''),'_',''))='annualbuildingutilityperformancesummary'"
        if "tabulardatawithstrings" in tables:
            query = """SELECT s2.Value,s3.Value,s4.Value,t.Value,t.Units
                       FROM TabularDataWithStrings t
                       JOIN Strings s1 ON t.ReportNameIndex=s1.StringIndex
                       JOIN Strings s2 ON t.TableNameIndex=s2.StringIndex
                       JOIN Strings s3 ON t.RowNameIndex=s3.StringIndex
                       JOIN Strings s4 ON t.ColumnNameIndex=s4.StringIndex
                       WHERE {}""".format(report_filter)
        elif "tabulardata" in tables:
            query = """SELECT s2.Value,s3.Value,s4.Value,t.Value,s5.Value
                       FROM TabularData t
                       JOIN Strings s1 ON t.ReportNameIndex=s1.StringIndex
                       JOIN Strings s2 ON t.TableNameIndex=s2.StringIndex
                       JOIN Strings s3 ON t.RowNameIndex=s3.StringIndex
                       JOIN Strings s4 ON t.ColumnNameIndex=s4.StringIndex
                       JOIN Strings s5 ON t.UnitsIndex=s5.StringIndex
                       WHERE {}""".format(report_filter)
        else:
            raise ValueError("EnergyPlus SQL lacks TabularData tables")
        records = [(str(a or "").strip(), str(b or "").strip(), str(c or "").strip(),
                    str(d or "").strip(), str(e or "").strip()) for a,b,c,d,e in con.execute(query)]
    finally:
        con.close()

    def lookup(table, row_name, column):
        for table_name, row, col, value, units in records:
            if table_name.casefold() == table.casefold() and row.casefold() == row_name.casefold() and col.casefold() == column.casefold():
                try:
                    return float(value.replace(",", "")), units
                except ValueError:
                    pass
        return None

    area_data = lookup("Building Area", "Total Building Area", "Area")
    if not area_data:
        area_data = lookup("Building Area", "Net Conditioned Building Area", "Area")
    energy_data = lookup("Site and Source Energy", "Total Site Energy", "Total Energy")
    if not area_data or not energy_data:
        raise ValueError("SQL lacks annual Total Building Area and Total Site Energy")
    area, area_units = area_data
    energy, energy_units = energy_data
    if area <= 0 or area_units.casefold() not in ("m2", "m^2", "m²"):
        raise ValueError("Unexpected SQL floor area {} {}".format(area, area_units))
    unit = energy_units.casefold().replace(" ", "")
    if unit in ("gj", "gigajoules"):
        energy_gj = energy
    elif unit in ("kwh", "kw-hr", "kw·h"):
        energy_gj = energy * 0.0036
    elif unit in ("j", "joules"):
        energy_gj = energy / 1e9
    else:
        raise ValueError("Unsupported SQL site-energy units: {}".format(energy_units))
    return area, energy_gj, energy_gj * 277.7777777778 / area


def verify_energyplus_run(sql_path, started=0):
    sql_path = Path(sql_path)
    run_dir = sql_path.parent
    end_file = run_dir / "eplusout.end"
    err_file = run_dir / "eplusout.err"
    if not end_file.is_file() or not err_file.is_file():
        raise ValueError("SQL has no paired eplusout.end/eplusout.err: {}".format(sql_path))
    if min(end_file.stat().st_mtime, err_file.stat().st_mtime, sql_path.stat().st_mtime) < started - 2:
        raise ValueError("EnergyPlus outputs are stale: {}".format(run_dir))
    if "completed successfully" not in end_file.read_text(encoding="utf-8", errors="replace").casefold():
        raise ValueError("EnergyPlus completion marker reports failure: {}".format(end_file))
    severe = []
    for n, line in enumerate(err_file.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if re.search(r"^\s*\*\*\s*(?:Severe|Fatal)\s*\*\*", line, re.IGNORECASE):
            severe.append("{}:{} {}".format(err_file, n, line.strip()))
    if severe:
        raise ValueError("Severe/Fatal EnergyPlus errors: " + " | ".join(severe[:6]))
    if sql_path.stat().st_mtime < end_file.stat().st_mtime - 5:
        raise ValueError("SQL predates EnergyPlus completion marker: {}".format(sql_path))


def values_match(row, area, eui):
    area_value = row.get("floor_area_m2") or ""
    eui_value = row.get("eui_kwh_m2_year") or row.get("eui_simulated") or ""
    try:
        if area_value and abs(float(area_value) - area) > max(0.1, area * 0.0001):
            return False
        if eui_value and abs(float(eui_value) - eui) > max(0.05, eui * 0.001):
            return False
    except ValueError:
        return False
    return True


def verified_existing(case_index, source, existing_root, prior_results):
    design_id = source["design_id"].strip()
    case_dir = Path(existing_root) / design_id
    if not case_dir.is_dir():
        return None
    old_row = prior_results.get(design_id, {})
    hbjsons = sorted(case_dir.rglob("*.hbjson"), key=lambda p: p.stat().st_mtime, reverse=True)
    for hbjson in hbjsons:
        if not read_hbjson_identity(hbjson, design_id):
            continue
        # Pair the SQL only with an OSW in the same exported model folder.
        # This prevents similarly named test models/runs from being mistaken
        # for the selected CSV case.
        osws = [p for p in hbjson.parent.rglob("workflow.osw") if workflow_references(p, hbjson)]
        if not osws:
            continue
        for osw in osws:
            sql_files = sorted((p for p in osw.parent.rglob("eplusout.sql")
                                if p.is_file() and p.stat().st_size),
                               key=lambda p: p.stat().st_mtime, reverse=True)
            for sql in sql_files:
                try:
                    verify_energyplus_run(sql)
                    area, energy_gj, eui = extract_sql(sql)
                    if not values_match(old_row, area, eui):
                        continue
                    return {"csv_index": case_index, "design_id": design_id, "floor_area_m2": "{:.6f}".format(area),
                            "annual_site_energy_gj": "{:.6f}".format(energy_gj), "eui_kwh_m2_year": "{:.6f}".format(eui),
                            "status": "SUCCESS", "run_origin": "VERIFIED_EXISTING", "error": "",
                            "hbjson_path": str(hbjson), "osw_path": str(osw), "sql_path": str(sql),
                            "updated_at": datetime.now().astimezone().isoformat(timespec="seconds")}
                except Exception:
                    continue
    return None


def verified_resume_row(row, source):
    if row.get("status") != "SUCCESS":
        return False
    design_id = source["design_id"].strip()
    hbjson = Path(row.get("hbjson_path", ""))
    osw = Path(row.get("osw_path", ""))
    sql = Path(row.get("sql_path", ""))
    if not read_hbjson_identity(hbjson, design_id) or not workflow_references(osw, hbjson):
        return False
    try:
        verify_energyplus_run(sql)
        area, energy_gj, eui = extract_sql(sql)
        return values_match(row, area, eui)
    except Exception:
        return False


def normalize_osw_paths(workflow, source_dir):
    path_keys = {"weather_file", "measure_paths", "file_paths", "model_json", "schedule_csv_dir", "simulation_parameter_json"}
    def walk(node):
        if isinstance(node, dict):
            for key, value in list(node.items()):
                if key in path_keys:
                    if isinstance(value, list):
                        node[key] = [str((source_dir / v).resolve()) if isinstance(v, str) and not Path(v).is_absolute() else v for v in value]
                    elif isinstance(value, str) and not Path(value).is_absolute():
                        node[key] = str((source_dir / value).resolve())
                else:
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
    walk(workflow)
    return workflow


def run_case(index, source, result, run_root, cli, timeout, dry_run=False):
    design_id = source["design_id"].strip()
    openstudio_dir = Path(run_root) / design_id / design_id / "openstudio"
    hbjson = openstudio_dir / (design_id + ".hbjson")
    osw = openstudio_dir / "workflow.osw"
    result.update({"hbjson_path": str(hbjson), "osw_path": str(osw), "status": "RUNNING", "run_origin": "NEW_RUN", "error": ""})
    if not hbjson.is_file() or not osw.is_file() or hbjson.stat().st_size == 0 or osw.stat().st_size == 0:
        raise FileNotFoundError("Missing case-specific HBJSON/OSW under {}".format(openstudio_dir))
    if not read_hbjson_identity(hbjson, design_id):
        raise ValueError("HBJSON identity mismatch for {}".format(design_id))
    with open(str(osw), "r", encoding="utf-8") as stream:
        workflow = normalize_osw_paths(json.load(stream), openstudio_dir)
    if not workflow_references(osw, hbjson):
        raise ValueError("OSW does not reference this case's HBJSON")
    if dry_run:
        result["status"] = "READY"
        return
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    run_dir = Path(run_root) / ".facadeai_batch_runs" / design_id / stamp
    run_dir.mkdir(parents=True, exist_ok=False)
    staged_osw = run_dir / "workflow.osw"
    staged_osw.write_text(json.dumps(workflow, indent=2), encoding="utf-8")
    started = time.time()
    command = [str(cli)]
    for measure_path in workflow.get("measure_paths", []):
        include_dir = Path(measure_path)
        if include_dir.name.casefold() == "measures":
            include_dir = include_dir.parent
        command.extend(["-I", str(include_dir)])
    command.extend(["run", "--show-stdout", "-w", str(staged_osw)])
    proc = subprocess.run(command, cwd=str(run_dir), capture_output=True, text=True, timeout=timeout, check=False)
    log = run_dir / "openstudio_batch.log"
    log.write_text("COMMAND: {}\nEXIT: {}\n\n--- STDOUT ---\n{}\n--- STDERR ---\n{}".format(
        " ".join(command), proc.returncode, proc.stdout or "", proc.stderr or ""), encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError("OpenStudio exit {} (see {})".format(proc.returncode, log))
    sql_files = [p for p in run_dir.rglob("eplusout.sql") if p.is_file() and p.stat().st_size]
    if not sql_files:
        raise FileNotFoundError("Fresh run produced no eplusout.sql")
    sql = max(sql_files, key=lambda p: p.stat().st_mtime)
    verify_energyplus_run(sql, started)
    area, energy_gj, eui = extract_sql(sql)
    result.update({"floor_area_m2": "{:.6f}".format(area), "annual_site_energy_gj": "{:.6f}".format(energy_gj),
                   "eui_kwh_m2_year": "{:.6f}".format(eui), "status": "SUCCESS", "sql_path": str(sql),
                   "eui_basis": "Annual Total Site Energy / Total Building Area; kWh/m2-year"})



# This module is imported by facadeai_case.py and the Rhino 8 IronPython driver.
