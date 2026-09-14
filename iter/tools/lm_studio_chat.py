import json
import urllib.request
import urllib.error

DESCRIPTION = (
    "Send a chat completion request to LM Studio's local LLM server, as a side call independent of your own "
    "main model (which is configured separately via BASE_URL/LLM_MODEL). "
    "Accepts: messages (list of {role, content} dicts, or a JSON string), model (default 'qwen/qwen3.8-27b'), "
    "temperature (default 0.7), max_tokens (default 1024), stream (default False). "
    "Returns the assistant's response text, or full JSON if raw=True. "
    "LM Studio base URL defaults to http://127.0.0.1:1234 (loopback, works with or without a network) but can "
    "be overridden via base_url."
)

# NOTE: this is the native-Python rewrite of the browser/WASM version of
# this tool (which used `import js` + `js.XMLHttpRequest` and only works
# inside the MicroPython/WASM page). This process is real CPython, so we
# use the standard library's urllib instead. Also switched the default
# host from the LAN IP (172.30.31.48) to 127.0.0.1 — the LAN IP requires
# Wi-Fi/DHCP to exist at all, loopback always works.
DEFAULT_BASE = "http://127.0.0.1:1234"
DEFAULT_MODEL = "qwen/qwen3.8-27b"


def _to_bool(val):
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() in ("true", "1", "yes")
    return bool(val)


def _to_int(val):
    return int(val)


def _to_float(val):
    return float(val)


def run(messages, model=None, temperature=0.7, max_tokens=1024,
        stream=False, raw=False, base_url=None, timeout=120):
    if base_url is None:
        base_url = DEFAULT_BASE
    if model is None:
        model = DEFAULT_MODEL

    if isinstance(messages, str):
        try:
            messages = json.loads(messages)
        except Exception:
            messages = [{"role": "user", "content": messages}]

    stream_b = _to_bool(stream)
    raw_b = _to_bool(raw)

    payload = {
        "model": str(model),
        "messages": messages,
        "temperature": _to_float(temperature),
        "max_tokens": _to_int(max_tokens),
        "stream": stream_b,
    }

    url = str(base_url).rstrip("/") + "/v1/chat/completions"
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(request, timeout=_to_float(timeout)) as response:
            resp_text = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        raise RuntimeError("LM Studio HTTP " + str(error.code) + ": " + error.read().decode("utf-8", "replace"))
    except urllib.error.URLError as error:
        raise RuntimeError(
            "Could not reach LM Studio at " + url + ": " + str(error.reason) +
            ". Check LM Studio's server is running and 'Enable CORS'/network settings if applicable."
        )

    if raw_b:
        return resp_text

    try:
        data = json.loads(resp_text)
    except Exception as e:
        return "Error parsing response: " + str(e) + " | Raw: " + resp_text[:500]

    try:
        choice = data["choices"][0]
        msg = choice["message"]
        usage = data.get("usage", {})
        content = msg.get("content", "")
        reasoning = msg.get("reasoning_content", "")

        result = content
        if reasoning:
            result = "Content: " + content + "\nReasoning: " + reasoning
        result += "\nModel: " + data.get("model", model)
        result += "\nTokens: " + str(usage.get("total_tokens", "n/a"))
        result += "\nFinish: " + str(choice.get("finish_reason", "unknown"))
        return result
    except (KeyError, IndexError, TypeError) as e:
        return "Error extracting response: " + str(e) + " | Raw: " + resp_text[:500]
