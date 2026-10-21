#!/usr/bin/env python3
"""M16 (already here): two of the four shell features Berton asked for from EAOS exist in IterBrow — pinned so
they are not rebuilt. Markdown in the chat (renderer/markdown.js) and drag-to-reorder tabs (tabstrip.js +
TabManager.reorder). Spec: docs/milestones/M16_shell_from_eaos.md "Already here". These tests pass today.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m16_support import source, popout_node, node, REPO  # noqa: E402


class MarkdownPresentTests(unittest.TestCase):
    """M16 (present): Iter's replies are rich text."""

    def test_renderer_renders_messages_and_cards_through_a_dependency_free_module(self):
        md = source("renderer/markdown.js")
        self.assertNotIn("require(", md.split("module.exports")[0].split("factory")[0], "no dependency")
        js = source("renderer/renderer.js")
        self.assertIn("IterMarkdown.render(message.content)", js)
        self.assertIn("IterMarkdown.render(card.body)", js)
        code, out, err = node("const M = require(%r); process.stdout.write(M.render('# Hi\\n\\n**bold** `x` <b>no</b>\\n\\n- a\\n- b'));"
                              % str(REPO / "renderer" / "markdown.js"))
        self.assertEqual(code, 0, err)
        self.assertIn("<h1>", out); self.assertIn("<strong>bold</strong>", out); self.assertIn("<code>x</code>", out)
        self.assertIn("&lt;b&gt;", out, "HTML in the input is escaped"); self.assertIn("<li>", out)


class ReorderPresentTests(unittest.TestCase):
    """M16 (present): tabs drag to a new position; pinned tabs stay first."""

    def test_pills_are_draggable_and_reorder_keeps_pinned_first(self):
        strip = source("renderer/tabstrip.js")
        self.assertIn("pill.draggable = true", strip); self.assertIn("'drop'", strip); self.assertIn("reorderTabs(", strip)
        out = popout_node("""
const a = tabs.createTab('https://a.example'), b = tabs.createTab('https://b.example'), c = tabs.createTab('https://c.example');
tabs.setPinned(c, true);
tabs.reorder([b, a, c]);
out.order = tabs.list().map((t) => t.id);
""")
        self.assertEqual(out["order"], [3, 2, 1], "pinned first, then the dragged order")


if __name__ == "__main__":
    unittest.main()
