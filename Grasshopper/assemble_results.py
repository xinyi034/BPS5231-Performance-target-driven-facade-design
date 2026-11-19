#!/usr/bin/env python3
"""Build the 160-case provenance-aware CSV/XLSX from supplied source records.

This utility never runs EnergyPlus. It verifies each automated Index 80-159 SQL
before recording those rows as successful. Index 0-79 remains explicitly
teammate-provided and unverified unless a separate verified workflow result is
later recorded by facadeai_case.py.
"""
import csv
import json
import sys
from pathlib import Path

import facadeai_pipeline as pipeline
from facadeai_case import CONFIG_PATH, load_config, sync_workbook, write_csv


def read_dicts(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    ids = [row.get("design_id", "").strip() for row in rows]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate design_id in {}".format(path))
    return {row["design_id"].strip(): row for row in rows if row.get("design_id")}


def main():
    cfg, resolve = load_config()
    sources = pipeline.read_cases(resolve(cfg["input_csv"]))
    teammate = read_dicts(resolve(cfg["teammate_results_csv"]))
    automated_path = resolve("data/results/FacadeAI_Results_80_159_AsRun.csv")
    automated = read_dicts(automated_path)
    results = []
    for index, source in enumerate(sources):
        design_id = source["design_id"].strip()
        row = {field: source.get(field, "") for field in pipeline.FIELDS}
        row.update({"csv_index": index, "design_id": design_id, "floor_area_m2": "",
                    "annual_site_energy_gj": "", "eui_kwh_m2_year": "", "status": "NOT_PROVIDED",
                    "run_origin": "", "error": "", "hbjson_path": "", "osw_path": "",
                    "sql_path": "", "updated_at": "", "provenance": "",
                    "source_status": ""})
        if index < 80:
            old = teammate.get(design_id, {})
            reported_eui = old.get("eui_simulated", "")
            reported_area = old.get("floor_area_m2", "")
            row.update({"status": "PROVIDED_UNVERIFIED" if reported_eui or reported_area else "NOT_PROVIDED",
                        "run_origin": "TEAMMATE_RECORDED_NOT_INDEPENDENTLY_VERIFIED",
                        "provenance": "Teammate-provided source record; not validated by the packaged SQL verification workflow.",
                        "source_status": old.get("simulation_status", "")})
            if reported_eui:
                row["eui_kwh_m2_year"] = reported_eui
            if reported_area:
                row["floor_area_m2"] = reported_area
            if old.get("output_path"):
                row["sql_path"] = old["output_path"]
            if old.get("notes"):
                row["error"] = "Source note: " + old["notes"]
        else:
            old = automated.get(design_id)
            if not old or int(old.get("csv_index", -1)) != index:
                raise ValueError("Missing or mismatched automated result at Index {} ({})".format(index, design_id))
            if old.get("simulation_status") != "SUCCESS":
                raise ValueError("Automated source result is not successful: Index {} {}".format(index, design_id))
            verified = {"status": "SUCCESS", "floor_area_m2": old.get("floor_area_m2", ""),
                        "eui_kwh_m2_year": old.get("eui_simulated", ""),
                        "hbjson_path": old.get("hbjson_path", ""), "osw_path": old.get("osw_path", ""),
                        "sql_path": old.get("sql_path", "")}
            if not pipeline.verified_resume_row(verified, source):
                raise ValueError("SQL/HBJSON/OSW verification failed at Index {} ({})".format(index, design_id))
            row.update({"status": "SUCCESS", "floor_area_m2": old["floor_area_m2"],
                        "eui_kwh_m2_year": old["eui_simulated"],
                        "hbjson_path": old.get("hbjson_path", ""), "osw_path": old.get("osw_path", ""),
                        "sql_path": old.get("sql_path", ""), "run_origin": "AUTOMATED_SQL_VERIFIED",
                        "provenance": "Automated workflow result; HBJSON identity, OSW model reference, EnergyPlus completion log, SQL and EUI were verified.",
                        "source_status": old.get("simulation_status", ""),
                        "updated_at": old.get("updated_at", "")})
        results.append(row)

    target_csv = resolve(cfg["results_csv"])
    write_csv(target_csv, results)
    workbook = sync_workbook(cfg, resolve, results)
    print("Wrote {} rows; automated SQL-verified successes: 80; teammate rows independently verified here: 0".format(len(results)))
    print("CSV: {}".format(target_csv))
    print("Workbook: {}".format(workbook))
    return 0


if __name__ == "__main__":
    sys.exit(main())
