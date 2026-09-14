"""Workbench Scroll is disabled: this runtime has no js DOM bridge, and the framework expects a (messages, tools) tuple."""
DESCRIPTION = "Disabled placeholder for workbench scroll."

def transform(messages, tools):
    return messages, tools
