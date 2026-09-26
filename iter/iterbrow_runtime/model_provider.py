"""Provider transport only; Iter's existing loop, tools and memory stay in charge."""
import copy
import json
import time
from pathlib import Path
from types import SimpleNamespace

from openai.types.chat import ChatCompletionMessage

CATALOG = json.loads(Path(__file__).with_name("openai_models.json").read_text())
RATES = {model["id"]: model for model in CATALOG["models"]}


def request_view(messages, provider, model):
    """Omit incompatible provider metadata from copies, never durable experience."""
    result = copy.deepcopy(messages)
    for message in result:
        native = message.get("_iter_openai_response")
        if provider == "openai":
            # GLM/OpenRouter reasoning is not OpenAI continuation state. Keep the
            # actual actions, observations and visible conversation on switching.
            for key in ("reasoning", "reasoning_content", "reasoning_details"):
                message.pop(key, None)
            # The offered tiers are one GPT-6 family. Keep compatible opaque
            # continuation items when the user switches tiers, too.
            if native and not native.get("model", "").startswith("gpt-6-"):
                message.pop("_iter_openai_response", None)
        else:
            message.pop("_iter_openai_response", None)
    return result


def _content(content):
    if isinstance(content, str):
        return content
    parts = []
    for part in content or []:
        if part.get("type") == "text":
            parts.append({"type": "input_text", "text": part["text"]})
        elif part.get("type") == "image_url":
            image = part["image_url"]
            parts.append({"type": "input_image", "image_url": image["url"],
                          "detail": image.get("detail", "auto")})
        else:
            raise ValueError("Unsupported OpenAI input content: " + str(part.get("type")))
    return parts


def response_input(messages):
    items = []
    for message in messages:
        role = message["role"]
        if role == "tool":
            items.append({"type": "function_call_output", "call_id": message["tool_call_id"],
                          "output": message.get("content", "")})
        elif role == "assistant":
            native = message.get("_iter_openai_response")
            if native:
                # Preserve ordering, phase and encrypted reasoning exactly. If
                # Iter's existing per-cycle cap omitted a call, acknowledge that
                # it was NOT executed; never leave an orphan or invent success.
                items.extend(copy.deepcopy(native["output"]))
                executed = {call["id"] for call in message.get("tool_calls", [])}
                for item in native["output"]:
                    if item["type"] == "function_call" and item["call_id"] not in executed:
                        items.append({"type": "function_call_output", "call_id": item["call_id"],
                                      "output": "Not executed: the existing per-cycle tool limit was reached."})
            else:
                if message.get("content"):
                    items.append({"role": "assistant", "content": message["content"]})
                for call in message.get("tool_calls", []):
                    items.append({"type": "function_call", "call_id": call["id"],
                                  "name": call["function"]["name"],
                                  "arguments": call["function"]["arguments"]})
        else:
            items.append({"role": role, "content": _content(message.get("content", ""))})
    return items


def _strict_arguments(parameters):
    """Enable strict mode for Iter's already-compatible flat string schemas.

    Optional/default parameters and richer schemas retain their exact contract;
    do not silently make optional values required or nullable to fit strict mode.
    """
    return (
        parameters.get("type") == "object"
        and parameters.get("additionalProperties") is False
        and set(parameters) <= {"type", "properties", "required", "additionalProperties", "description"}
        and set(parameters.get("required", [])) == set(parameters.get("properties", {}))
        and all(value.get("type") == "string" and set(value) <= {"type", "description"}
                for value in parameters.get("properties", {}).values())
    )


def request_kwargs(provider, model, messages, tools, max_tokens, effort="low", extra_body=None):
    if provider != "openai":
        return {"model": model, "messages": messages, "tools": tools,
                "tool_choice": "required", "max_tokens": max_tokens,
                "extra_body": extra_body or {}}
    if model not in RATES or effort not in ("low", "medium", "high"):
        raise ValueError("Choose a supported OpenAI model and reasoning effort in Settings")
    functions = []
    for tool in tools:
        if tool.get("type") != "function":
            raise ValueError("Iter currently exposes function tools only")
        function = tool["function"]
        functions.append({"type": "function", "name": function["name"],
                          "description": function.get("description", ""),
                          "parameters": copy.deepcopy(function["parameters"]),
                          "strict": _strict_arguments(function["parameters"])})
    return {"model": model, "input": response_input(messages), "tools": functions,
            "tool_choice": "required", "max_output_tokens": max_tokens,
            "reasoning": {"effort": effort}, "store": False, "service_tier": "default"}


def _normalize(response, model):
    raw = response.model_dump(exclude_none=True)
    output = raw.get("output", [])
    text, calls = [], []
    for item in output:
        if item["type"] == "message":
            text.extend(p.get("text", p.get("refusal", "")) for p in item.get("content", []))
        elif item["type"] == "function_call":
            calls.append({"id": item["call_id"], "type": "function",
                          "function": {"name": item["name"], "arguments": item["arguments"]}})
    incomplete = raw.get("status") == "incomplete"
    if raw.get("status") not in ("completed", "incomplete"):
        raise ValueError("OpenAI returned no completed response: " + str(raw.get("status")))
    # Partial arguments must not dispatch. The ordinary loop already retries a
    # length-limited response with no calls; no new executor or retry loop.
    message = ChatCompletionMessage.model_validate({
        "role": "assistant", "content": "\n".join(text) or None,
        "tool_calls": [] if incomplete else calls,
        "_iter_openai_response": {"model": model, "output": output},
    })
    return SimpleNamespace(choices=[SimpleNamespace(message=message,
                           finish_reason="length" if incomplete else "stop")],
                           usage=raw.get("usage"), id=raw.get("id"))


def call_model(client, provider, model, messages, tools, max_tokens, *, effort="low",
               extra_body=None, usage_path=None):
    kwargs = request_kwargs(provider, model, messages, tools, max_tokens, effort, extra_body)
    started = time.monotonic()
    response = (client.responses.create(**kwargs) if provider == "openai"
                else client.chat.completions.create(**kwargs))
    elapsed = time.monotonic() - started
    if provider == "openai":
        response = _normalize(response, model)
        usage = response.usage or {}
        rate = RATES[model]
        cached = (usage.get("input_tokens_details") or {}).get("cached_tokens", 0) or 0
        written = (usage.get("input_tokens_details") or {}).get("cache_write_tokens", 0) or 0
        input_tokens, output_tokens = usage.get("input_tokens"), usage.get("output_tokens")
        cost = None if input_tokens is None or output_tokens is None else (
            max(0, input_tokens - cached - written) * rate["input"] + cached * rate["cachedInput"]
            + written * rate["cacheWrite"]
            + output_tokens * rate["output"]) / 1_000_000
        record = {"provider": provider, "model": model, "at": time.time(),
                  "seconds": round(elapsed, 2), "usage": usage,
                  "estimated_usd": cost, "pricing_checked": CATALOG["verifiedOn"],
                  "note": "Standard text-token estimate including reported cache reads/writes; excludes image, regional and other surcharges."}
        print("[model usage] " + json.dumps(record, sort_keys=True))
        if usage_path:
            try:
                dest = Path(usage_path)
                dest.parent.mkdir(parents=True, exist_ok=True)
                temporary = dest.with_suffix(".next")
                temporary.write_text(json.dumps(record))
                temporary.replace(dest)
            except OSError as error:
                print("[model usage] display record unavailable: " + type(error).__name__)
    return response
