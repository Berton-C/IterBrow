import datetime
import inspect
import json
import os
import sys
import openai
import time
import importlib.util
import signal
import subprocess
import tempfile
import uuid
from pathlib import Path

# Shared rule for "which memory/ files are prompt memory" (tools/_memory_projection.py).
# iter.py is the authority on the projection; self_improve.py and auto_improve.py
# measure the same set through this module so the three can never drift apart
# again (2026-09-17: they had, pinning memory_efficiency at 0 and pain at ~20,000).
_TOOLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)
import _memory_projection

# --------------------------------------------------------------------
# 0. Configuration:
# --------------------------------------------------------------------
MAX_MEMORY_CHARS = 20000 #When memory turns into an index (raised from 3000: that cap was tuned for the old browser/WASM build and was tripping constantly on real desktop usage, flooding the agent with "FIX THIS FIRST" directives that starved out chat replies)
LLM_TIMEOUT = 600
KEEP_REASONING_IN_EPISODE = True
PRINT_CALLS = False
MAX_TOOL_CALLS = 10
MAX_TOOL_OUTPUT_CHARS = 5000
MAX_EXPERIENCE_SIZE = 100   #20 percent
RETAIN_EXPERIENCE_SIZE = 80 #jumps
MAX_FAST_STEPS = 50
SLOW_STEP_DELAY = 10
ERROR_RECOVERY_TIME = 1 #after how long to retry when exception occurs
RETURN_VALUE_PRESERVE = 0
RETURN_VALUE_PRESERVE_MESSAGES = 10
DEFAULT_DELAY = 0 #default delay added irregard of whether in slow mode
MAX_TOKENS = 2524
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
METTA_GATE_PATH = Path("tools/_metta_gate.py")  # Phase 3 reasoning-substrate dispatch gate; see tools/_metta_gate.py
GATE_LOG_PATH = Path("transformations/.runtime/gate_health.log")  # trail for gate ALLOW-via-fail-open/crash cases, which iter.py's dispatch loop otherwise never surfaces (see _log_gate_issue)
MODEL = os.getenv("LLM_MODEL", "mlx-community/gemma-4-26b-a4b-it-4bit")
BASE_URL = os.getenv("BASE_URL", "http://192.168.64.1:2277/v1")
API_KEY = os.getenv("AI_API_KEY", "dummy")

# --------------------------------------------------------------------
# 1. Dynamic execution:
# --------------------------------------------------------------------
def dynamic_worker():
    path = Path(sys.argv[2])
    function = sys.argv[3]
    result_path = Path(sys.argv[4])
    payload_path = Path(sys.argv[5])
    try:
        payload = json.loads(payload_path.read_text())
        spec = importlib.util.spec_from_file_location("_dynamic_" + path.stem, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if function == "__description__":
            result = str(module.DESCRIPTION)
        elif function == "__tool_metadata__":
            parameters = inspect.signature(module.run).parameters.values()
            description = str(module.DESCRIPTION)
            if len(description) > MAX_TOOL_DESCRIPTION_CHARS:
                description = description[:MAX_TOOL_DESCRIPTION_CHARS] + " [DESCRIPTION TRUNCATED]"
            result = {"description": description, "parameters": [parameter.name for parameter in parameters]}
        else:
            result = getattr(module, function)(*payload.get("args", []), **payload.get("kwargs", {}))
            if function != "transform" and result is not None:
                result = str(result)
        output = {"ok": True, "result": result}
    except BaseException as error:
        output = {"ok": False, "error": f"{type(error).__name__}: {error}"}
    try:
        result_path.write_text(json.dumps(output, ensure_ascii=False))
    except BaseException as error:
        result_path.write_text(json.dumps({"ok": False, "error": f"Result serialization failed: {type(error).__name__}: {error}"}, ensure_ascii=False))

def invoke_dynamic(path, function, *args, **kwargs):
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
        try:
            process.wait(timeout=DYNAMIC_TIMEOUT)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            return {"ok": False, "error": f"TIMEOUT after {DYNAMIC_TIMEOUT}s"}
        try:
            return json.loads(Path(result_file).read_text())
        except Exception:
            return {"ok": False, "error": f"Dynamic process exited with code {process.returncode} without a valid result"}
    finally:
        for file in (result_file, payload_file):
            try:
                os.unlink(file)
            except FileNotFoundError:
                pass

if len(sys.argv) > 1 and sys.argv[1] == "--invoke":
    dynamic_worker()
    sys.exit(0)

# --------------------------------------------------------------------
# 2. Runtime helpers:
# --------------------------------------------------------------------
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

def receive():
    events = []
    paths = [path for path in sorted(Path("channels").glob("*.py")) if not path.name.startswith("_")]
    for path in paths:
        try:
            result = invoke_dynamic(path, "receive")
            if not result["ok"]:
                raise RuntimeError(result["error"])
            event = result["result"]
            if event:
                events.append("[" + path.stem + "] " + str(event))
        except Exception as error:
            events.append(f"[CHANNEL ERROR in {path}: {type(error).__name__}: {error}. Repair {path} if needed.]")
    return "\n".join(events)

def slow_wait_for_input():
    for second in range(SLOW_STEP_DELAY):
        time.sleep(1)
        event_append = receive()
        if event_append:
            return event_append
    return ""

def save_experience(experience):
    with open("experience.tmp", "w", encoding="utf-8") as file:
        json.dump(experience, file, ensure_ascii=False, indent=2)
    os.replace("experience.tmp", "experience.json")

# --------------------------------------------------------------------
# 3. Dynamic components:
# --------------------------------------------------------------------
# Tools that must NEVER be silently dropped by the MAX_TOOLS cap, regardless of
# alphabetical sort position or how large tools/ grows. `send` is the model's only
# way to talk to the user - if it's ever excluded again, the model can go silent
# indefinitely even though the silent_streak safety net keeps demanding it call
# send (that exact incident is why this list exists; see MAX_TOOLS comment above).
PROTECTED_TOOL_NAMES = {"send", "nop", "shell", "python", "start_new_task"}

def load_tools():
    inops = {}
    errors = []
    paths = [path for path in sorted(Path("tools").glob("*.py")) if not path.name.startswith("_")]
    # Protected tools always go first so truncation (if the directory ever grows
    # past MAX_TOOLS again) can only ever drop non-essential tools.
    protected = [path for path in paths if path.stem in PROTECTED_TOOL_NAMES]
    rest = [path for path in paths if path.stem not in PROTECTED_TOOL_NAMES]
    ordered = protected + rest
    for path in ordered[:MAX_TOOLS]:
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
            inops[path.stem] = (path, metadata["description"], metadata["parameters"])
        except Exception as error:
            errors.append(f"[TOOL ERROR in {path}: {type(error).__name__}: {error}. Repair {path} if needed.]")
    return inops, len(ordered) - MAX_TOOLS, "\n".join(errors)

def native_tools(inops):
    tools = []
    for name, (path, description, parameters) in inops.items():
        tools.append({"type": "function", "function": {"name": name, "description": description, "parameters": {"type": "object", "properties": { parameter: { "type": "string" } for parameter in parameters }, "required": [parameter for parameter in parameters], "additionalProperties": False}}})
    return tools

def load_transformation_descriptions():
    entries = []
    for path in sorted(Path("transformations").glob("*.py")):
        if path.name.startswith("_"):
            continue
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

def apply_transformation(messages, tools):
    errors = []
    paths = sorted(path for path in Path("transformations").glob("*.py") if not path.name.startswith("_"))
    for path in paths:
        try:
            result = invoke_dynamic(path, "transform", messages, tools)
            if not result["ok"]:
                raise RuntimeError(result["error"])
            messages, tools = result["result"]
        except Exception as error:
            errors.append(f"[RUNTIME ERROR in {path}: {type(error).__name__}: {error}. Repair {path} if needed.]")
    return messages, tools, "\n".join(errors)

# --------------------------------------------------------------------
# 4. Main loop
# --------------------------------------------------------------------
try:
    with open("experience.json", "r", encoding="utf-8") as file:
        experience = json.load(file)
except FileNotFoundError:
    experience = []
SESSION_ID = str(uuid.uuid4())
client = openai.OpenAI(api_key=API_KEY, base_url=BASE_URL, timeout=LLM_TIMEOUT, max_retries=0, default_headers={"X-APC-Tenant": "iter", "x-session-id": SESSION_ID})
time.sleep(INIT_WAIT)
Path("memory").mkdir(exist_ok=True)
Path("transformations").mkdir(exist_ok=True)
post_task_mode, autonomous_steps, new_burst, pending_event_append = False, 0, True, ""
silent_streak = 0  # consecutive cycles in a row with no send() tool call — hard safety net so a self-repair spiral can never leave the user in total silence (see HARD_SEND_STREAK below)
HARD_SEND_STREAK = 3  # lowered from 8 (2026-09-13): each nop-bearing turn also triggers a real 10s slow_wait_for_input() throttle below, and turns can carry up to MAX_TOOL_CALLS tool calls -- 8 silent turns could stretch into minutes of real silence before this fired. 3 still allows a short legitimate bookkeeping burst but forces a check-in much sooner.
cleanup_interval = MAX_EXPERIENCE_SIZE - RETAIN_EXPERIENCE_SIZE
cleanup_bucket = len(experience) // cleanup_interval
while True:
    current_bucket = len(experience) // cleanup_interval
    if current_bucket > cleanup_bucket:
        for i, old_message in enumerate(experience):
            if i < len(experience) - RETURN_VALUE_PRESERVE_MESSAGES:
                if old_message.get("role") == "tool" and len(old_message.get("content", "")) > RETURN_VALUE_PRESERVE:
                    old_message["content"] = old_message.get("content", "")[:RETURN_VALUE_PRESERVE] + " [TRUNCATED]"
                for key in ("reasoning", "reasoning_details", "reasoning_content"):
                    old_message.pop(key, None)
        cleanup_bucket = current_bucket
    if len(experience) >= MAX_EXPERIENCE_SIZE:
        experience = experience[-RETAIN_EXPERIENCE_SIZE:]
        cleanup_bucket = len(experience) // cleanup_interval
    while experience and experience[0].get("role") == "tool":
        experience = experience[1:]
    history_checkpoint = len(experience) #before user input
    try:
        time.sleep(DEFAULT_DELAY)
        print("BEFORE RECEIVE")
        event_append = pending_event_append or receive()
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
            base_temporary_message = [{"role": "user", "content": "Step " + get_current_time() + ": [TASK COMPLETED. DO NOT RE-SEND THE COMPLETED RESPONSE BUT SEND IN CASE YOU FORGOT. NOW QUERY FOR AND PICK A TASK BASED ON YOUR GOALS, PREFERABLY MEMORY CONSOLIDATION: FINDING EPISODES WHICH SUPPORT / CONTRADICT LTM ITEMS, LINKING EPISODES, PROMOTING USEFUL MEMORIES]"}]
        elif post_task_mode:
            base_temporary_message = [{"role": "user", "content": "Step " + get_current_time() + ": [NO NEW USER INPUT. CONTINUE AUTONOMOUS WORK. DO NOT REPEAT THE PREVIOUS RESPONSE. ONLY USE send FOR GENUINELY NEW INFORMATION OR WHEN USER INPUT IS NEEDED.]"}]
        else:
            base_temporary_message = [{"role": "user", "content": "Step " + get_current_time() + ": [NO ADDITIONAL USER INPUT. CONTINUE THE CURRENT USER TASK.]"}]
        if silent_streak >= HARD_SEND_STREAK:
            base_temporary_message = [{"role": "user", "content": (
                "Step " + get_current_time() + ": [URGENT — THIS OVERRIDES EVERYTHING ELSE THIS TURN: "
                "you have gone " + str(silent_streak) + " tool calls in a row without calling send. The user "
                "has received ZERO replies this whole time and has no visibility into any of your other tool "
                "calls — to them this looks exactly like you are frozen or broken. Your ONLY tool call this turn "
                "MUST be send, with a short, honest status update (what you're doing, what's blocking you, what's "
                "next). Do this before touching anything else, even mid-repair — you can resume repair work "
                "immediately after.]"
            )}] + base_temporary_message
        history_checkpoint = len(experience) #as we want not to loose user input even when exception
        retry_message = None
        while True:
            temporary_message = list(base_temporary_message)
            if retry_message:
                temporary_message += retry_message
            INOPS, omitted_tools, tool_load_error = load_tools()
            if tool_load_error:
                temporary_message += [{"role": "user", "content": tool_load_error}]
            if omitted_tools > 0:
                temporary_message += [{"role": "user", "content": f"[TOOL LIMIT REACHED: {omitted_tools} tools are currently omitted. Consolidate or remove tools if they are needed.]"}]
            TOOLS = native_tools(INOPS)
            TRANSFORMATIONS = load_transformation_descriptions()
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
            memory_len = sum(len(content) for _, content in memory_contents)
            if memory_len <= MAX_MEMORY_CHARS:
                MARGIN = MAX_MEMORY_CHARS - memory_len
                MEMORY = f"[{MARGIN} CHARACTERS BELOW MAXIMUM]\n./memory/:\n"
                MEMORY += "\n\n".join(f"{path}:\n{content}" for path, content in memory_contents)
            else:
                # Graceful degrade of the PROMPT PROJECTION ONLY: drop/truncate the
                # smallest-first so the most substantial state files still show up
                # in full where possible; nothing here writes to any file. This
                # deliberately replaces the old "FIX THIS FIRST" imperative (which
                # read as an instruction to go delete/shrink files) with a calm,
                # factual note plus a pointer to the sanctioned regeneration tool.
                DIFF = memory_len - MAX_MEMORY_CHARS
                ordered = sorted(memory_contents, key=lambda pc: len(pc[1]))
                included = []
                used = 0
                for path, content in ordered:
                    if used + len(content) <= MAX_MEMORY_CHARS:
                        included.append((path, content))
                        used += len(content)
                    else:
                        remaining = MAX_MEMORY_CHARS - used
                        if remaining > 200:
                            included.append((path, content[:remaining - 60] + "\n...[truncated for THIS PROMPT ONLY; the file on disk is untouched]"))
                            used = MAX_MEMORY_CHARS
                        break
                MEMORY = (
                    f"[PROMPT PROJECTION TRUNCATED BY {DIFF} CHARS FOR THIS TURN ONLY - nothing on disk was "
                    "changed. If this persists, call rebuild_tiers to compact the episodic pyramid, or archive "
                    "resolved items in memory/tasks/. Do not hand-edit files to shrink them.]\n./memory/:\n"
                )
                MEMORY += "\n\n".join(f"{path}:\n{content}" for path, content in included)
            request_messages = [{"role": "system", "content": "prompt.txt:\n" + open("prompt.txt", encoding="utf-8", errors="replace").read().strip() + "\n\n./transformations/:\n" + TRANSFORMATIONS + "\n\n" + MEMORY}] + experience + temporary_message
            request_messages, request_tools, transformation_error = apply_transformation(request_messages, TOOLS)
            if transformation_error:
                request_messages += [{"role": "user", "content": transformation_error}]
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
                    "tool_names": [t.get("function", {}).get("name") for t in (request_tools or []) if isinstance(t, dict)],
                    "messages": request_messages,
                }, ensure_ascii=False, default=str), encoding="utf-8")
            except Exception as _dump_err:
                print(f"[last_prompt dump skipped: {_dump_err}]")
            print("BEFORE LLM")
            response = client.chat.completions.create(model=MODEL, messages=request_messages, tools=request_tools, tool_choice="required", max_tokens=MAX_TOKENS, extra_body={ "enable_thinking": True})
            print("AFTER LLM", response)
            message = response.choices[0].message
            if message.content:
                message.content += "\n[NOT DELIVERED TO ANY CHANNEL. IF THIS WAS INTENDED AS COMMUNICATION, USE send.]"
            if message.tool_calls:
                message.tool_calls = message.tool_calls[:MAX_TOOL_CALLS]
                break
            try:
                if response.choices[0].finish_reason == "length":
                    retry_message = [{"role": "user", "content": "[OUTPUT TOKEN LIMIT REACHED. CALL THE REQUIRED TOOL CONCISELY.]"}]
                else:
                    retry_message = [{"role": "user", "content": f"[YOUR PREVIOUS RESPONSE CONTAINED NO TOOL CALL AND WAS NOT DELIVERED. CALL AT LEAST ONE TOOL NOW. IF YOU INTENDED THIS CONTENT AS COMMUNICATION, USE send: {message.content!r}]"}]
            except:
                retry_message = [{"role": "user", "content": f"[YOUR PREVIOUS RESPONSE CONTAINED NO TOOL CALL AND WAS NOT DELIVERED. CALL AT LEAST ONE TOOL NOW. IF YOU INTENDED THIS CONTENT AS COMMUNICATION, USE send: {message.content!r}]"}]
        print(f"RESPONSE {response}\nFINISH_REASON {response.choices[0].finish_reason}\nUSAGE {response.usage}")
        silent_streak = 0 if any(call.function.name == "send" for call in message.tool_calls) else silent_streak + 1
        experience += [{key: value for key, value in message.model_dump(exclude_none=True).items() if KEEP_REASONING_IN_EPISODE or key not in ("reasoning", "reasoning_details", "reasoning_content")}]
        tool_outputs = []
        nop_already_run = False  # NOP DEDUPE (2026-09-13): the model has been observed stacking several
        # redundant nop calls within a single turn (up to 7 of the 10 slots) instead of nop.py's intended
        # single idle signal. Each one still paid for a real subprocess spawn via invoke_dynamic for zero
        # additional effect, adding real wall-clock latency to already-silent turns. Only the first nop per
        # turn actually dispatches below; later ones short-circuit without spawning a process.
        for tool_call in message.tool_calls:
            tool_name = tool_call.function.name
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
                            try:
                                gate_call = invoke_dynamic(METTA_GATE_PATH, "run", tool_name)
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
                            if gate_action == "VETO":
                                ret = f"Tool execution blocked by reasoning substrate ({gate_mode} mode): {gate_detail}"
                            else:
                                if gate_action == "ADVISE":
                                    gate_note = f"[NACE advisory: {gate_detail}] "
                                result = invoke_dynamic(INOPS[tool_name][0], "run", **tool_arguments)
                                ret = gate_note + (result["result"] if result["ok"] else f"Tool execution failed: {result['error']}")
                    except Exception as error:
                        ret = f"Tool execution failed: {type(error).__name__}: {error}"
                if tool_name == "nop":
                    nop_already_run = True
            ret = str(ret)
            if len(ret) > MAX_TOOL_OUTPUT_CHARS:
                ret = ret[:MAX_TOOL_OUTPUT_CHARS] + " [TRUNCATED]"
            experience += [{"role": "tool", "tool_call_id": tool_call.id, "content": "Step " + get_current_time() + ": " + ret}]
            tool_outputs += ["tool call: " + tool_name + " " + str(tool_arguments) + "\n" "tool return: " + ret]
        history_checkpoint = len(experience) #tool calls succeeded, even on later exception we won't unroll them
        save_experience(experience)
        print("Output> " + "\n".join(tool_outputs))
        autonomous_steps = 0 if event_append else autonomous_steps + 1
        called_nop = any(call.function.name == "nop" for call in message.tool_calls)
        if called_nop:
            new_burst, autonomous_steps = True, 0
            pending_event_append = slow_wait_for_input()
        elif autonomous_steps >= MAX_FAST_STEPS:
            autonomous_steps = 0
            pending_event_append = slow_wait_for_input()
    except Exception as error:
        print(f"Output> {type(error).__name__}: {error}")
        experience = experience[:history_checkpoint]
        time.sleep(ERROR_RECOVERY_TIME)
