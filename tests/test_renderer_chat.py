#!/usr/bin/env python3
"""Sidebar chat: Markdown rendering, formatting bar and the light theme."""
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")


@unittest.skipUnless(NODE, "needs node")
class ChatRenderingTests(unittest.TestCase):
    def test_markdown_renderer_contract_and_safety(self):
        result = subprocess.run([NODE, str(ROOT / "tests" / "node" / "markdown_test.js")],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("all assertions passed", result.stdout)

    def test_chat_uses_the_renderer_and_links_open_in_tabs(self):
        html = (ROOT / "renderer" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "renderer" / "renderer.js").read_text(encoding="utf-8")
        self.assertLess(html.index('<script src="markdown.js">'), html.index('<script src="renderer.js">'))
        self.assertIn("window.IterMarkdown.render(message.content)", js)
        # system notes are never rendered as markup; user and Iter messages are
        self.assertIn("if (message.role === 'sys') body.textContent = message.content;", js)
        self.assertIn("window.iterApi.newTab(href)", js)
        self.assertIn("event.preventDefault();\n  const href = window.IterMarkdown.safeHref", js)

    def test_formatting_bar_shortcuts_and_preview_exist(self):
        html = (ROOT / "renderer" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "renderer" / "renderer.js").read_text(encoding="utf-8")
        for name in ("bold", "italic", "strike", "heading", "link", "code", "quote", "bullet", "number"):
            self.assertIn('data-format="%s"' % name, html)
            self.assertIn("%s:" % name, js)
        self.assertIn('id="btn-preview"', html)
        self.assertIn("function togglePreview", js)
        for key in ("'b'", "'i'", "'k'"):
            self.assertIn("key === %s" % key, js)
        # Enter still sends, Shift+Enter still makes a new line
        self.assertIn("if (e.key === 'Enter' && !e.shiftKey)", js)

    def test_light_theme_is_consistent_across_the_three_views(self):
        for name in ("style.css", "toolbar.css", "tabstrip.css"):
            css = (ROOT / "renderer" / name).read_text(encoding="utf-8")
            self.assertIn("color-scheme: light", css, name)
            self.assertNotIn("color-scheme: dark", css, name)
            root = css[css.index(":root"):css.index("}")]
            bg = re.search(r"--bg:\s*(#[0-9a-fA-F]{6})", root).group(1)
            # a light background: every channel well above mid-grey
            self.assertTrue(all(int(bg[i:i + 2], 16) > 0xd0 for i in (1, 3, 5)), (name, bg))
        main = (ROOT / "main.js").read_text(encoding="utf-8")
        style = (ROOT / "renderer" / "style.css").read_text(encoding="utf-8")
        sidebar_bg = re.search(r"const SIDEBAR_BG = '(#[0-9a-fA-F]{6})'", main).group(1)
        self.assertIn("--bg: %s;" % sidebar_bg, style)

    def test_chat_prose_is_not_monospace(self):
        style = (ROOT / "renderer" / "style.css").read_text(encoding="utf-8")
        start = style.index("\nbody {")
        body = style[start:style.index("}", start)]
        self.assertNotIn("monospace", body)
        self.assertIn("var(--font-ui)", body)


    def test_links_never_navigate_the_sidebar_including_the_preview(self):
        js = (ROOT / "renderer" / "renderer.js").read_text(encoding="utf-8")
        main = (ROOT / "main.js").read_text(encoding="utf-8")
        # one capture-phase handler covers the chat, the composer preview and every panel
        self.assertIn("document.addEventListener('click', (event) => {\n  const anchor = event.target.closest('a[href]');\n  if (!anchor) return;\n  event.preventDefault();", js)
        self.assertNotIn("chat.addEventListener('click'", js)
        self.assertIn("if (event.target.closest('a')) return; // the link opened as a tab; keep previewing", js)
        # and the main process refuses any navigation of the three UI views
        self.assertIn("function pinUiViewToItsPage(view, name)", main)
        self.assertIn("contents.on('will-navigate', (event, url) => {", main)
        self.assertIn("contents.setWindowOpenHandler(({ url }) => { openAsTab(url); return { action: 'deny' }; });", main)
        for view in ("sidebarView", "toolbarView", "tabstripView"):
            self.assertIn("pinUiViewToItsPage(%s," % view, main)
            self.assertLess(main.index("pinUiViewToItsPage(%s," % view), main.index("%s.webContents.loadFile" % view))


if __name__ == "__main__":
    unittest.main()
