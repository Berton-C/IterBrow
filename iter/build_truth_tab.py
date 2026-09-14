tools = [
    ("browser_attach", 0.6667, 0.9376, 15, 10, 5),
    ("browser_cdp", 0.5000, 0.5000, 2, 1, 1),
    ("browser_click", 0.5000, 0.5000, 2, 1, 1),
    ("browser_close_tab", 0.7501, 0.9413, 16, 12, 4),
    ("browser_detach", 1.0000, 0.9167, 11, 11, 0),
    ("browser_eval", 0.8333, 0.7500, 4, 3, 1),
    ("browser_navigate", 0.8750, 0.8889, 8, 7, 1),
    ("browser_new_tab", 1.0000, 0.9167, 11, 11, 0),
    ("browser_patch_live", 0.0000, 0.6667, 2, 0, 2),
    ("browser_read_text", 0.6252, 0.9413, 16, 10, 6),
    ("browser_screenshot", 0.9286, 0.8750, 8, 7, 1),
    ("browser_scroll", 0.5714, 0.8750, 7, 4, 3),
    ("browser_switch_tab", 0.5000, 0.5000, 2, 1, 1),
    ("browser_tabs", 1.0000, 0.9525, 20, 20, 0),
    ("browser_type", 0.5000, 0.5000, 2, 1, 1),
    ("chroma_query", 0.9929, 0.9930, 998, 908, 90),
    ("contradict", 1.0000, 0.9231, 12, 12, 0),
    ("episodes", 1.0000, 0.9930, 206, 206, 0),
    ("eval", 0.6397, 0.9617, 25, 16, 9),
    ("forget", 1.0000, 0.6667, 2, 2, 0),
    ("formalize_metta", 1.0000, 0.9923, 125, 125, 0),
    ("link_episode", 1.0000, 0.9876, 79, 79, 0),
    ("lm_studio_chat", 0.2500, 0.6667, 3, 1, 2),
    ("memory_journal", 1.0000, 0.9830, 58, 58, 0),
    ("memory_update", 1.0000, 0.9697, 32, 32, 0),
    ("metta", 0.9298, 0.9883, 85, 79, 6),
    ("museum_list", 0.6000, 0.8333, 5, 3, 2),
    ("nop", 1.0000, 0.9930, 506, 506, 0),
    ("petta_db", 1.0000, 0.9762, 41, 41, 0),
    ("pin", 1.0000, 0.9930, 160, 160, 0),
    ("preview", 1.0000, 0.7500, 3, 3, 0),
    ("python", 0.9303, 0.9930, 245, 233, 12),
    ("rebuild_tiers", 1.0000, 0.8000, 4, 4, 0),
    ("remember", 0.9359, 0.9893, 95, 89, 6),
    ("reminder", 0.6667, 0.9000, 9, 6, 3),
    ("screenshot", 1.0000, 0.9501, 19, 19, 0),
    ("search_transcript", 1.0000, 0.9376, 15, 15, 0),
    ("self_improve", 0.8211, 0.9824, 56, 46, 10),
    ("send", 0.9830, 0.9930, 287, 282, 5),
    ("shell", 0.9348, 0.9930, 3301, 3047, 254),
    ("soul_eval", 0.7834, 0.9895, 97, 76, 21),
    ("soul_eval_v3_backup", 1.0000, 0.5000, 1, 1, 0),
    ("soul_lock", 0.7500, 0.8000, 4, 3, 1),
    ("soul_skill_registry", 0.5713, 0.8750, 7, 4, 3),
    ("start_new_task", 1.0000, 0.9930, 135, 135, 0),
    ("support", 1.0000, 0.9930, 302, 302, 0),
    ("test_soul_absent", 1.0000, 0.5000, 1, 1, 0),
    ("token_awareness", 1.0000, 0.6667, 2, 2, 0),
    ("tool_reliability", 1.0000, 0.9882, 84, 84, 0),
    ("websearch", 0.8312, 0.9911, 112, 44, 65),
]

def f_color(f):
    if f >= 0.9: return "#2da44e"
    if f >= 0.7: return "#3fb950"
    if f >= 0.5: return "#d29922"
    return "#f85149"

def c_color(c):
    if c >= 0.9: return "#2da44e"
    if c >= 0.7: return "#d29922"
    return "#f85149"

def bar(val, color):
    pct = round(val*100)
    return ('<div style="display:flex;align-items:center;gap:6px"><div style="width:80px;height:8px;background:#21262d;border-radius:4px;overflow:hidden"><div style="width:' + str(pct) + '%;height:100%;background:' + color + '"></div></div><span style="font-size:12px;color:' + color + '">' + format(val, '.4f') + '</span></div>')

rows = []
for name, f, c, calls, succ, fail in sorted(tools, key=lambda t: -t[3]):
    status = "ACTIVE" if f >= 0.5 else "HIDDEN"
    status_color = "#2da44e" if f >= 0.5 else "#f85149"
    rows.append('<tr><td style="padding:6px 10px;border-bottom:1px solid #30363d;font-family:monospace;color:#58a6ff">' + name + '</td><td style="padding:6px 10px;border-bottom:1px solid #30363d">' + bar(f, f_color(f)) + '</td><td style="padding:6px 10px;border-bottom:1px solid #30363d">' + bar(c, c_color(c)) + '</td><td style="padding:6px 10px;border-bottom:1px solid #30363d;text-align:right">' + format(calls, ',') + '</td><td style="padding:6px 10px;border-bottom:1px solid #30363d;text-align:right;color:#3fb950">' + format(succ, ',') + '</td><td style="padding:6px 10px;border-bottom:1px solid #30363d;text-align:right;color:#f85149">' + format(fail, ',') + '</td><td style="padding:6px 10px;border-bottom:1px solid #30363d;text-align:center;color:' + status_color + ';font-size:11px">' + status + '</td></tr>')

total_calls = sum(t[3] for t in tools)
total_succ = sum(t[4] for t in tools)
total_fail = sum(t[5] for t in tools)
overall_f = total_succ/total_calls
hidden = [t for t in tools if t[1] < 0.5]

head = ('<!DOCTYPE html><html><head><meta charset="utf-8"><title>Iter - NAL Tool Truth Tables</title>'
'<style>body{background:#0d1117;color:#c9d1d9;font-family:system-ui;margin:0;padding:20px}'
'h1{color:#58a6ff;font-size:22px;margin-bottom:4px}'
'table{border-collapse:collapse;width:100%;background:#161b22;border:1px solid #30363d;border-radius:8px;overflow:hidden}'
'th{background:#21262d;color:#58a6ff;padding:8px 10px;text-align:left;font-size:12px;border-bottom:2px solid #30363d}'
'.note{font-size:12px;color:#8b949e;margin-bottom:16px}'
'.legend{display:flex;gap:16px;font-size:12px;color:#8b949e;margin:8px 0 16px 0;flex-wrap:wrap}'
'.legend span{display:flex;align-items:center;gap:4px}'
'.dot{width:10px;height:10px;border-radius:50%;display:inline-block}'
'.summary{display:flex;gap:12px;flex-wrap:wrap;margin:12px 0}'
'.stat{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px 16px;min-width:140px}'
'.stat .v{font-size:24px;font-weight:bold;color:#58a6ff}'
'.stat .l{font-size:11px;color:#8b949e}'
'</style></head><body>'
'<h1>&#9878;&#65039; NAL Tool Truth Tables</h1>'
'<div class="note">Non-Axiomatic Logic truth values for every tool Iter can call. f = frequency (success rate), c = confidence (evidence strength). Live from tool_reliability tracker &middot; 2026-09-13 13:09</div>')

summary = ('<div class="summary">'
'<div class="stat"><div class="v">' + str(len(tools)) + '</div><div class="l">tools tracked</div></div>'
'<div class="stat"><div class="v">' + format(total_calls, ',') + '</div><div class="l">total calls</div></div>'
'<div class="stat"><div class="v">' + format(overall_f, '.4f') + '</div><div class="l">overall f</div></div>'
'<div class="stat"><div class="v">' + str(len(hidden)) + '</div><div class="l">hidden (f<0.5)</div></div>'
'</div>')

legend = ('<div class="legend">'
'<span><span class="dot" style="background:#2da44e"></span> f&ge;0.9 excellent</span>'
'<span><span class="dot" style="background:#3fb950"></span> f&ge;0.7 good</span>'
'<span><span class="dot" style="background:#d29922"></span> f&ge;0.5 caution</span>'
'<span><span class="dot" style="background:#f85149"></span> f<0.5 hidden by budget</span>'
'</div>')

table = ('<table><tr><th>Tool</th><th>f (frequency)</th><th>c (confidence)</th><th style="text-align:right">calls</th><th style="text-align:right">succ</th><th style="text-align:right">fail</th><th style="text-align:center">status</th></tr>'
+ ''.join(rows) + '</table>')

nal_note = ('<div class="note" style="margin-top:16px">'
'<b>NAL truth-value semantics:</b> Each tool carries a truth value &lang;f, c&rang; where f = w+/(w+ + w&minus;) is the '
'frequency of success and c = (w+ + w&minus;)/(k + w+ + w&minus;) is confidence (k=1 evidential horizon). '
'Higher c means more accumulated evidence; f near 1 with high c means the tool is reliably useful. '
'Tools with f < 0.5 are auto-hidden by the Dynamic Tool Budget to conserve cycles.'
'</div>')

html = head + summary + legend + table + nal_note + '</body></html>'

with open('truth_tables.html', 'w') as fh:
    fh.write(html)
print('written', len(html), 'chars,', len(tools), 'tools,', len(hidden), 'hidden')
