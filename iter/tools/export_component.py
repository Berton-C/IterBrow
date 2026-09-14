"""OpenUI-inspired browser feature #6: HTML -> portable component export.

Mirrors OpenUI's framework-conversion feature (it can re-render a
generated UI as React/Svelte/Vue/vanilla-JS). Takes a component-museum
entry (or raw html/css/js passed directly) and writes a standalone file
the user can drop into a real project - e.g. their ClarityOmega source
tree - instead of it only ever existing as a live-injected DOM patch or a
museum record inside Iter's own memory.

This performs a straightforward, deterministic wrap/convert (no LLM call)
so it is always available and reproducible:
  - vanilla : a single self-contained .html file (inline <style>/<script>)
  - react   : a functional component .jsx file (CSS is inlined via a
              <style> tag injected on mount; JS logic runs in a useEffect)
  - svelte  : a .svelte single-file component (script/style/markup blocks)

Output is written under .runtime/exports/ (Iter's own working directory -
NOT a protected memory path) and also returned inline so the agent can
hand the code directly to the user or place it via other means.
"""

import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _component_museum as museum

DESCRIPTION = (
    "Export a component-museum entry (by component_id) or raw html/css/js as a portable, "
    "standalone component file: framework='vanilla' (single .html file), 'react' (.jsx "
    "functional component), or 'svelte' (.svelte single-file component). Writes to "
    ".runtime/exports/ and returns the generated code inline so it can be handed to the user "
    "for saving into a real project."
)

EXPORT_DIR = Path(".runtime/exports")


def _slug(name):
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", (name or "component")).strip("-")
    return slug or "component"


def _strip_html_shell(html):
    """Pull just the <body> inner markup out of a full <html> document, if
    given one; passes fragments through unchanged."""
    if not html:
        return ""
    match = re.search(r"<body[^>]*>(.*?)</body>", html, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else html.strip()


def _resolve_source(component_id, html, css, js):
    if component_id:
        record = museum.get(component_id)
        if not record:
            raise ValueError("no museum entry found for id=%r" % (component_id,))
        html = html or museum.full_field(record, "html")
        css = css or museum.full_field(record, "css")
        js = js or museum.full_field(record, "js")
        label = record.get("label", component_id)
    else:
        label = "exported-component"
    return html or "", css or "", js or "", label


def _render_vanilla(html, css, js, label):
    body = _strip_html_shell(html) or "<div>%s</div>" % label
    return (
        "<!DOCTYPE html>\n<html>\n<head>\n<meta charset=\"utf-8\">\n<title>%s</title>\n"
        "<style>\n%s\n</style>\n</head>\n<body>\n%s\n<script>\n%s\n</script>\n</body>\n</html>\n"
    ) % (label, css, body, js)


def _render_react(html, css, js, label):
    body = _strip_html_shell(html) or "<div>%s</div>" % label
    comp_name = "".join(p.capitalize() for p in re.split(r"[^a-zA-Z0-9]+", label) if p) or "ExportedComponent"
    return (
        "import React, { useEffect, useRef } from 'react';\n\n"
        "// Auto-exported by Iter Browser's export_component tool.\n"
        "// CSS is scoped via an injected <style> tag on mount; original inline JS\n"
        "// (if any) runs against the rendered root via the ref below - review before\n"
        "// relying on it in a real app, this is a direct, un-optimized port.\n\n"
        "const %s = () => {\n"
        "  const rootRef = useRef(null);\n\n"
        "  useEffect(() => {\n"
        "    const style = document.createElement('style');\n"
        "    style.textContent = %r;\n"
        "    document.head.appendChild(style);\n\n"
        "    const cleanupFns = [];\n"
        "    try {\n"
        "      const root = rootRef.current;\n"
        "      %s\n"
        "    } catch (e) { console.error('exported component script error', e); }\n\n"
        "    return () => {\n"
        "      style.remove();\n"
        "      cleanupFns.forEach((fn) => fn());\n"
        "    };\n"
        "  }, []);\n\n"
        "  return (\n"
        "    <div ref={rootRef} dangerouslySetInnerHTML={{ __html: %r }} />\n"
        "  );\n"
        "};\n\n"
        "export default %s;\n"
    ) % (comp_name, css, js or "// no injected JS", body, comp_name)


def _render_svelte(html, css, js, label):
    body = _strip_html_shell(html) or "<div>%s</div>" % label
    return (
        "<script>\n"
        "  // Auto-exported by Iter Browser's export_component tool.\n"
        "  import { onMount } from 'svelte';\n"
        "  onMount(() => {\n"
        "    try {\n%s\n    } catch (e) { console.error('exported component script error', e); }\n"
        "  });\n"
        "</script>\n\n"
        "%s\n\n"
        "<style>\n%s\n</style>\n"
    ) % (js or "  // no injected JS", body, css)


RENDERERS = {"vanilla": _render_vanilla, "react": _render_react, "svelte": _render_svelte}
EXTENSIONS = {"vanilla": ".html", "react": ".jsx", "svelte": ".svelte"}


def run(framework="vanilla", component_id="", html="", css="", js="", name=""):
    framework = (framework or "vanilla").lower()
    if framework not in RENDERERS:
        return "ERROR: framework must be one of %s" % (list(RENDERERS.keys()),)

    resolved_html, resolved_css, resolved_js, label = _resolve_source(component_id, html, css, js)
    if not resolved_html and not resolved_css and not resolved_js:
        return "ERROR: nothing to export - pass component_id or at least one of html/css/js"

    name = name or label
    code = RENDERERS[framework](resolved_html, resolved_css, resolved_js, name)

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    filename = _slug(name) + "-%d" % int(time.time() * 1000) + EXTENSIONS[framework]
    out_path = EXPORT_DIR / filename
    out_path.write_text(code, encoding="utf-8")

    try:
        import memory_journal
        memory_journal.log("export_component", "exported", {"path": str(out_path), "framework": framework, "component_id": component_id})
    except Exception:
        pass

    return "exported %s component to %s\n\n%s" % (framework, out_path, code)
