import datetime
import atexit
import hashlib
import inspect
import json
import os
import sys
import time
import importlib.util
import signal
import subprocess
import tempfile
import uuid
from pathlib import Path

from iterbrow_runtime.hotload_manager import HotloadManager, IterHeartbeat
# PORT: Independently bound complete input projection and model output.
from iterbrow_runtime.request_budget import RequestBudgetExceeded, project_request, working_input_limit, relevant_memory, memory_context, rotate_experience
from iterbrow_runtime.episodic_history import archive_text
from iterbrow_runtime.atomspace_store import _atomic_json
# PORT: Retain oversized observations for reading without repeating tool effects.
from iterbrow_runtime import tool_results as retained_text
from iterbrow_runtime.tool_results import capture_tool_output
from iterbrow_runtime.work_inquiry import question_context
from iterbrow_runtime.working_handoff import working_context, working_record, runtime_context
from iterbrow_runtime.loop_continuity import resume_event_wait

# Shared rule for "which memory/ files are prompt memory" (tools/_memory_projection.py).
# iter.py is the authority on the projection; self_improve.py and auto_improve.py
# measure the same set through this module so the three can never drift apart
# again (2026-09-17: they had, pinning memory_efficiency at 0 and pain at ~20,000).
_TOOLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)
import _memory_projection


def is_transient_provider_error(error):
    """A provider outage is not evidence that a hot-loaded component broke."""
    return isinstance(error, (openai.APIConnectionError, openai.RateLimitError)) or (
        isinstance(error, openai.APIStatusError) and error.status_code >= 500
    )


def is_rejected_model_request(error):
    """Malformed/oversized input needs a change, not an identical API retry."""
    return isinstance(error, openai.APIStatusError) and error.status_code in (400, 413, 422)

# --------------------------------------------------------------------
# 0. Configuration:
# --------------------------------------------------------------------
MAX_MEMORY_CHARS = 20000 #When memory turns into an index (raised from 3000: that cap was tuned for the old browser/WASM build and was tripping constantly on real desktop usage, flooding the agent with "FIX THIS FIRST" directives that starved out chat replies)
LLM_TIMEOUT = 600
KEEP_REASONING_IN_EPISODE = True
PRINT_CALLS = False
MAX_TOOL_CALLS = 10
MAX_TOOL_OUTPUT_CHARS = 5000
MAX_EXPERIENCE_SIZE = 100   # soft tail limit; active work is never discarded
RETAIN_EXPERIENCE_SIZE = 80 # older task history is archived before leaving the tail
MAX_FAST_STEPS = 50
SLOW_STEP_DELAY = 10
ERROR_RECOVERY_TIME = 1 #after how long to retry when exception occurs
DEFAULT_DELAY = 0 #default delay added irregard of whether in slow mode
# PORT: User-authorized per-request allowances; input uses a labeled estimate.
MAX_INPUT_TOKENS = 45000
MAX_TOKENS = 45000
INIT_WAIT = 10
MAX_TOOLS = 80  # raised from 30: the tools/ directory has grown to 55+ public tools across past
                # feature work, and this cap silently truncated the ALPHABETICALLY SORTED tool list -
                # `send.py` (and 20+ other tools including remember, self_improve, support, websearch,
                # tab_autonomy, start_new_task) sorted past position 30 and were completely invisible
                # to the model for an extended period. This was the real cause of an incident where the
                # model correctly reported "send isn't in my available tools" (not a hallucination) and
                # could not respond to the user despite the silent_streak safety net repeatedly demanding
                # it call send. See PROTECTED_TOOL_NAMES below for defense-in-depth against a recurrence.
MAX_TOOL_DESCRIPTION_CHARS = 500
DYNAMIC_TIMEOUT = 15
ITER_ROOT = Path(__file__).resolve().parent
# Direct ``python iter.py`` launches do not pass through Electron's environment.
# Export the same canonical-root contract here so every dynamic subprocess can
# resolve application state independently of its immutable generation path.
os.environ["ITER_DIR"] = str(ITER_ROOT)
GATE_LOG_PATH = Path("transformations/.runtime/gate_health.log")  # trail for gate ALLOW-via-fail-open/crash cases, which iter.py's dispatch loop otherwise never surfaces (see _log_gate_issue)
MODEL = os.getenv("LLM_MODEL", "mlx-community/gemma-4-26b-a4b-it-4bit")
BASE_URL = os.getenv("BASE_URL", "http://192.168.64.1:2277/v1")
API_KEY = os.getenv("AI_API_KEY", "dummy")
PROVIDER = os.getenv("LLM_PROVIDER", "compatible")
REASONING_EFFORT = os.getenv("LLM_REASONING_EFFORT") or "low"

# PORT: Optional canonical OpenRouter routing is explicit and fail-closed.
def model_request_extra_body(base_url, settings_path):
    from urllib.parse import urlsplit
    import re

    body = {"enable_thinking": True}
    if urlsplit(base_url).hostname != "openrouter.ai":
        return body
    try:
        settings = json.loads(settings_path.read_text())
    except FileNotFoundError:
        return body
    except (OSError, ValueError) as error:
        raise ValueError("Cannot read canonical OpenRouter routing settings") from error
    if not isinstance(settings, dict):
        raise ValueError("Canonical routing settings must be an object")
    if settings.get("provider") != "openrouter":
        return body
    configured = settings.get("openrouter", {})
    if not isinstance(configured, dict):
        raise ValueError("OpenRouter settings must be an object")
    if "routing" not in configured:
        return body
    routing = configured["routing"]
    if not isinstance(routing, dict) or set(routing) != {"only", "allow_fallbacks"}:
        raise ValueError("OpenRouter routing requires only and allow_fallbacks")
    providers = routing["only"]
    if (not isinstance(providers, list) or not 1 <= len(providers) <= 4
            or any(not isinstance(provider, str)
                   or not re.fullmatch(r"[a-z0-9][a-z0-9._/-]{0,63}", provider)
                   for provider in providers)
            or len(set(providers)) != len(providers)):
        raise ValueError("OpenRouter routing.only requires 1..4 distinct provider slugs")
    if type(routing["allow_fallbacks"]) is not bool:
        raise ValueError("OpenRouter routing.allow_fallbacks must be an explicit boolean")
    body["provider"] = {"only": list(providers), "allow_fallbacks": routing["allow_fallbacks"]}
    return body

# --------------------------------------------------------------------
# 1. Dynamic execution:
# --------------------------------------------------------------------
def dynamic_worker():
    path = Path(sys.argv[2])
    function = sys.argv[3]
    result_path = Path(sys.argv[4])
    payload_path = Path(sys.argv[5])
    execution = {"success": True, "state": "returned", "scope": "invocation",
                 "task_fulfillment": "unverified"}
    invoking_tool = False
    try:
        # A hot-load generation is a complete component tree.  Put the exact
        # component directory first so a promoted tool can import helper files
        # from its own immutable generation rather than mixing generations.
        component_dir = str(path.resolve().parent)
        if component_dir not in sys.path:
            sys.path.insert(0, component_dir)
        payload = json.loads(payload_path.read_text())
        spec = importlib.util.spec_from_file_location("_dynamic_" + path.stem, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if function == "__description__":
            result = str(module.DESCRIPTION)
        elif function == "__tool_metadata__":
            signature_parameters = inspect.signature(module.run).parameters.values()
            parameters = [
                parameter for parameter in signature_parameters
                if parameter.kind not in (
                    inspect.Parameter.VAR_POSITIONAL,
                    inspect.Parameter.VAR_KEYWORD,
                )
            ]
            description = str(module.DESCRIPTION)
            if len(description) > MAX_TOOL_DESCRIPTION_CHARS:
                description = description[:MAX_TOOL_DESCRIPTION_CHARS] + " [DESCRIPTION TRUNCATED]"
            result = {
                "description": description,
                "parameters": [parameter.name for parameter in parameters],
                "required": [
                    parameter.name for parameter in parameters
                    if parameter.default is inspect.Parameter.empty
                ],
            }
        else:
            invoking_tool = function == "run"
            result = getattr(module, function)(*payload.get("args", []), **payload.get("kwargs", {}))
            invoking_tool = False
            execution = getattr(result, "execution_outcome", execution)
            if function != "transform" and result is not None:
                result = str(result)
        output = {"ok": True, "result": result, "execution": execution}
    except BaseException as error:
        output = {"ok": False, "error": f"{type(error).__name__}: {error}"}
        if invoking_tool and isinstance(error, retained_text.ToolInputError):
            output["input_rejected"] = True
        if (getattr(error, "execution_outcome", None)
                and (not isinstance(error, retained_text.ToolInputError) or invoking_tool)):
            output["execution"] = error.execution_outcome
    try:
        result_path.write_text(json.dumps(output, ensure_ascii=False))
    except BaseException as error:
        result_path.write_text(json.dumps({"ok": False, "error": f"Result serialization failed: {type(error).__name__}: {error}"}, ensure_ascii=False))

_DYNAMIC_WORKERS = set()


def stop_dynamic_workers():
    """Stop only process groups spawned by this loop, including their children."""
    for worker in tuple(_DYNAMIC_WORKERS):
        try:
            os.killpg(worker.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    for worker in tuple(_DYNAMIC_WORKERS):
        try:
            worker.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(worker.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        worker.wait()
        _DYNAMIC_WORKERS.discard(worker)


def _stop_loop(signum, _frame):
    stop_dynamic_workers()
    raise SystemExit(128 + signum)


def invoke_dynamic(path, function, *args, **kwargs):
    process = None
    # These existing memory tools may use a 30s embedding request and a 30s
    # durable commit. Killing them at 15s loses the reply, not the transaction.
    memory_writes = {"remember", "memory_update", "forget", "support", "contradict",
                     "link_episode", "unlink_episode", "formalize_metta"}
    memory_write = function == "run" and Path(path).stem in memory_writes
    # The outer deadline is a hung-worker backstop, not a speed requirement.
    # Browser/AtomSpace reads already have 30s internal deadlines; give those
    # handlers time to return their own useful errors. Composed/build actions
    # need a larger envelope. Metadata and transformations keep their fast bound.
    timeout = DYNAMIC_TIMEOUT
    if function == "run":
        timeout = 75 if memory_write else {
            "chroma_query": 40, "eval": 180, "shell": 180, "python": 180,
            "self_improve": 180, "preview": 180, "device_capture": 180,
            "lm_studio_chat": 180,
        }.get(Path(path).stem, 60)
    result_fd, result_file = tempfile.mkstemp(prefix="iter-result-", suffix=".json")
    payload_fd, payload_file = tempfile.mkstemp(prefix="iter-payload-", suffix=".json")
    try:
        os.close(result_fd)
        os.close(payload_fd)
        Path(payload_file).write_text(json.dumps({"args": args, "kwargs": kwargs}, ensure_ascii=False))
        # DEAD-CODE CLEANUP (2026-09-13): this used to special-case a channel named
        # "terminal" to inherit real stdin for interactive receive() calls, but the
        # channel file has been "_terminal.py" (stem "_terminal") for a while now --
        # and receive()'s own channel scan already excludes underscore-prefixed
        # files, so this stem == "terminal" branch could never actually match
        # anything. Removed rather than reactivated: the app now has its own,
        # unrelated Terminal pane (terminal:start/run/interrupt/stop IPC), so
        # resurrecting the old stdin-inheriting channel risked two competing
        # "terminal" concepts. Dynamic invocations always run detached with no
        # stdin now, matching what effectively already happened.
        process = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--invoke", str(Path(path).resolve()), function, result_file, payload_file],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True
        )
        _DYNAMIC_WORKERS.add(process)
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            outcome = {"ok": False,
                       "error": f"TIMEOUT after {timeout}s in {Path(path).stem}.{function}; worker stopped. "
                                "Effects may be partial; inspect the outcome before repeating the action."}
            if function == "run" and Path(path).stem == "eval":
                outcome["error"] += " Partial check results and the interrupted check are in memory/regression_tests.json."
            if memory_write:
                outcome["error"] += "; memory-write outcome is UNCONFIRMED, not proof of failure. Check stored state before creating a replacement; retry the exact same text/IDs, not a reworded memory."
                outcome["execution"] = {"success": None, "state": "uncertain", "scope": "invocation", "task_fulfillment": "unverified"}
            return outcome
        try:
            return json.loads(Path(result_file).read_text())
        except Exception:
            return {"ok": False, "error": f"Dynamic process exited with code {process.returncode} without a valid result"}
    finally:
        if process is not None:
            if process.poll() is None:
                stop_dynamic_workers()
            _DYNAMIC_WORKERS.discard(process)
        for file in (result_file, payload_file):
            try:
                os.unlink(file)
            except FileNotFoundError:
                pass

if len(sys.argv) > 1 and sys.argv[1] == "--invoke":
    dynamic_worker()
    sys.exit(0)

# Only the main loop talks to the model. Importing its SDK in every isolated
# file-reading worker repeated the same startup cost dozens of times per turn.
import openai
from iterbrow_runtime.model_provider import request_view, call_model, request_kwargs

# PORT: normal Stop/quit cleans detached invocations, not the independent AtomSpace.
atexit.register(stop_dynamic_workers)
signal.signal(signal.SIGTERM, _stop_loop)
signal.signal(signal.SIGINT, _stop_loop)

# --------------------------------------------------------------------
# 2. Runtime helpers:
# --------------------------------------------------------------------
ACTIVE_COMPONENT_SNAPSHOT = None


def _component_paths(root_name):
    snapshot = ACTIVE_COMPONENT_SNAPSHOT
    root = snapshot["roots"][root_name] if snapshot else ITER_ROOT / root_name
    return [path for path in sorted(root.glob("*.py")) if not path.name.startswith("_")]


def _component_file(relative_path):
    relative = Path(relative_path)
    snapshot = ACTIVE_COMPONENT_SNAPSHOT
    if snapshot and relative.parts and relative.parts[0] in snapshot["roots"]:
        return snapshot["roots"][relative.parts[0]].joinpath(*relative.parts[1:])
    return ITER_ROOT / relative


def get_current_time():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _log_gate_issue(tool_name, detail):
    # The dispatch gate is deliberately fail-open (see tools/_metta_gate.py's
    # docstring): a broken/unavailable reasoning substrate must never be able
    # to stall tool dispatch. But that means a genuinely crashed or import-
    # broken gate module currently looks IDENTICAL, in the visible transcript,
    # to a perfectly healthy "nothing to advise" cycle -- gate_detail is only
    # ever surfaced to the LLM when gate_action == "ADVISE", never for plain
    # ALLOW. This writes a durable, out-of-band trail for those cases without
    # changing dispatch behavior or adding noise to the conversation itself.
    # Best-effort only -- must never raise or block dispatch.
    try:
        GATE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(GATE_LOG_PATH, "a") as f:
            f.write(json.dumps({"ts": get_current_time(), "tool": tool_name, "detail": detail}) + "\n")
    except Exception:
        pass

def receive(*, include_errors=True):
    events = []
    paths = _component_paths("channels")
    for path in paths:
        try:
            result = invoke_dynamic(path, "receive")
            if not result["ok"]:
                raise RuntimeError(result["error"])
            event = result["result"]
            if event:
                events.append("[" + path.stem + "] " + str(event))
        except Exception as error:
            if include_errors:
                events.append(f"[CHANNEL ERROR in {path}: {type(error).__name__}: {error}. Repair {path} if needed.]")
    return "\n".join(events)

def slow_wait_for_input(seconds=SLOW_STEP_DELAY, *, request_error=None):
    # PORT: A heartbeat needs no model call. Zero is an explicit event wait;
    # positive waits preserve timed retries and autonomous work chosen by Iter.
    deadline = time.monotonic() + seconds if seconds else None
    generation = ACTIVE_COMPONENT_SNAPSHOT["generation_id"]
    while deadline is None or time.monotonic() < deadline:
        time.sleep(1)
        HEARTBEAT.write(generation, "request_blocked" if request_error else "idle_wait", cycle_number,
                        hard_floor_ok=cycle_hard_floor_ok, detail=request_error or "")
        event_append = receive(include_errors=False) if request_error else receive()
        if event_append:
            return event_append
        if HOTLOAD_MANAGER.component_snapshot()["generation_id"] != generation:
            return "[Runtime components changed; resume with current state.]"
        # A due alarm does not shrink a rejected request. Leave it pending for
        # the next viable turn rather than waking the same failure every second.
        for alarm in ([] if request_error else Path("memory/alarms").glob("*")):
            try:
                if alarm.is_file() and float(alarm.name) <= time.time():
                    return ""  # The existing alarm transformation delivers it.
            except ValueError:
                continue
    return ""


def wait_for_request_change(error):
    global request_failure_notice
    request_failure_notice = f"{type(error).__name__}: {error}"
    if error.__cause__ is not None:
        request_failure_notice += f" Cause: {type(error.__cause__).__name__}: {error.__cause__}"
    request_failure_notice = request_failure_notice[:800]
    detail = (request_failure_notice + " "
              "Automatic retries paused; history is unchanged. Waiting for new input "
              "or a runtime revision. Restart alone does not reduce this request.")
    print("[request blocked] " + detail)
    return slow_wait_for_input(0, request_error=detail)

def save_experience(experience):
    _atomic_json("experience.json", experience)

# --------------------------------------------------------------------
# 3. Dynamic components:
# --------------------------------------------------------------------
# Tools that must NEVER be silently dropped by the MAX_TOOLS cap, regardless of
# alphabetical sort position or how large tools/ grows. `send` is the model's only
# way to talk to the user - if it's ever excluded again, the model can go silent
# indefinitely even though the silent_streak safety net keeps demanding it call
# send (that exact incident is why this list exists; see MAX_TOOLS comment above).
PROTECTED_TOOL_NAMES = {"send", "nop", "shell", "python", "start_new_task", "read_tool_result", "pin"}

def load_tools():
    # PORT: The kernel creates retained references, so their read-only consumer
    # shares the host lifecycle. An older/failed managed generation cannot remove
    # it or substitute a same-named wrapper. No execution or approval is cached.
    inops = {"read_tool_result": (
        ITER_ROOT / "iterbrow_runtime" / "tool_results.py",
        retained_text.DESCRIPTION, list(inspect.signature(retained_text.run).parameters), [],
    )}
    errors = []
    paths = [path for path in _component_paths("tools") if path.stem != "read_tool_result"]
    # Protected tools always go first so truncation (if the directory ever grows
    # past MAX_TOOLS again) can only ever drop non-essential tools.
    protected = [path for path in paths if path.stem in PROTECTED_TOOL_NAMES]
    rest = [path for path in paths if path.stem not in PROTECTED_TOOL_NAMES]
    ordered = protected + rest
    for path in ordered[:MAX_TOOLS - 1]:
        try:
            # PROMOTED (see tools/_metadata_static.py): if this exact file
            # content (path, mtime) was already verified == a real
            # subprocess result in a prior cycle, skip the subprocess and
            # use the trusted static result. Any failure here just means
            # "not trusted" -- falls back to today's exact real subprocess
            # call below, unchanged.
            try:
                from tools._metadata_static import get_trusted_tool_metadata
                metadata = get_trusted_tool_metadata(path)
            except Exception:
                metadata = None
            if metadata is None:
                result = invoke_dynamic(path, "__tool_metadata__")
                if not result["ok"]:
                    raise RuntimeError(result["error"])
                metadata = result["result"]
                try:
                    from tools._metadata_static import record_tool_metadata_verified
                    record_tool_metadata_verified(path, metadata)
                except Exception:
                    pass
            inops[path.stem] = (
                path, metadata["description"], metadata["parameters"],
                metadata.get("required", metadata["parameters"]),
            )
        except Exception as error:
            errors.append(f"[TOOL ERROR in {path}: {type(error).__name__}: {error}. Repair {path} if needed.]")
    return inops, max(0, len(ordered) - (MAX_TOOLS - 1)), "\n".join(errors)

def native_tools(inops):
    tools = []
    for name, (path, description, parameters, required) in inops.items():
        tools.append({"type": "function", "function": {"name": name, "description": description, "parameters": {"type": "object", "properties": { parameter: { "type": "string" } for parameter in parameters }, "required": list(required), "additionalProperties": False}}})
        if name == "read_tool_result":
            # PORT: Reading needs an explicit selector; neither lookup is inferred.
            tools[-1]["function"]["parameters"]["anyOf"] = [
                {"required": [selector], "properties": {selector: {"minLength": 1}}}
                for selector in ("result_id", "tool_call_id")
            ]
    return tools


def ensure_observation_reader(request_tools, inops):
    """PORT: Preserve the host reader through old-generation tool filters."""
    others = [tool for tool in request_tools
              if tool.get("function", {}).get("name") != "read_tool_result"]
    return others + native_tools({"read_tool_result": inops["read_tool_result"]})


def retain_assistant_for_request(message, index):
    """PORT: Capture ordinary text only; never rewrite reasoning or experience."""
    text = message["content"]
    return retained_text.capture_assistant_message(
        ITER_ROOT, text, message_id="am-" + hashlib.sha256(text.encode("utf-8")).hexdigest(),
        generation_id=ACTIVE_COMPONENT_SNAPSHOT["generation_id"],
    )


def retain_completed_exchange_for_request(messages):
    return retained_text.capture_completed_exchange(
        ITER_ROOT, messages, generation_id=ACTIVE_COMPONENT_SNAPSHOT["generation_id"],
    )


def undelivered_retry_content(content):
    """PORT: Do not duplicate an oversized non-tool response into a directive."""
    if isinstance(content, str) and len(content) > retained_text.WIRE_CHARS:
        return retain_assistant_for_request({"content": content}, -1)
    return content

def load_transformation_descriptions():
    entries = []
    for path in _component_paths("transformations"):
        # PROMOTED (see tools/_metadata_static.py): if this exact file
        # content (path, mtime) was already verified == a real subprocess
        # result in a prior cycle, skip the subprocess and use the trusted
        # static result. Any failure here just means "not trusted" -- falls
        # back to today's exact real subprocess call below, unchanged.
        try:
            from tools._metadata_static import get_trusted_description
            trusted_description = get_trusted_description(path)
        except Exception:
            trusted_description = None
        if trusted_description is not None:
            entries.append(f"{path.stem}: {trusted_description}")
            continue
        result = invoke_dynamic(path, "__description__")
        if result["ok"]:
            entries.append(f"{path.stem}: {result['result']}")
            try:
                from tools._metadata_static import record_description_verified
                record_description_verified(path, result["result"])
            except Exception:
                pass
        else:
            entries.append(f"{path.stem}: [DESCRIPTION MISSING]")
    return "\n".join(entries)

TRANSFORMATION_HEALTH_FAILURE = False


def apply_transformation(messages, tools, timings=None):
    global TRANSFORMATION_HEALTH_FAILURE
    TRANSFORMATION_HEALTH_FAILURE = False
    errors = []
    paths = _component_paths("transformations")
    for path in paths:
        started = time.monotonic()
        try:
            result = invoke_dynamic(path, "transform", messages, tools)
            if not result["ok"]:
                raise RuntimeError(result["error"])
            messages, tools = result["result"]
        except Exception as error:
            errors.append(f"[RUNTIME ERROR in {path}: {type(error).__name__}: {error}. Repair {path} if needed.]")
            # An unchanged transformation's timeout remains visible for repair,
            # but is not evidence that an unrelated new component broke. Real
            # exceptions and timeouts in changed transformations still fail probation.
            relative = "transformations/" + path.name
            changed = (ACTIVE_COMPONENT_SNAPSHOT or {}).get("changed_paths", [])
            if "TIMEOUT after " not in str(error) or relative in changed:
                TRANSFORMATION_HEALTH_FAILURE = True
        finally:
            if timings is not None:
                timings[path.name] = round(time.monotonic() - started, 4)
    return messages, tools, "\n".join(errors)

# --------------------------------------------------------------------
# 4. Main loop
# --------------------------------------------------------------------
try:
    with open("experience.json", "r", encoding="utf-8") as file:
        experience = json.load(file)
except FileNotFoundError:
    experience = []
try:
    retained_text.archive_cached_outputs(ITER_ROOT)
except Exception as error:
    print("[continuity] existing captures retained in place; archive unavailable: " + str(error))
SESSION_ID = str(uuid.uuid4())
HOTLOAD_MANAGER = HotloadManager(ITER_ROOT)
HEARTBEAT = IterHeartbeat(ITER_ROOT, SESSION_ID)
try:
    startup_heartbeat = json.loads((ITER_ROOT / ".runtime/recovery/iter_heartbeat.json").read_text())
except (OSError, ValueError):
    startup_heartbeat = {}
request_failure_notice = (str(startup_heartbeat.get("detail", ""))[:800]
                          if isinstance(startup_heartbeat, dict)
                          and startup_heartbeat.get("phase") == "request_blocked" else "")
REQUEST_EXTRA_BODY = {} if PROVIDER == "openai" else model_request_extra_body(BASE_URL, ITER_ROOT / ".runtime" / "settings.json")
client = openai.OpenAI(api_key=API_KEY, base_url=BASE_URL, timeout=LLM_TIMEOUT, max_retries=0, default_headers={"X-APC-Tenant": "iter", "x-session-id": SESSION_ID})
time.sleep(INIT_WAIT)
Path("memory").mkdir(exist_ok=True)
Path("transformations").mkdir(exist_ok=True)
post_task_mode, autonomous_steps, new_burst, pending_event_append = False, 0, True, ""
silent_streak = 0  # work cycles without send(); deliberate nop-only waiting is not silent work
HARD_SEND_STREAK = 3  # retain prompt check-ins during actual work, not repeated idle pings
cycle_number = 0
while True:
    # PORT: Preserve unfinished work across rollover/restart. Completed earlier
    # task history goes to the existing exact archive before leaving the tail.
    # Token limits apply later to a request COPY, never to stored observations.
    try:
        experience = rotate_experience(
            experience, MAX_EXPERIENCE_SIZE, RETAIN_EXPERIENCE_SIZE,
            archive=lambda messages: archive_text(
                "experience.json", json.dumps(messages, ensure_ascii=False)),
        )
    except Exception as error:
        print("[continuity] history retained; archive unavailable: " + str(error))
    history_checkpoint = len(experience) #before user input
    try:
        # One immutable component generation is pinned for this entire cycle,
        # including retries and every tool dispatch.  A newly activated
        # generation becomes visible only at the next cycle boundary.
        cycle_number += 1
        ACTIVE_COMPONENT_SNAPSHOT = HOTLOAD_MANAGER.component_snapshot()
        cycle_hard_floor_ok = True
        cycle_health_details = []
        if cycle_number == 1 and resume_event_wait(experience, startup_heartbeat, ACTIVE_COMPONENT_SNAPSHOT):
            print("[continuity] restoring saved event wait; no model request needed")
            pending_event_append = slow_wait_for_input(0)
        HEARTBEAT.write(
            ACTIVE_COMPONENT_SNAPSHOT["generation_id"], "cycle_start",
            cycle_number,
        )
        time.sleep(DEFAULT_DELAY)
        print("BEFORE RECEIVE")
        event_append = pending_event_append or receive()
        HEARTBEAT.write(
            ACTIVE_COMPONENT_SNAPSHOT["generation_id"], "input_received",
            cycle_number,
        )
        print("AFTER RECEIVE")
        if event_append:
            autonomous_steps, new_burst, post_task_mode = 0, False, False
            print("IN FROM CHANNEL " + event_append)
            experience += [{"role": "user", "content": "Step " + get_current_time() + ": " + event_append}]
            save_experience(experience)
            pending_event_append = ""
            base_temporary_message = []
        elif new_burst:
            post_task_mode, new_burst = True, False
            # PORT: A restart or nop is not evidence that the user's task ended.
            # Resume from existing experience; preserve autonomous work when idle.
            base_temporary_message = [{"role": "user", "content": "Step " + get_current_time() + ": [NO NEW USER INPUT. A restart or idle wait does not mark the current task complete. Resume unfinished user work from the actual request and saved context. If the user asked you to wait, keep waiting. Only when no user work remains may you choose autonomous work within standing instructions. Do not repeat an already delivered reply.]"}]
        elif post_task_mode:
            base_temporary_message = [{"role": "user", "content": "Step " + get_current_time() + ": [NO NEW USER INPUT. Continue unfinished user work; honor requests to wait. When no user work remains, autonomous work within standing instructions is available. Do not repeat the previous response; use send for new information or needed user input.]"}]
        else:
            base_temporary_message = [{"role": "user", "content": "Step " + get_current_time() + ": [NO ADDITIONAL USER INPUT. CONTINUE THE CURRENT USER TASK.]"}]
        if silent_streak >= HARD_SEND_STREAK:
            base_temporary_message = [{"role": "user", "content": (
                "Step " + get_current_time() + ": [URGENT — THIS OVERRIDES EVERYTHING ELSE THIS TURN: "
                "you have gone " + str(silent_streak) + " work cycles in a row without calling send. The user "
                "has received ZERO replies this whole time and has no visibility into any of your other tool "
                "calls — to them this looks exactly like you are frozen or broken. Your ONLY tool call this turn "
                "MUST be send, with a short, honest status update (what you're doing, what's blocking you, what's "
                "next). Do this before touching anything else, even mid-repair — you can resume repair work "
                "immediately after.]"
            )}] + base_temporary_message
        history_checkpoint = len(experience) #as we want not to loose user input even when exception
        retry_message = None
        while True:
            preparation_started = time.monotonic()
            preparation = {}
            temporary_message = list(base_temporary_message)
            if retry_message:
                temporary_message += retry_message
            INOPS, omitted_tools, tool_load_error = load_tools()
            if tool_load_error:
                temporary_message += [{"role": "user", "content": tool_load_error}]
                cycle_hard_floor_ok = False
                cycle_health_details.append("component load error: " + tool_load_error[:500])
            if omitted_tools > 0:
                temporary_message += [{"role": "user", "content": f"[TOOL LIMIT REACHED: {omitted_tools} tools are currently omitted. Consolidate or remove tools if they are needed.]"}]
            TOOLS = native_tools(INOPS)
            TRANSFORMATIONS = load_transformation_descriptions()
            HEARTBEAT.write(
                ACTIVE_COMPONENT_SNAPSHOT["generation_id"], "components_loaded",
                cycle_number,
                hard_floor_ok=cycle_hard_floor_ok,
                detail="; ".join(cycle_health_details),
            )
            preparation["components_seconds"] = round(time.monotonic() - preparation_started, 4)
            stage_started = time.monotonic()
            # Prompt-projection vs on-disk storage split (Headlong-inspired fix):
            # recap/, tiers/, and the append-only journal/log files already have
            # their own bounded, budget-fitted injections (transformations/recap.py,
            # transformations/tiered_memory.py). Including their raw file bytes here
            # too would double-count them AND is exactly what previously produced a
            # "FIX THIS FIRST" demand that pressured destructive hand-edits of those
            # same append-only files. They are excluded from this raw dump on purpose
            # -- excluding them from the PROMPT here never touches them on disk.
            # The exclusion sets now live in tools/_memory_projection.py (EXCLUDE_DIRS /
            # EXCLUDE_NAMES) -- edit them THERE. Same semantics as before plus the
            # on-disk storage that had been silently blowing the budget every cycle
            # (story_journal/ web app, backups/, verification/, probe_log.json, ...).
            memory_paths = [Path(p) for p in _memory_projection.projection_files("memory")]
            memory_contents = [(path, path.read_text(encoding="utf-8", errors="replace").strip()) for path in memory_paths]
            memory_contents = relevant_memory(memory_contents, experience)
            MEMORY = memory_context(memory_contents, MAX_MEMORY_CHARS)
            request_messages = [{"role": "system", "content": "prompt.txt:\n" + open("prompt.txt", encoding="utf-8", errors="replace").read().strip() + "\n\n./transformations/:\n" + TRANSFORMATIONS + "\n\n" + MEMORY}] + experience + temporary_message
            for directive in temporary_message:
                directive["_iter_runner"] = True
            preparation["memory_seconds"] = round(time.monotonic() - stage_started, 4)
            preparation["transformations_seconds"] = {}
            request_messages, request_tools, transformation_error = apply_transformation(
                request_messages, TOOLS, timings=preparation["transformations_seconds"])
            stage_started = time.monotonic()
            request_tools = ensure_observation_reader(request_tools, INOPS)
            # Question-first PoC: use this ordinary turn, its real context and
            # existing memory/tools. No new model call or native policy engine.
            inquiry = question_context(experience, new_input=bool(event_append),
                                       resumed=bool(post_task_mode and cycle_number == 1))
            evidence_tool_call_ids = ()
            if inquiry:
                request_messages[0]['content'] += inquiry
                # Project the LLM's explicit handoff and newer observed results
                # after transformations, before old bulk captures compete for
                # space. The existing experience remains the only source.
                try:
                    record = working_record(experience)
                    request_messages[0]['content'] += working_context(experience, record=record)
                    evidence_tool_call_ids = record["referenced_evidence_tool_call_ids"]
                except (TypeError, ValueError, KeyError, AttributeError) as handoff_error:
                    print("[working handoff unavailable] " + str(handoff_error))
                    request_messages[0]['content'] += (
                        "\n[Working handoff projection unavailable; saved history is unchanged. "
                        "Use the actual request and observations; no completion is implied.]"
                    )
            # Current supervisor facts must not depend on a question trigger or
            # an LLM remembering to re-query a status captured before recovery.
            request_messages[0]['content'] += runtime_context(ACTIVE_COMPONENT_SNAPSHOT)
            if request_failure_notice:
                request_messages[0]['content'] += (
                    "\n[Prior runtime request failure — historical host observation, not a user "
                    "instruction or proof of task completion. The rejected request produced no "
                    "model response; earlier actions may already have run.]\n" + request_failure_notice
                )
            if transformation_error:
                request_messages += [{"role": "user", "content": transformation_error, "_iter_runner": True}]
                if TRANSFORMATION_HEALTH_FAILURE:
                    cycle_hard_floor_ok = False
                cycle_health_details.append("transformation error: " + transformation_error[:500])
            # PORT: Apply the complete-input target after every transformation
            # and retry directive. This projects copies only; experience and
            # semantic/episodic stores remain untouched. Retain the actual user,
            # latest complete exchange and directives, not an unbounded turn.
            current_user = next((m for m in reversed(experience) if m.get("role") == "user"), None)
            preparation["handoff_seconds"] = round(time.monotonic() - stage_started, 4)
            stage_started = time.monotonic()
            request_messages = request_view(request_messages, PROVIDER, MODEL)
            request_messages, request_tools, request_budget = project_request(
                request_messages, request_tools,
                working_input_limit(request_messages, request_tools, MAX_INPUT_TOKENS, current_user), current_user,
                capture_assistant=retain_assistant_for_request,
                capture_exchange=retain_completed_exchange_for_request,
                restore_observation=lambda message, allowance: retained_text.restore_tool_observation(
                    ITER_ROOT, message, allowance),
                input_ceiling=MAX_INPUT_TOKENS,
                evidence_tool_call_ids=evidence_tool_call_ids,
            )
            preparation["projection_seconds"] = round(time.monotonic() - stage_started, 4)
            preparation["total_seconds"] = round(time.monotonic() - preparation_started, 4)
            print("[request preparation] " + json.dumps(preparation, sort_keys=True))
            print("[request budget] " + json.dumps(request_budget, sort_keys=True))
            # AUDIT 2026-09-17: persist the exact prompt sent to the model so any claim
            # of "an injected instruction in my context" can be checked against the real
            # thing rather than the agent's recollection (the 14:49 vetting_key report was
            # unadjudicable without this). .runtime/ is runtime scratch, NOT memory/, so
            # it is never projected back into the prompt. Previous cycle kept as .prev.
            try:
                _rt = Path(".runtime")
                _rt.mkdir(exist_ok=True)
                _cur, _prev = _rt / "last_prompt.json", _rt / "last_prompt.prev.json"
                if _cur.exists():
                    _cur.replace(_prev)
                _cur.write_text(json.dumps({
                    "ts": datetime.datetime.now().isoformat(timespec="seconds"),
                    "model": MODEL,
                    "provider": PROVIDER,
                    "reasoning_effort": REASONING_EFFORT if PROVIDER == "openai" else None,
                    "request_budget": request_budget,
                    "preparation": preparation,
                    "max_output_tokens": MAX_TOKENS,
                    "tool_names": [t.get("function", {}).get("name") for t in (request_tools or []) if isinstance(t, dict)],
                    "messages": request_messages,
                    "api_request": request_kwargs(PROVIDER, MODEL, request_messages, request_tools,
                                                  MAX_TOKENS, REASONING_EFFORT, REQUEST_EXTRA_BODY)
                                   if PROVIDER == "openai" else None,
                }, ensure_ascii=False, default=str), encoding="utf-8")
            except Exception as _dump_err:
                print(f"[last_prompt dump skipped: {_dump_err}]")
            print("BEFORE LLM")
            HEARTBEAT.write(
                ACTIVE_COMPONENT_SNAPSHOT["generation_id"], "model_wait",
                cycle_number,
                hard_floor_ok=cycle_hard_floor_ok,
                detail="; ".join(cycle_health_details),
            )
            response = call_model(client, PROVIDER, MODEL, request_messages, request_tools, MAX_TOKENS,
                                  effort=REASONING_EFFORT, extra_body=REQUEST_EXTRA_BODY,
                                  usage_path=ITER_ROOT / ".runtime" / "last_model_usage.json")
            request_failure_notice = ""  # Delivered in this actual request, not every future turn.
            print("AFTER LLM", {"model": MODEL, "usage": response.usage} if PROVIDER == "openai" else response)
            HEARTBEAT.write(
                ACTIVE_COMPONENT_SNAPSHOT["generation_id"], "model_returned",
                cycle_number,
                hard_floor_ok=cycle_hard_floor_ok,
                detail="; ".join(cycle_health_details),
            )
            message = response.choices[0].message
            if message.content:
                message.content += "\n[NOT DELIVERED TO ANY CHANNEL. IF THIS WAS INTENDED AS COMMUNICATION, USE send.]"
            if message.tool_calls:
                message.tool_calls = message.tool_calls[:MAX_TOOL_CALLS]
                break
            retry_content = undelivered_retry_content(message.content)
            try:
                if response.choices[0].finish_reason == "length":
                    retry_message = [{"role": "user", "content": "[OUTPUT TOKEN LIMIT REACHED. CALL THE REQUIRED TOOL CONCISELY.]"}]
                else:
                    retry_message = [{"role": "user", "content": f"[YOUR PREVIOUS RESPONSE CONTAINED NO TOOL CALL AND WAS NOT DELIVERED. CALL AT LEAST ONE TOOL NOW. IF YOU INTENDED THIS CONTENT AS COMMUNICATION, USE send: {retry_content!r}]"}]
            except:
                retry_message = [{"role": "user", "content": f"[YOUR PREVIOUS RESPONSE CONTAINED NO TOOL CALL AND WAS NOT DELIVERED. CALL AT LEAST ONE TOOL NOW. IF YOU INTENDED THIS CONTENT AS COMMUNICATION, USE send: {retry_content!r}]"}]
        print(f"RESPONSE {MODEL if PROVIDER == 'openai' else response}\nFINISH_REASON {response.choices[0].finish_reason}\nUSAGE {response.usage}")
        called_tools = {call.function.name for call in message.tool_calls}
        if "send" in called_tools:
            silent_streak = 0
        elif called_tools - {"nop"}:
            silent_streak += 1
        experience += [{key: value for key, value in message.model_dump(exclude_none=True).items() if KEEP_REASONING_IN_EPISODE or key not in ("reasoning", "reasoning_details", "reasoning_content")}]
        tool_outputs = []
        nop_already_run = False  # NOP DEDUPE (2026-09-13): the model has been observed stacking several
        # redundant nop calls within a single turn (up to 7 of the 10 slots) instead of nop.py's intended
        # single idle signal. Each one still paid for a real subprocess spawn via invoke_dynamic for zero
        # additional effect, adding real wall-clock latency to already-silent turns. Only the first nop per
        # turn actually dispatches below; later ones short-circuit without spawning a process.
        for tool_call in message.tool_calls:
            tool_name = tool_call.function.name
            tool_started = time.monotonic()
            gate_seconds = None
            # PORT: Keep each call's advisory separate from its original JSON body.
            raw_tool_result = None
            gate_note = ""
            execution = {"success": None, "state": "not_executed", "scope": "invocation",
                         "task_fulfillment": "unverified"}
            if tool_name == "nop" and nop_already_run:
                tool_arguments = {}
                ret = "SUCCESS (deduped: nop already ran once this turn, redundant call skipped)"
            else:
                try:
                    tool_arguments = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError as error:
                    tool_arguments = tool_call.function.arguments
                    ret = f"Invalid tool arguments from model: {error}"
                else:
                    try: #unless tool unknown/args formatting issue, we use the tool's INOPS function return value:
                        if tool_name not in INOPS:
                            ret = f"Unknown tool: {tool_name!r}"
                        elif not isinstance(tool_arguments, dict):
                            ret = "Tool arguments must be a JSON object"
                        else:
                            # Phase 3 reasoning-substrate gate: fails open on any
                            # error/timeout/no-data (see tools/_metta_gate.py's own
                            # docstring) -- never able to stall dispatch on its own.
                            gate_note = ""
                            gate_started = time.monotonic()
                            try:
                                gate_call = invoke_dynamic(
                                    _component_file("tools/_metta_gate.py"), "run",
                                    tool_name, tool_arguments,
                                    {
                                        "cycle": cycle_number,
                                        "generation_id": ACTIVE_COMPONENT_SNAPSHOT.get("generation_id"),
                                    },
                                )
                                if gate_call.get("ok"):
                                    gate_mode, gate_action, gate_detail = gate_call["result"].split("|", 2)
                                    # gate_detail otherwise only reaches the LLM when action==ADVISE
                                    # (below); a circuit-breaker-open or substrate-unavailable ALLOW
                                    # would silently vanish here without this -- see _log_gate_issue.
                                    if "circuit breaker open" in gate_detail or "substrate unavailable" in gate_detail:
                                        _log_gate_issue(tool_name, gate_detail)
                                else:
                                    gate_mode, gate_action, gate_detail = "advisory", "ALLOW", ""
                                    _log_gate_issue(tool_name, "gate call failed: " + str(gate_call.get("error", "")))
                            except Exception as gate_error:
                                gate_mode, gate_action, gate_detail = "advisory", "ALLOW", ""
                                _log_gate_issue(tool_name, "gate dispatch exception: %s: %s" % (type(gate_error).__name__, gate_error))
                            gate_seconds = round(time.monotonic() - gate_started, 4)
                            if gate_action == "VETO":
                                ret = f"Tool execution blocked by reasoning substrate ({gate_mode} mode): {gate_detail}"
                            else:
                                if gate_action == "ADVISE":
                                    gate_note = f"[NACE advisory: {gate_detail}] "
                                result = invoke_dynamic(INOPS[tool_name][0], "run", **tool_arguments)
                                execution = result.get("execution") or {
                                    "success": bool(result["ok"]),
                                    "state": "returned" if result["ok"] else "failed",
                                    "scope": "invocation", "task_fulfillment": "unverified",
                                }
                                if (
                                    not result["ok"]
                                    and not result.get("input_rejected", False)
                                    and ACTIVE_COMPONENT_SNAPSHOT.get("status") == "probation"
                                ):
                                    try:
                                        relative_tool = INOPS[tool_name][0].relative_to(
                                            ACTIVE_COMPONENT_SNAPSHOT["roots"]["tools"].parent
                                        ).as_posix()
                                    except Exception:
                                        relative_tool = ""
                                    if relative_tool in ACTIVE_COMPONENT_SNAPSHOT.get("changed_paths", []):
                                        cycle_hard_floor_ok = False
                                        cycle_health_details.append(
                                            "changed tool failed: %s: %s" % (
                                                tool_name, str(result.get("error", ""))[:300]
                                            )
                                        )
                                raw_tool_result = str(result["result"]) if result["ok"] else (
                                    ("Tool input rejected: " if result.get("input_rejected") else
                                     "Tool execution failed: ") + result['error']
                                )
                                ret = gate_note + raw_tool_result
                    except Exception as error:
                        ret = f"Tool execution failed: {type(error).__name__}: {error}"
                if tool_name == "nop":
                    nop_already_run = True
            ret = str(ret)
            elapsed = round(time.monotonic() - tool_started, 4)
            print("[tool timing] " + json.dumps({"tool": tool_name,
                "call_id": tool_call.id, "total_seconds": elapsed,
                "nace_dispatch_seconds": gate_seconds,
                "state": execution.get("state")}, sort_keys=True))
            # PORT: This is captured output, never cached execution/authorization.
            # The bounded reader only reads these bytes; it cannot replay a tool.
            ret = capture_tool_output(
                ITER_ROOT, ret, tool_call_id=tool_call.id, tool_name=tool_name,
                generation_id=ACTIVE_COMPONENT_SNAPSHOT["generation_id"],
                raw_result=raw_tool_result, advisory=gate_note, execution=execution,
                max_chars=MAX_TOOL_OUTPUT_CHARS - 500,
            )
            experience += [{"role": "tool", "tool_call_id": tool_call.id,
                            "content": "Step " + get_current_time() + ": " + ret,
                            "_iter_execution": execution}]
            tool_outputs += ["tool call: " + tool_name + " " + str(tool_arguments) + "\n" "tool return: " + ret]
            HEARTBEAT.write(
                ACTIVE_COMPONENT_SNAPSHOT["generation_id"], "tool_progress",
                cycle_number,
                hard_floor_ok=cycle_hard_floor_ok,
                detail=("%s; %s" % (tool_name, "; ".join(cycle_health_details)))[:1000],
            )
        history_checkpoint = len(experience) #tool calls succeeded, even on later exception we won't unroll them
        save_experience(experience)
        print("Output> " + "\n".join(tool_outputs))
        autonomous_steps = 0 if event_append else autonomous_steps + 1
        HEARTBEAT.write(
            ACTIVE_COMPONENT_SNAPSHOT["generation_id"], "cycle_complete",
            cycle_number,
            hard_floor_ok=cycle_hard_floor_ok,
            detail="; ".join(cycle_health_details),
        )
        if not cycle_hard_floor_ok and ACTIVE_COMPONENT_SNAPSHOT.get("status") == "probation":
            # Do not let the next cycle overwrite a failed probation heartbeat
            # before the external supervisor observes it. If Electron itself is
            # unavailable, this safely holds until restart, where startup recovery
            # restores the parent before Iter can run again.
            print("[hot-load] probation hard floor failed; waiting for external rollback")
            while True:
                time.sleep(1)
                recovered_snapshot = HOTLOAD_MANAGER.component_snapshot()
                if recovered_snapshot["generation_id"] != ACTIVE_COMPONENT_SNAPSHOT["generation_id"]:
                    break
        called_nop = any(call.function.name == "nop" for call in message.tool_calls)
        if called_nop:
            new_burst, autonomous_steps = True, 0
            wait_call = next(call for call in message.tool_calls if call.function.name == "nop")
            try:
                wait_seconds = float(json.loads(wait_call.function.arguments).get("wait_seconds", 0))
                if not 0 <= wait_seconds <= 86400:
                    wait_seconds = SLOW_STEP_DELAY
            except (ValueError, TypeError, AttributeError):
                wait_seconds = SLOW_STEP_DELAY
            pending_event_append = slow_wait_for_input(wait_seconds)
        elif autonomous_steps >= MAX_FAST_STEPS:
            autonomous_steps = 0
            pending_event_append = slow_wait_for_input()
    except RequestBudgetExceeded as error:
        # A deterministic input failure is not a transient provider outage or
        # evidence that a managed tool broke. Do not replay actions, truncate
        # experience, roll back a healthy generation, or retry unchanged input.
        # Keep existing input/revision wakeups and the supervisor heartbeat.
        pending_event_append = wait_for_request_change(error)
    except Exception as error:
        if is_rejected_model_request(error):
            pending_event_append = wait_for_request_change(error)
            continue
        print(f"Output> {type(error).__name__}: {error}")
        try:
            provider_retry = is_transient_provider_error(error)
            generation_id = (
                ACTIVE_COMPONENT_SNAPSHOT["generation_id"]
                if ACTIVE_COMPONENT_SNAPSHOT else "unavailable"
            )
            HEARTBEAT.write(
                generation_id, "provider_retry" if provider_retry else "error", cycle_number,
                hard_floor_ok=cycle_hard_floor_ok if provider_retry else False,
                detail="%s: %s" % (type(error).__name__, error),
            )
        except Exception as heartbeat_error:
            print(f"[heartbeat error: {heartbeat_error}]")
        experience = experience[:history_checkpoint]
        time.sleep(ERROR_RECOVERY_TIME)
