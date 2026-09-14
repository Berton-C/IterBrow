import time, json, os

DESCRIPTION = "Runtime dashboard without atom-space visualization or recent messages"

ROOT = "."
TASKS_FILE = ROOT + "/memory/tasks/current_tasks.txt"
ALARMS_DIR = ROOT + "/memory/alarms"

def _escape_html(value):
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#x27;")

def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False

def _isdir(path):
    try:
        return bool(os.stat(path)[0] & 0x4000)
    except OSError:
        return False

def _walk_files(root):
    result = []
    stack = [root]
    while stack:
        folder = stack.pop()
        try:
            names = sorted(os.listdir(folder))
        except OSError:
            continue
        subdirs = []
        for name in names:
            full = folder.rstrip("/") + "/" + name
            if _isdir(full):
                subdirs.append(full)
            else:
                result.append(full)
        for full in reversed(subdirs):
            stack.append(full)
    return sorted(result)

def _fmt_time(value=None):
    t = time.localtime() if value is None else time.localtime(value)
    return "%04d-%02d-%02d %02d:%02d:%02d" % (t[0], t[1], t[2], t[3], t[4], t[5])

def _fmt_int(value):
    try:
        s = str(int(value))
        sign = ""
        if s.startswith("-"):
            sign, s = "-", s[1:]
        parts = []
        while len(s) > 3:
            parts.insert(0, s[-3:])
            s = s[:-3]
        parts.insert(0, s)
        return sign + ",".join(parts)
    except Exception:
        return str(value)

def get_system_info():
    tools_dir = ROOT + "/tools"
    tool_files = []
    if _isdir(tools_dir):
        for name in sorted(os.listdir(tools_dir)):
            if name.startswith("__"):
                continue
            if name.endswith(".py") or name.endswith(".js"):
                tool_files.append(name.rsplit(".", 1)[0])
    seen = set()
    tools = []
    for name in tool_files:
        if name not in seen:
            seen.add(name)
            tools.append(name)

    channels = []
    chan_dir = ROOT + "/channels"
    if _isdir(chan_dir):
        for name in sorted(os.listdir(chan_dir)):
            if name.endswith(".py") and not name.startswith("_"):
                channels.append(name[:-3])

    transforms = []
    trans_dir = ROOT + "/transformations"
    if _isdir(trans_dir):
        for name in sorted(os.listdir(trans_dir)):
            if name.endswith(".py"):
                transforms.append(name[:-3])

    mem_files = []
    total_size = 0
    mem_dir = ROOT + "/memory"
    if _isdir(mem_dir):
        for full in _walk_files(mem_dir):
            name = full.rsplit("/", 1)[-1]
            if name.startswith("_"):
                continue
            try:
                size = os.stat(full)[6]
            except OSError:
                continue
            total_size += size
            rel = full[len(ROOT) + 1:] if full.startswith(ROOT + "/") else full
            mem_files.append((rel, size))
    return tools, channels, transforms, mem_files, total_size

def upload_html(html_doc):
    try:
        with open(ROOT + "/dashboard_runtime.html", "w") as f:
            f.write(html_doc)
    except Exception:
        pass

def get_tool_reliability():
    tr_file = ROOT + "/transformations/.runtime/tool_reliability.json"
    tools_dir = ROOT + "/tools"
    if not _exists(tr_file):
        return []
    try:
        existing_tools = set()
        if _isdir(tools_dir):
            for name in os.listdir(tools_dir):
                if name.endswith(".py") and not name.startswith("_"):
                    existing_tools.add(name[:-3])
        with open(tr_file) as f:
            data = json.loads(f.read())
        rows = []
        for name, info in sorted(data.items(), key=lambda x: -x[1].get("calls", 0)):
            if name not in existing_tools:
                continue
            rows.append({
                "name": name,
                "f": info.get("f", 0),
                "c": info.get("c", 0),
                "calls": info.get("calls", 0),
                "successes": info.get("successes", 0),
                "failures": info.get("failures", 0)
            })
        return rows
    except Exception:
        return []

def get_alarms():
    alarms = []
    if not _isdir(ALARMS_DIR):
        return alarms
    now = time.time()
    for name in sorted(os.listdir(ALARMS_DIR)):
        full = ALARMS_DIR + "/" + name
        if _isdir(full):
            continue
        try:
            target_time = float(name)
        except ValueError:
            continue
        try:
            with open(full) as f:
                content = f.read().strip()
        except Exception:
            continue
        lines = content.split("\n", 1)
        if len(lines) == 2:
            channel, msg = lines
        else:
            channel, msg = "terminal", content
        trigger_str = _fmt_time(target_time)
        delta = target_time - now
        if delta > 0:
            if delta >= 86400:
                remaining = "{:.0f}d {:.0f}h".format(delta / 86400, (delta % 86400) / 3600)
            elif delta >= 3600:
                remaining = "{:.0f}h {:.0f}m".format(delta / 3600, (delta % 3600) / 60)
            else:
                remaining = "{:.0f}m".format(delta / 60)
        else:
            remaining = "OVERDUE"
        alarms.append({
            "trigger": trigger_str,
            "channel": channel,
            "message": msg,
            "remaining": remaining
        })
    return alarms

CSS = r"""
:root{
  color-scheme:dark;
  --bg:#0b0d10;--panel:#111419;--panel3:#0f1217;
  --line:#2a3039;--text:#d8dee9;--strong:#eef2f7;
  --muted:#808a98;--dim:#5f6977;--blue:#6ea8fe;--green:#7ccf91;
  --orange:#e7a86e;--violet:#b8a1e3;--red:#e98686;--cyan:#79c7d3;
  --mono:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono",monospace;
  --sans:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif
}
*{box-sizing:border-box}html{background:var(--bg)}
body{margin:0;background:var(--bg);color:var(--text);font-family:var(--sans);font-size:13px}
code,pre,table{font-family:var(--mono)}
.c{width:min(1600px,calc(100% - 32px));margin:0 auto;padding:24px 0 54px}
.page-head{display:flex;justify-content:space-between;align-items:flex-end;gap:24px;padding-bottom:17px;border-bottom:1px solid var(--line);margin-bottom:14px}
.page-title{margin:0;color:var(--strong);font:600 21px/1.2 var(--mono);letter-spacing:-.02em}
.page-subtitle{margin-top:5px;color:var(--muted);font:11px/1.4 var(--mono)}
.clock{text-align:right;color:var(--blue);font:600 15px/1.2 var(--mono);white-space:nowrap}
.clock-label{display:block;margin-bottom:4px;color:var(--dim);font:9px/1.2 var(--mono);letter-spacing:.08em;text-transform:uppercase}
.grid{display:grid;grid-template-columns:1fr;gap:12px;margin:12px 0}
.card{min-width:0;overflow:hidden;background:var(--panel);border:1px solid var(--line)}
.card-head{min-height:43px;padding:11px 13px;display:flex;align-items:baseline;justify-content:space-between;gap:12px;background:var(--panel3);border-bottom:1px solid var(--line)}
.card-title{margin:0;color:var(--strong);font:700 11px/1.2 var(--mono);letter-spacing:.07em;text-transform:uppercase}
.card-note{color:var(--muted);font:9px/1.2 var(--mono);white-space:nowrap}.card-body{padding:12px}
.label,.empty{color:var(--muted);font:10px/1.45 var(--mono)}
.f{margin-top:22px;color:#424a55;font:9px/1.3 var(--mono);text-align:center}
.sys-group+.sys-group{margin-top:14px}.sys-group-head{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:6px}
.sys-label{color:#aab3bf;font:700 10px/1.2 var(--mono);letter-spacing:.05em;text-transform:uppercase}.sys-count{color:var(--dim);font:9px var(--mono)}
.tags{display:flex;flex-wrap:wrap;gap:5px}.tag{display:inline-flex;align-items:center;min-height:24px;padding:3px 8px;background:#131820;border:1px solid #29313b;color:#aeb7c3;font:10px/1.2 var(--mono)}
.tag-tool{color:#9ec9ff}.tag-channel{color:#99d9a8}.tag-transform{color:#cbb9eb}
.sysinfo{overflow:visible;border:1px solid #252c35;background:#0e1116}
.memory-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:14px;padding:5px 8px;border-bottom:1px solid #222831;align-items:baseline}.memory-row:last-child{border-bottom:0}
.memory-name{min-width:0;color:#bcc4cf;font-size:9px;overflow-wrap:anywhere}.memory-size{color:var(--dim);font:9px var(--mono);white-space:nowrap}
.table-wrap{width:100%;overflow:visible}.reliability{width:100%;border-collapse:collapse;font-size:10px}.reliability th,.reliability td{padding:7px 9px;border-bottom:1px solid #252c35;white-space:nowrap}
.reliability th{background:#12171d;color:var(--muted);font-size:9px;letter-spacing:.05em;text-transform:uppercase;text-align:right}.reliability th:first-child,.reliability td:first-child{text-align:left}
.reliability td{text-align:right;color:#aeb7c2}.reliability tbody tr:hover td{background:#151a21}.tool-cell{color:#d1d7df!important;font-weight:600}.ok{color:var(--green)!important}.warn{color:var(--orange)!important}.fail{color:var(--red)!important}
.alarm-list{display:grid;gap:7px;overflow:visible}.alarm{border:1px solid #313640;background:#14171d}.alarm-head{display:flex;justify-content:space-between;gap:10px;padding:7px 9px;border-bottom:1px solid #252b33}.alarm-trigger{color:var(--orange);font:700 9px var(--mono)}.alarm-meta{color:var(--muted);font:8px var(--mono);text-align:right}.alarm-message{padding:8px 9px;color:#c9d0d9;white-space:pre-wrap;overflow-wrap:anywhere;font:10px/1.45 var(--mono)}
.tasks{overflow:visible}.source-pre{margin:0;color:#c9d1d9;white-space:pre-wrap;overflow-wrap:anywhere;font:10px/1.5 var(--mono)}
@media(max-width:980px){.c{width:min(100% - 18px,1600px);padding-top:12px}.page-head{align-items:flex-start;flex-direction:column;gap:8px}.clock{text-align:left}}
"""

def transform(messages, tools):
    now = _fmt_time()

    tasks_content = ""
    if _exists(TASKS_FILE):
        try:
            with open(TASKS_FILE) as f:
                tasks_content = f.read()
        except Exception:
            pass
    tasks_escaped = _escape_html(tasks_content)

    sys_tools, sys_channels, sys_transforms, mem_files, mem_total = get_system_info()

    mem_items = []
    for fname, fsize in mem_files:
        size_str = "{:.1f}KB".format(fsize / 1024) if fsize >= 1024 else "{}B".format(fsize)
        mem_items.append(
            '<div class="memory-row"><code class="memory-name">' + _escape_html(fname)
            + '</code><span class="memory-size">' + size_str + '</span></div>'
        )
    mem_html = "\n".join(mem_items) if mem_items else '<span class="empty">No memory files</span>'
    mem_total_str = "{:.1f}KB".format(mem_total / 1024) if mem_total >= 1024 else "{}B".format(mem_total)

    sys_section = (
        '<section class="card"><div class="card-head"><h2 class="card-title">System State</h2>'
        '<span class="card-note">runtime inventory</span></div><div class="card-body">'
        '<div class="sys-group"><div class="sys-group-head"><span class="sys-label">Tools</span><span class="sys-count">' + str(len(sys_tools)) + '</span></div><div class="tags">'
        + ''.join('<span class="tag tag-tool">' + _escape_html(str(x)) + '</span>' for x in sys_tools) + '</div></div>'
        '<div class="sys-group"><div class="sys-group-head"><span class="sys-label">Channels</span><span class="sys-count">' + str(len(sys_channels)) + '</span></div><div class="tags">'
        + ''.join('<span class="tag tag-channel">' + _escape_html(str(x)) + '</span>' for x in sys_channels) + '</div></div>'
        '<div class="sys-group"><div class="sys-group-head"><span class="sys-label">Transformations</span><span class="sys-count">' + str(len(sys_transforms)) + '</span></div><div class="tags">'
        + ''.join('<span class="tag tag-transform">' + _escape_html(str(x)) + '</span>' for x in sys_transforms) + '</div></div>'
        '<div class="sys-group"><div class="sys-group-head"><span class="sys-label">Memory Files</span><span class="sys-count">' + str(len(mem_files)) + ' · ' + mem_total_str + '</span></div>'
        '<div class="sysinfo">' + mem_html + '</div></div></div></section>'
    )

    tr_rows = get_tool_reliability()
    tr_items = []
    if tr_rows:
        tr_items.append(
            '<div class="table-wrap"><table class="reliability"><thead><tr>'
            '<th>Tool</th><th>f</th><th>c</th><th>Calls</th><th>OK</th><th>Fail</th>'
            '</tr></thead><tbody>'
        )
        for r in tr_rows:
            f_class = "ok" if r["f"] >= 0.9 else ("warn" if r["f"] >= 0.5 else "fail")
            tr_items.append(
                '<tr><td class="tool-cell">' + _escape_html(r["name"]) + '</td>'
                '<td class="' + f_class + '">' + str(r["f"]) + '</td>'
                '<td>' + str(r["c"]) + '</td><td>' + _fmt_int(r["calls"]) + '</td>'
                '<td class="ok">' + _fmt_int(r["successes"]) + '</td>'
                '<td class="fail">' + _fmt_int(r["failures"]) + '</td></tr>'
            )
        tr_items.append('</tbody></table></div>')
    else:
        tr_items.append('<span class="empty">No tool reliability data</span>')
    tr_html_str = "\n".join(tr_items)

    tr_section = (
        '<section class="card"><div class="card-head"><h2 class="card-title">Tool Reliability</h2><span class="card-note">' + str(len(tr_rows)) + ' tracked tools</span></div>'
        '<div class="card-body">' + tr_html_str + '</div></section>'
    )

    alarm_list = get_alarms()
    if alarm_list:
        alarm_items = []
        for a in alarm_list:
            alarm_items.append(
                '<div class="alarm"><div class="alarm-head"><span class="alarm-trigger">'
                + _escape_html(a["trigger"]) + '</span><span class="alarm-meta">'
                + _escape_html(a["remaining"]) + ' · ' + _escape_html(a["channel"]) + '</span></div>'
                '<div class="alarm-message">' + _escape_html(a["message"]) + '</div></div>'
            )
        alarm_html = "\n".join(alarm_items)
    else:
        alarm_html = '<span class="empty">No active alarms</span>'

    alarm_section = (
        '<section class="card"><div class="card-head"><h2 class="card-title">Alarms</h2><span class="card-note">' + str(len(alarm_list)) + ' active</span></div>'
        '<div class="card-body alarm-list">' + alarm_html + '</div></section>'
    )

    tasks_section = (
        '<section class="card"><div class="card-head"><h2 class="card-title">Current Tasks</h2><span class="card-note">memory/tasks/current_tasks.txt</span></div>'
        '<div class="card-body tasks"><pre class="source-pre">' + tasks_escaped + '</pre></div></section>'
    )

    html_doc = (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<script>setTimeout(function(){window.location.reload();},15000);</script>'
        '<style>' + CSS + '</style></head><body><main class="c">'
        '<header class="page-head"><div><h1 class="page-title">Eray Index <span style="color:#66707d;font-weight:400">/ Runtime Dashboard</span></h1>'
        '<div class="page-subtitle">Runtime inventory, reliability, alarms, and active work.</div></div>'
        '<div class="clock"><span class="clock-label">Local snapshot</span>' + _escape_html(now) + '</div></header>'
        + '<div class="grid">' + sys_section + tr_section + alarm_section + tasks_section + '</div>'
        + '<div class="f">Generated by Iter · transformations/dashboard_runtime.py · refresh 15s</div>'
        '</main></body></html>'
    )

    upload_html(html_doc)
    return messages, tools
