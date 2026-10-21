"""M15-B1: the tool list the model sees is a view of the request, never a removal.

`view(tools, mode)`: "build" (an app is being made, `build_mode.active`) offers the builder's set; "chat"
hides the build-only tools. Hidden means not in this request; every tool is offered again next cycle.
Order and the tool dicts are kept (a filter, never a copy-and-edit); an unknown mode changes nothing.
Spec: docs/milestones/M15_build_ledger.md section B.
"""

# The builder's hands, eyes and voice: files, tests, the browser actions and reads, the app tools, research,
# the person's cards and briefs, waiting and remembering. The loop's never-drop names are in it too.
BUILD = frozenset({
    "read_file", "write_file", "edit_file", "list_files", "grep_files", "run_tests", "shell", "python",
    "browser_click", "browser_type", "browser_scroll", "browser_eval", "browser_read_text", "browser_screenshot",
    "browser_wait_for", "browser_open_app", "browser_navigate", "browser_new_tab", "browser_tabs", "browser_attach",
    "browser_switch_tab", "browser_close_tab",
    "new_app", "app_probe", "app_rollback", "apps", "github", "websearch",
    "card", "brief", "ally_sdk", "send", "nop", "task_state", "remember", "memory_update",
    "read_tool_result", "start_new_task", "pin",
})

# Tools that only make sense while building; a conversation does not need their schemas.
BUILD_ONLY = frozenset({"new_app", "app_probe", "app_rollback", "github", "run_tests"})


def _name(tool):
    return (tool.get("function") or {}).get("name") if isinstance(tool, dict) else None


def view(tools, mode):
    if mode == "build":
        return [tool for tool in tools if _name(tool) in BUILD]
    if mode == "chat":
        return [tool for tool in tools if _name(tool) not in BUILD_ONLY]
    return tools
