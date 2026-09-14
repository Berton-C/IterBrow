# Save this file as transformations/browser_vision.py in the iter repo
# (renamed here to transformations__browser_vision.py only so it doesn't
# collide with tools/ files when copied — see SETUP.md).
#
# Turns a browser_screenshot tool result into an actual image the model can
# see on its next turn, the same way the browser build's own
# transformations/screenshot.py already does for its screenshot tool.
import base64
import os

DESCRIPTION = "Attach browser_screenshot tool results as one-shot multimodal image input."
MARKER = "__ITER_BROWSER_SCREENSHOT__ "


def transform(messages, tools):
    transformed = []
    for message in messages:
        content = message.get("content")
        if message.get("role") != "tool" or not isinstance(content, str) or MARKER not in content:
            transformed.append(message)
            continue

        index = content.find(MARKER)
        path = content[index + len(MARKER):].strip()
        copied = dict(message)
        data_url = None
        try:
            with open(path, "rb") as file:
                data_url = "data:image/png;base64," + base64.b64encode(file.read()).decode("ascii")
        except Exception:
            pass

        copied["content"] = content[:index].rstrip() + "\n[BROWSER SCREENSHOT CAPTURED]"
        transformed.append(copied)

        if data_url:
            transformed.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": "Visual context for the immediately preceding browser_screenshot result."},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            })
            try:
                os.remove(path)
            except OSError:
                pass

    return transformed, tools
