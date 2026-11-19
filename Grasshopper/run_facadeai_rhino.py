# Run with Rhino 8: _RunPythonScript "...\scripts\run_facadeai_rhino.py"
# Python 2.7-compatible Rhino driver. Uses the existing model, CSV reader,
# Case Index, List Items and ModelToOSM; no geometry or simulation assumptions change.
import io
import json
import os
import traceback
import time
import System
import Grasshopper
import Rhino
from System.Diagnostics import Process, ProcessStartInfo, ProcessWindowStyle

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(SCRIPTS, os.pardir))
CONFIG_PATH = os.path.join(PROJECT, "config.json")
if not os.path.isfile(CONFIG_PATH):
    CONFIG_PATH = os.path.join(PROJECT, "config.example.json")
with io.open(CONFIG_PATH, "r", encoding="utf-8") as config_stream:
    CONFIG = json.load(config_stream)

def config_path(key):
    value = CONFIG[key]
    if os.path.isabs(value):
        return value
    return os.path.abspath(os.path.join(PROJECT, value))

WORKING_GHX = config_path("grasshopper_model")
CSV_PATH = config_path("input_csv")
SIM_ROOT = config_path("simulation_root")
CASE_RUNNER = os.path.join(SCRIPTS, "facadeai_case.py")
PYTHON_EXE = config_path("python_exe")
FIRST = int(CONFIG.get("start_index", 0))
LAST = int(CONFIG.get("end_index", 159))
EXPECTED_INDEX_80 = "G12_W30_S00"

CASE_INDEX_ID = System.Guid("228461f8-bdea-47ff-9f41-6f32565f843d")
MANUAL_GATE_ID = System.Guid("ad015aa2-9c7f-457b-8357-a5cb39c33cb2")
WRITE_TOGGLE_ID = System.Guid("e6abb2a6-9ec8-4027-9778-671888281ae8")
MODEL_TO_OSM_TOGGLE_ID = System.Guid("1a2f8a89-9fcc-4a63-aec5-bf9bbeb22f34")
RUN_OSM_TOGGLE_ID = System.Guid("8694240d-ac1a-4489-8ebc-c30c8f544d61")
RUNNER_ID = System.Guid("1905e43a-c385-4dad-8b05-08a84af15531")
CSV_PATH_PANEL_ID = System.Guid("4ed78ee6-3346-4f20-aebc-c8eb2711a867")
MODEL_OUTPUT_PANEL_ID = System.Guid("02fd4665-5fa3-4eef-ab6b-3b8e347eeba7")
OLD_BATCH_START_ID = System.Guid("16c77153-b217-49f6-9e80-67114bc6c85d")
OLD_CONTROLLER_START_ID = System.Guid("c561445a-b197-462d-b0c5-3146b421e10d")
OLD_SCHEDULER_START_ID = System.Guid("ca7897ff-579c-4852-be12-9c8f9626481e")
OLD_ADVANCE_ID = System.Guid("15b65b93-0f6f-4341-839a-69186db83bbf")

# Existing List Item components and their single outputs in the original GHX.
CSV_OUTPUTS = {
    "design_id": System.Guid("a9acc8c4-bdff-4953-8f2d-1a7393bd9f28"),
    "glazing_id": System.Guid("aa6f032f-81b8-4ef5-b610-d728a87e9a63"),
    "wwr": System.Guid("021ef1d8-fcba-4faf-83d7-4025465a20a0"),
    "u_value": System.Guid("534f1b65-ee4a-4a93-9a2b-ab10e315e910"),
    "shgc": System.Guid("dc36a454-3898-4f21-a1b5-f713abaf9d79"),
    "shading_depth_m": System.Guid("27cf9b24-e738-4f49-a693-2e54e1b2449f"),
    "glazing_name": System.Guid("c87caaa5-1b85-4ce3-91d7-f14f450e2930")
}


def write_log(message):
    text = "[{}] {}".format(time.strftime("%Y-%m-%d %H:%M:%S"), message)
    Rhino.RhinoApp.WriteLine(text)
    folder = os.path.join(SIM_ROOT, ".facadeai_logs")
    if not os.path.isdir(folder):
        os.makedirs(folder)
    with io.open(os.path.join(folder, "rhino_batch.log"), "a", encoding="utf-8") as stream:
        stream.write(text + u"\n")


def parse_csv_line(line):
    values = []
    value = u""
    quoted = False
    pos = 0
    while pos < len(line):
        char = line[pos]
        if char == u'"':
            if quoted and pos + 1 < len(line) and line[pos + 1] == u'"':
                value += u'"'
                pos += 1
            else:
                quoted = not quoted
        elif char == u"," and not quoted:
            values.append(value)
            value = u""
        else:
            value += char
        pos += 1
    values.append(value)
    return values


def read_cases():
    raw = System.IO.File.ReadAllText(CSV_PATH, System.Text.Encoding.UTF8)
    raw = raw.lstrip(u"\ufeff").replace(u"\r", u"")
    lines = [line for line in raw.split(u"\n") if line.strip()]
    headers = parse_csv_line(lines[0])
    rows = []
    for line in lines[1:]:
        values = parse_csv_line(line)
        rows.append(dict((headers[i], values[i]) for i in range(min(len(headers), len(values)))))
    if len(rows) != 160 or rows[80]["design_id"].strip() != EXPECTED_INDEX_80:
        raise ValueError("CSV must contain 160 rows and Index 80 must be " + EXPECTED_INDEX_80)
    if FIRST < 0 or LAST > 159 or FIRST > LAST:
        raise ValueError("Configured index range must satisfy 0 <= start <= end <= 159")
    return rows


def find_object(document, instance_id):
    for obj in document.Objects:
        if obj.InstanceGuid == instance_id:
            return obj
    return None


def set_slider(slider, value):
    slider.SetSliderValue(System.Decimal(value))
    slider.ExpireSolution(True)

def set_panel(panel, value):
    if panel is None or not hasattr(panel, "UserText"):
        raise ValueError("Existing model path panel is missing or not editable")
    panel.UserText = value
    panel.ExpireSolution(True)


def solve(document):
    document.NewSolution(False)


def one_output_value(component):
    if component is None or component.Params.Output.Count < 1:
        raise ValueError("Expected CSV selector component/output is missing")
    items = list(component.Params.Output[0].VolatileData.AllData(True))
    if len(items) != 1:
        raise ValueError("Expected one CSV value from " + str(component.NickName))
    item = items[0]
    if hasattr(item, "ScriptVariable"):
        return item.ScriptVariable()
    if hasattr(item, "Value"):
        return item.Value
    return item


def verify_selected_case(document, expected):
    for name, instance_id in CSV_OUTPUTS.items():
        component = find_object(document, instance_id)
        actual = one_output_value(component)
        wanted = expected[name]
        if name == "design_id" or name in ("glazing_id", "glazing_name"):
            if str(actual).strip() != wanted.strip():
                raise ValueError("CSV {} mismatch: {} != {}".format(name, actual, wanted))
        else:
            if abs(float(actual) - float(wanted)) > 0.000001:
                raise ValueError("CSV {} mismatch: {} != {}".format(name, actual, wanted))


def quote_arg(value):
    # CreateProcess uses the Windows command-line quoting rules. Paths in this
    # project contain spaces, so quote every argument and escape backslashes
    # immediately before embedded quotes/trailing quotes.
    value = str(value)
    out = '"'
    slashes = 0
    for char in value:
        if char == "\\":
            slashes += 1
        elif char == '"':
            out += "\\" * (slashes * 2 + 1) + '"'
            slashes = 0
        else:
            out += "\\" * slashes + char
            slashes = 0
    return out + "\\" * (slashes * 2) + '"'


def clean_python_environment(info):
    # Rhino embeds IronPython and may pass its Python runtime paths to children.
    # Start the standalone CPython with a clean interpreter environment.
    env = info.EnvironmentVariables
    keys = list(env.Keys)
    for key in keys:
        upper = str(key).upper()
        if (upper.startswith("PYTHON") or upper.startswith("CONDA_") or
                upper in ("VIRTUAL_ENV", "__PYVENV_LAUNCHER__")):
            env.Remove(key)


def call_python(args, timeout_ms):
    info = ProcessStartInfo()
    info.FileName = PYTHON_EXE
    info.Arguments = " ".join([quote_arg(a) for a in args])
    info.WorkingDirectory = SCRIPTS
    info.UseShellExecute = False
    info.CreateNoWindow = True
    info.WindowStyle = ProcessWindowStyle.Hidden
    info.RedirectStandardOutput = True
    info.RedirectStandardError = True
    clean_python_environment(info)
    process = Process.Start(info)
    if process is None:
        raise RuntimeError("Could not start Python subprocess: {} {} (cwd {})".format(
            PYTHON_EXE, info.Arguments, SCRIPTS))
    timed_out = not process.WaitForExit(timeout_ms)
    if timed_out:
        process.Kill()
        process.WaitForExit()
    stdout = process.StandardOutput.ReadToEnd()
    stderr = process.StandardError.ReadToEnd()
    write_log("Python subprocess: {} {} (cwd={})".format(PYTHON_EXE, info.Arguments, SCRIPTS))
    write_log("Python stdout: {}".format(stdout.strip() or "<empty>"))
    write_log("Python stderr: {}".format(stderr.strip() or "<empty>"))
    if timed_out:
        raise RuntimeError("Python subprocess timed out. stdout:\n{}\nstderr:\n{}".format(stdout, stderr))
    return process.ExitCode, stdout, stderr


def call_case_runner(args, timeout_ms):
    return call_python([CASE_RUNNER] + args, timeout_ms)


def validate_python_runtime():
    code = "import encodings, sqlite3, openpyxl; print('PYTHON_RUNTIME_OK', openpyxl.__version__)"
    result, stdout, stderr = call_python(["-c", code], 60000)
    if result != 0 or "PYTHON_RUNTIME_OK" not in stdout:
        raise RuntimeError("Python runtime validation failed, exit code {}. stdout:\n{}\nstderr:\n{}".format(
            result, stdout, stderr))
    write_log("Verified standalone Python runtime imports encodings, sqlite3 and openpyxl: {}".format(stdout.strip()))


def verify_export(index, case, started):
    folder = os.path.join(SIM_ROOT, case, case, "openstudio")
    hbjson = os.path.join(folder, case + ".hbjson")
    osw = os.path.join(folder, "workflow.osw")
    deadline = time.time() + 600
    previous = None
    while time.time() < deadline:
        if os.path.isfile(hbjson) and os.path.isfile(osw):
            snapshot = (os.path.getsize(hbjson), os.path.getmtime(hbjson),
                        os.path.getsize(osw), os.path.getmtime(osw))
            fresh = snapshot[1] >= started - 2 and snapshot[3] >= started - 2
            if snapshot[0] > 0 and snapshot[2] > 0 and fresh and snapshot == previous:
                try:
                    with io.open(hbjson, "r", encoding="utf-8") as stream:
                        model = json.load(stream)
                    with io.open(osw, "r", encoding="utf-8") as stream:
                        workflow = json.load(stream)
                except Exception:
                    previous = snapshot
                    time.sleep(1)
                    continue
                identity = model.get("identifier") or model.get("display_name")
                if identity != case or not model.get("rooms"):
                    raise ValueError("HBJSON identity/rooms check failed for " + case)
                refs = []
                for step in workflow.get("steps", []):
                    if step.get("measure_dir_name") == "from_honeybee_model":
                        ref = step.get("arguments", {}).get("model_json")
                        if ref:
                            if not os.path.isabs(ref):
                                ref = os.path.join(folder, ref)
                            refs.append(os.path.normcase(os.path.abspath(ref)))
                if len(refs) != 1 or refs[0] != os.path.normcase(os.path.abspath(hbjson)):
                    raise ValueError("OSW model reference does not match " + case)
                return hbjson, osw
            previous = snapshot
        time.sleep(1)
    raise RuntimeError("Timed out after 10 minutes waiting for fresh, stable HBJSON/OSW: " + case)


def main():
    if not os.path.isfile(WORKING_GHX):
        raise IOError("Prepared working GHX is missing: " + WORKING_GHX)
    if not os.path.isfile(PYTHON_EXE) or not os.path.isfile(CASE_RUNNER):
        raise IOError("Standalone Python or case processor is missing: {} / {}".format(PYTHON_EXE, CASE_RUNNER))
    validate_python_runtime()

    # Always open the specified working copy so a cached GH document cannot run.
    gh_io = Grasshopper.Kernel.GH_DocumentIO()
    if not gh_io.Open(WORKING_GHX):
        raise RuntimeError("Could not open working model: " + WORKING_GHX)
    document = gh_io.Document
    Grasshopper.Instances.DocumentServer.AddDocument(document)
    Grasshopper.Instances.ActiveCanvas.Document = document
    write_toggle = find_object(document, System.Guid("e6abb2a6-9ec8-4027-9778-671888281ae8"))
    model_toggle = find_object(document, MODEL_TO_OSM_TOGGLE_ID)
    run_toggle = find_object(document, RUN_OSM_TOGGLE_ID)
    batch_start = find_object(document, OLD_BATCH_START_ID)
    old_controller_start = find_object(document, OLD_CONTROLLER_START_ID)
    old_scheduler_start = find_object(document, OLD_SCHEDULER_START_ID)
    old_advance = find_object(document, OLD_ADVANCE_ID)
    gate = find_object(document, MANUAL_GATE_ID)
    index_slider = find_object(document, CASE_INDEX_ID)
    csv_path_panel = find_object(document, CSV_PATH_PANEL_ID)
    model_output_panel = find_object(document, MODEL_OUTPUT_PANEL_ID)
    if None in (write_toggle, model_toggle, run_toggle, batch_start, old_controller_start,
                old_scheduler_start, old_advance, gate, index_slider, csv_path_panel, model_output_panel):
        raise RuntimeError("Working copy is missing an existing Case Index or simulation control")

    # Disable the earlier runner; use the model's existing manual Case Index.
    batch_start.Value = False
    old_controller_start.Value = False
    old_scheduler_start.Value = False
    old_advance.Value = False
    model_toggle.Value = False
    run_toggle.Value = False
    gate.SetSliderValue(System.Decimal(0))
    write_toggle.Value = False
    set_panel(csv_path_panel, CSV_PATH)
    for obj in (batch_start, old_controller_start, old_scheduler_start, old_advance,
                model_toggle, run_toggle, gate, write_toggle):
        obj.ExpireSolution(True)
    solve(document)

    rows = read_cases()
    successes = 0
    failures = 0
    write_log("Running configured CSV Index {}-{}; verified successful cases are preserved and skipped.".format(FIRST, LAST))

    for index in range(FIRST, LAST + 1):
        case = rows[index]["design_id"].strip()
        case_result_written = False
        write_log("Index {} {}: checking validated prior result".format(index, case))
        try:
            check, check_stdout, check_stderr = call_case_runner(
                ["--index", str(index), "--check-only"], 120000)
            if check == 0:
                successes += 1
                write_log("SKIP VERIFIED {}".format(case))
                continue
            if check != 10:
                raise RuntimeError("Index {} precheck failed, exit code {}. stdout:\n{}\nstderr:\n{}".format(
                    index, check, check_stdout, check_stderr))
            write_log("Index {} precheck passed: {} (exit 10 means no verified prior result; ready for fresh export).".format(index, case))

            # First recompute with write disabled, ensuring all CSV parameters reach the model.
            write_toggle.Value = False
            set_panel(model_output_panel, os.path.join(SIM_ROOT, case))
            set_slider(index_slider, index)
            write_toggle.ExpireSolution(True)
            solve(document)
            verify_selected_case(document, rows[index])

            # ModelToOSM writes HBJSON/OSW only. OpenStudio is run after verified export.
            started = time.time()
            write_toggle.Value = True
            write_toggle.ExpireSolution(True)
            solve(document)
            write_toggle.Value = False
            write_toggle.ExpireSolution(True)
            solve(document)
            verify_export(index, case, started)
            write_log("Index {} export verified: {}".format(index, case))

            exit_code, run_stdout, run_stderr = call_case_runner(
                ["--index", str(index)], (180 * 60 + 10) * 1000)
            case_result_written = True
            if exit_code == 0:
                successes += 1
                write_log("Index {} simulation result checkpointed: {}".format(index, case))
            else:
                raise RuntimeError("Index {} simulation failed, exit code {}. stdout:\n{}\nstderr:\n{}".format(
                    index, exit_code, run_stdout, run_stderr))

        except Exception as exc:
            failures += 1
            detail = traceback.format_exc()
            if not case_result_written:
                try:
                    call_case_runner(["--index", str(index), "--record-export-failure", "--error", detail], 120000)
                except Exception:
                    pass
            write_log("Index {} failed; stopping batch for debugging. Full exception and traceback:\n{}".format(index, detail))
            Rhino.RhinoApp.WriteLine("FacadeAI stopped at Index {}. Full exception/traceback is in rhino_batch.log: {}".format(index, exc))
            break

    # Retry workbook synchronization after the simulations. This is a SQL/CSV
    # validation and workbook write only; it never starts EnergyPlus.
    try:
        sync_code, sync_stdout, sync_stderr = call_case_runner(["--sync-workbook"], 120000)
        if sync_code == 0:
            write_log("Final workbook sync completed. stdout:\n{}\nstderr:\n{}".format(sync_stdout, sync_stderr))
        else:
            write_log("Final workbook sync deferred; verified CSV/SQL remain saved. exit {} stdout:\n{}\nstderr:\n{}".format(
                sync_code, sync_stdout, sync_stderr))
    except Exception:
        write_log("Final workbook sync failed; verified CSV/SQL remain saved:\n{}".format(traceback.format_exc()))

    write_log("Batch ended: {} verified successes; {} failures; configured range {}-{}.".format(successes, failures, FIRST, LAST))
    Rhino.RhinoApp.WriteLine("FacadeAI range {}-{} ended: {} successful, {} failed.".format(FIRST, LAST, successes, failures))


try:
    main()
except Exception as error:
    Rhino.RhinoApp.WriteLine("FacadeAI batch stopped before simulation: " + str(error))
    raise
