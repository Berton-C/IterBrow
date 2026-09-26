# Save this file as transformations/browser_vision.py in the iter repo
# (renamed here to transformations__browser_vision.py only so it doesn't
# collide with tools/ files when copied — see SETUP.md).
#
# Turns a browser_screenshot tool result into an actual image the model can
# see on its next turn, the same way the browser build's own
# transformations/screenshot.py already does for its screenshot tool.
import base64

DESCRIPTION = "Attach browser_screenshot tool results as one-shot multimodal image input."
MARKER = "__ITER_BROWSER_SCREENSHOT__ "


def transform(messages, tools):
    transformed = []
    pending_images = []
    last_assistant = max((i for i, message in enumerate(messages)
                          if message.get("role") == "assistant"), default=-1)
    for position, message in enumerate(messages):
        # A tool batch must remain contiguous: inserting a visual user message
        # between parallel results invalidates the assistant/tool exchange.
        if message.get("role") != "tool" and pending_images:
            transformed.extend(pending_images)
            pending_images = []
        content = message.get("content")
        if message.get("role") != "tool" or not isinstance(content, str) or MARKER not in content:
            transformed.append(message)
            continue

        index = content.find(MARKER)
        path = content[index + len(MARKER):].strip()
        copied = dict(message)
        if position < last_assistant:
            copied["content"] = content[:index].rstrip() + "\n[Historical browser screenshot: " + path + "]"
            transformed.append(copied)
            continue
        data_url = None
        unavailable = "no image was attached"
        try:
            with open(path, "rb") as file:
                image_bytes = file.read()
            if image_bytes:
                data_url = "data:image/png;base64," + base64.b64encode(image_bytes).decode("ascii")
            else:
                unavailable = "capture file is empty; no image was attached"
        except Exception:
            pass

        copied["content"] = content[:index].rstrip() + (
            "\n[BROWSER SCREENSHOT ATTACHED]" if data_url else
            "\n[Browser screenshot unavailable; " + unavailable + ": " + path + "]")
        transformed.append(copied)

        if data_url:
            pending_images.append({
                "role": "user",
                "_iter_runner": True,
                "content": [
                    {"type": "text", "text": "Visual context for browser_screenshot result " +
                     str(message.get("tool_call_id", "")) + " in the preceding tool batch."},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            })
            # A transformation is not a successful model request. Keep the
            # temporary capture so failed/retried requests can attach it again.
            # Once a later assistant response exists, history gets a path only.

    transformed.extend(pending_images)
    return transformed, tools
