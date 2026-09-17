# Synthetic fixture: DESCRIPTION longer than MAX_TOOL_DESCRIPTION_CHARS (500),
# to verify truncation + marker parity -- mirrors real files browser_patch_live.py,
# device_capture.py, and lm_studio_chat.py which are ALSO over 500 chars today.
DESCRIPTION = "This description is deliberately long enough to exceed the 500 character MAX_TOOL_DESCRIPTION_CHARS truncation limit so the parity test can confirm the static parser applies the exact same truncation and appends the exact same marker text as iter.py's dynamic_worker does today. This description is deliberately long enough to exceed the 500 character MAX_TOOL_DESCRIPTION_CHARS truncation limit so the parity test can confirm the static parser applies the exact same truncation and appends the exact same marker text as iter.py's dynamic_worker does today. This description is deliberately long enough to exceed the 500 character MAX_TOOL_DESCRIPTION_CHARS truncation limit so the parity test can confirm the static parser applies the exact same truncation and appends the exact same marker text as iter.py's dynamic_worker does today. "

def run(a):
    return a
