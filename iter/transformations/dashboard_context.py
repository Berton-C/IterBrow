import os, json, re



def _escape_html(value):
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#x27;")



def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False

DESCRIPTION = 'Dashboard Context Transformation'

ROOT = "."
MSGS_FILE = ROOT + "/recent_messages.txt"
OUTPUT_HTML = ROOT + "/dashboard_context.html"
CYCLE_STATE = ROOT + "/.dashboard_cycle_state.json"

N_CYCLES = 10  # how many recent cycles to show


# -----------------------------------------------------------------------------
# Context accounting
# -----------------------------------------------------------------------------

def _msg_len(m):
    return len(json.dumps(m, separators=(',', ':')))


def _msg_content_str(m):
    content = m.get('content', '')
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                parts.append(str(part.get('text', '')))
            else:
                parts.append(str(part))
        return '\n'.join(parts)
    else:
        return str(content)


def _tools_len(tools):
    if not tools:
        return 0
    total = 0
    for t in tools:
        total += len(json.dumps(t))
    return total


def _fmt_int(value):
    try:
        return "%d" % int(value)
    except Exception:
        return str(value)


def _json_pretty(value):
    try:
        return json.dumps(value)
    except Exception:
        return str(value)


# -----------------------------------------------------------------------------
# Tool schema rendering
# -----------------------------------------------------------------------------

def _normalize_tool(tool):
    """Normalize OpenAI-style tool definitions while remaining tolerant of variants."""
    if not isinstance(tool, dict):
        return {
            'name': str(tool),
            'description': '',
            'parameters': {},
            'type': type(tool).__name__,
            'raw': tool,
        }

    tool_type = str(tool.get('type', 'function'))
    fn = tool.get('function') if isinstance(tool.get('function'), dict) else tool

    name = fn.get('name', tool.get('name', '?'))
    description = fn.get('description', tool.get('description', '')) or ''
    parameters = fn.get('parameters', tool.get('parameters', {}))
    if not isinstance(parameters, dict):
        parameters = {}

    return {
        'name': str(name),
        'description': str(description),
        'parameters': parameters,
        'type': tool_type,
        'raw': tool,
    }


def _schema_type(schema):
    if not isinstance(schema, dict):
        return 'any'

    t = schema.get('type')
    if isinstance(t, list):
        t = ' | '.join(str(x) for x in t)
    elif not t:
        if 'enum' in schema:
            t = 'enum'
        elif 'properties' in schema:
            t = 'object'
        elif 'items' in schema:
            t = 'array'
        elif 'anyOf' in schema:
            t = 'anyOf'
        elif 'oneOf' in schema:
            t = 'oneOf'
        else:
            t = 'any'

    if t == 'array' and isinstance(schema.get('items'), dict):
        return 'array<' + _schema_type(schema['items']) + '>'

    return str(t)


def _schema_constraints(schema):
    if not isinstance(schema, dict):
        return ''

    bits = []
    if 'enum' in schema and isinstance(schema['enum'], list):
        enum_text = ', '.join(repr(v) for v in schema['enum'])
        if len(enum_text) > 180:
            enum_text = enum_text[:177] + '...'
        bits.append('enum: ' + enum_text)
    if 'default' in schema:
        bits.append('default: ' + repr(schema['default']))
    if 'minimum' in schema:
        bits.append('min: ' + str(schema['minimum']))
    if 'maximum' in schema:
        bits.append('max: ' + str(schema['maximum']))
    if 'minLength' in schema:
        bits.append('minLength: ' + str(schema['minLength']))
    if 'maxLength' in schema:
        bits.append('maxLength: ' + str(schema['maxLength']))

    return ' · '.join(bits)


def _parameter_rows(parameters):
    if not isinstance(parameters, dict):
        return '', 0, 0

    properties = parameters.get('properties', {})
    if not isinstance(properties, dict):
        properties = {}

    required = parameters.get('required', [])
    required = set(required if isinstance(required, list) else [])

    rows = []
    for name, schema in properties.items():
        schema = schema if isinstance(schema, dict) else {}
        req = name in required
        description = str(schema.get('description', '') or '')
        constraints = _schema_constraints(schema)

        rows.append('<div class="schema-param">')
        rows.append('<code class="schema-param-name">' + _escape_html(str(name)) + '</code>')
        rows.append('<code class="schema-param-type">' + _escape_html(_schema_type(schema)) + '</code>')
        rows.append('<span class="schema-param-mode ' + ('is-required' if req else '') + '">' + ('required' if req else 'optional') + '</span>')
        if description or constraints:
            detail = description
            if description and constraints:
                detail += ' · '
            detail += constraints
            rows.append('<span class="schema-param-detail">' + _escape_html(detail) + '</span>')
        rows.append('</div>')

    return ''.join(rows), len(properties), len(required)


def _tool_signature(name, parameters):
    properties = parameters.get('properties', {}) if isinstance(parameters, dict) else {}
    if not isinstance(properties, dict):
        properties = {}
    required = parameters.get('required', []) if isinstance(parameters, dict) else []
    required = set(required if isinstance(required, list) else [])

    pieces = ['<span class="sig-name">' + _escape_html(name) + '</span><span class="sig-punct">(</span>']
    for i, param_name in enumerate(properties.keys()):
        if i:
            pieces.append('<span class="sig-punct">, </span>')
        pieces.append('<span class="sig-param">' + _escape_html(str(param_name)) + '</span>')
        if param_name not in required:
            pieces.append('<span class="sig-optional">?</span>')
    pieces.append('<span class="sig-punct">)</span>')
    return ''.join(pieces)


def _tools_to_html(tools):
    if not tools:
        return '<div class="empty-state">No tools.</div>'

    normalized = [_normalize_tool(t) for t in tools]
    normalized.sort(key=lambda t: t['name'].lower())

    total_chars = sum(len(json.dumps(t['raw'])) for t in normalized)
    parts = [
        '<div class="tools-summary">'
        '<span><strong>' + _fmt_int(len(normalized)) + '</strong> available tools</span>'
        '<span><strong>' + _fmt_int(total_chars) + '</strong> schema chars</span>'
        '</div>',
        '<div class="tools-list">'
    ]

    for tool in normalized:
        name = tool['name']
        description = tool['description']
        parameters = tool['parameters']
        raw_chars = len(json.dumps(tool['raw']))
        param_html, param_count, required_count = _parameter_rows(parameters)

        parts.append('<details class="tool-definition">')
        parts.append('<summary>')
        parts.append('<span class="tool-disclosure" aria-hidden="true"></span>')
        parts.append('<div class="tool-summary-main">')
        parts.append('<code class="tool-signature">' + _tool_signature(name, parameters) + '</code>')
        if description:
            parts.append('<div class="tool-description">' + _escape_html(description) + '</div>')
        parts.append('<div class="tool-meta">')
        parts.append('<span>' + _escape_html(tool['type']) + '</span>')
        parts.append('<span>' + str(param_count) + (' arg' if param_count == 1 else ' args') + '</span>')
        if required_count != param_count:
            parts.append('<span>' + str(required_count) + ' required</span>')
        parts.append('<span>' + _fmt_int(raw_chars) + ' chars</span>')
        parts.append('</div>')
        parts.append('</div>')
        parts.append('</summary>')

        parts.append('<div class="tool-body">')
        if param_html:
            parts.append('<div class="schema-label">Arguments</div>')
            parts.append('<div class="schema-params">' + param_html + '</div>')
        else:
            parts.append('<div class="empty-note">No declared arguments.</div>')

        parts.append('<details class="raw-schema"><summary>Raw OpenAI schema</summary><pre>' + _escape_html(_json_pretty(tool['raw'])) + '</pre></details>')
        parts.append('</div>')
        parts.append('</details>')

    parts.append('</div>')
    return ''.join(parts)


# -----------------------------------------------------------------------------
# Message and tool-call rendering
# -----------------------------------------------------------------------------

def _render_call_value(value):
    if isinstance(value, (dict, list)):
        text = _json_pretty(value)
    else:
        text = str(value)
    return _escape_html(text)


def _split_step_prefix(text):
    """Split Iter's 'Step YYYY-MM-DD HH:MM:SS: ...' wrapper from actual content."""
    text = str(text)
    match = re.match(r'^Step (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}):\s?(.*)$', text, 0)
    if match:
        return match.group(1), match.group(2)
    return '', text


def _pretty_return_content(content):
    timestamp, body = _split_step_prefix(content)
    stripped = body.strip()
    if stripped:
        try:
            parsed = json.loads(stripped)
        except Exception:
            pretty = body
        else:
            pretty = _json_pretty(parsed)
    else:
        pretty = body
    return timestamp, pretty


def _tool_return_to_html(message):
    content = _msg_content_str(message)
    timestamp, pretty = _pretty_return_content(content)
    char_count = _msg_len(message)

    parts = ['<div class="tool-return">']
    parts.append('<div class="tool-return-head">')
    parts.append('<span class="tool-return-label">RETURN</span>')
    if timestamp:
        parts.append('<span class="tool-return-time">' + _escape_html(timestamp) + '</span>')
    parts.append('<span class="tool-return-chars">' + _fmt_int(char_count) + ' chars</span>')
    parts.append('</div>')
    parts.append('<pre class="tool-return-value">' + _escape_html(pretty) + '</pre>')
    parts.append('</div>')
    return ''.join(parts)


def _tool_result_index(messages):
    """Map tool_call_id -> queued (message index, message) return values."""
    lookup = {}
    for index, message in enumerate(messages):
        if str(message.get('role', '')).lower() != 'tool':
            continue
        call_id = str(message.get('tool_call_id', '') or '')
        if not call_id:
            continue
        lookup.setdefault(call_id, []).append((index, message))
    return lookup


def _tool_calls_to_html(m, tool_results=None, consumed=None):
    """Render assistant tool calls with their synchronous Iter return directly beneath."""
    tool_calls = m.get('tool_calls', [])
    if not tool_calls:
        return ''

    tool_results = tool_results or {}
    consumed = consumed if consumed is not None else set()
    html_parts = ['<div class="tool-calls">']

    for tc in tool_calls:
        if not isinstance(tc, dict):
            continue

        fn = tc.get('function', {}) if isinstance(tc.get('function'), dict) else {}
        tc_name = str(fn.get('name', '?'))
        tc_args_raw = fn.get('arguments', '{}')
        tc_id = str(tc.get('id', '') or '')

        parsed_ok = True
        try:
            tc_args = json.loads(tc_args_raw) if isinstance(tc_args_raw, str) else tc_args_raw
        except Exception:
            parsed_ok = False
            tc_args = tc_args_raw

        html_parts.append('<div class="tool-exchange">')
        html_parts.append('<div class="tool-call">')
        html_parts.append('<div class="tool-call-head">')
        html_parts.append('<span class="tool-call-label">CALL</span>')
        html_parts.append('<code class="tool-call-name">' + _escape_html(tc_name) + '</code>')
        if tc_id:
            html_parts.append('<code class="tool-call-id">' + _escape_html(tc_id) + '</code>')
        html_parts.append('</div>')

        if parsed_ok and isinstance(tc_args, dict):
            if tc_args:
                html_parts.append('<div class="call-args">')
                for key, value in tc_args.items():
                    html_parts.append('<div class="call-arg">')
                    html_parts.append('<code class="call-arg-key">' + _escape_html(str(key)) + '</code>')
                    html_parts.append('<pre class="call-arg-value">' + _render_call_value(value) + '</pre>')
                    html_parts.append('</div>')
                html_parts.append('</div>')
            else:
                html_parts.append('<div class="empty-note call-empty">No arguments.</div>')
        else:
            html_parts.append('<pre class="tool-call-raw">' + _escape_html(str(tc_args_raw)) + '</pre>')

        html_parts.append('</div>')

        matched = None
        if tc_id:
            queue = tool_results.get(tc_id, [])
            while queue:
                result_index, result_message = queue.pop(0)
                if result_index not in consumed:
                    consumed.add(result_index)
                    matched = result_message
                    break

        if matched is not None:
            html_parts.append(_tool_return_to_html(matched))
        else:
            html_parts.append('<div class="tool-return pending-return"><span class="tool-return-label">RETURN</span><span>No matching return in current context.</span></div>')

        html_parts.append('</div>')

    html_parts.append('</div>')
    return ''.join(html_parts)


def _msg_to_html(messages):
    if not messages:
        return '<div class="empty-state">No messages this cycle.</div>'

    html_parts = ['<div class="messages-list">']
    role_labels = {
        'user': 'USER',
        'assistant': 'ASSISTANT',
        'tool': 'TOOL RETURN',
        'system': 'SYSTEM',
        'developer': 'DEVELOPER',
    }
    tool_results = _tool_result_index(messages)
    consumed_tool_messages = set()

    for i, m in enumerate(messages):
        role_raw = str(m.get('role', 'unknown')).lower()

        # In Iter these are synchronous return values for prior tool_calls. If matched,
        # they are rendered inside the originating call instead of duplicated here.
        if role_raw == 'tool' and i in consumed_tool_messages:
            continue

        role = _escape_html(role_raw)
        role_label = role_labels.get(role_raw, role_raw.upper())
        content_raw = _msg_content_str(m)
        char_count = _msg_len(m)
        reasoning_fields = []
        if role_raw != "user":
            for key in ('reasoning', 'reasoning_content'):
                value = m.get(key)
                if value:
                    reasoning_fields.append((key, value if isinstance(value, str) else _json_pretty(value)))
                    break

        html_parts.append('<article class="message role-' + role + '">')
        html_parts.append('<div class="message-meta">')
        html_parts.append('<span class="message-index">' + "%02d" % (i + 1) + '</span>')
        html_parts.append('<span class="message-role">' + _escape_html(role_label) + '</span>')
        html_parts.append('<span class="message-chars">' + _fmt_int(char_count) + ' chars</span>')
        if m.get('tool_call_id'):
            html_parts.append('<code class="message-tool-link">↳ ' + _escape_html(str(m.get('tool_call_id'))) + '</code>')
        html_parts.append('</div>')

        html_parts.append('<div class="message-body">')
        if content_raw.strip():
            timestamp, body = _split_step_prefix(content_raw)
            if timestamp:
                html_parts.append('<div class="message-step">' + _escape_html(timestamp) + '</div>')
            if body.strip():
                html_parts.append('<div class="message-content">' + _escape_html(body) + '</div>')
        for key, value in reasoning_fields:
            html_parts.append('<div class="message-reasoning">')
            html_parts.append('<div class="message-reasoning-label">' + _escape_html(key.upper()) + '</div>')
            html_parts.append('<pre class="message-reasoning-content">' + _escape_html(value) + '</pre>')
            html_parts.append('</div>')
        tc_html = _tool_calls_to_html(m, tool_results, consumed_tool_messages)
        if tc_html:
            html_parts.append(tc_html)
        html_parts.append('</div>')
        html_parts.append('</article>')

    html_parts.append('</div>')
    return ''.join(html_parts)


# -----------------------------------------------------------------------------
# Styling
# -----------------------------------------------------------------------------

CSS = r'''
:root {
    color-scheme: dark;
    --bg: #0b0d10;
    --panel: #111419;
    --panel-2: #151920;
    --panel-3: #191e26;
    --line: #2a3039;
    --line-strong: #38414d;
    --text: #d8dee9;
    --text-strong: #eef2f7;
    --muted: #808a98;
    --dim: #5f6977;
    --blue: #6ea8fe;
    --green: #7ccf91;
    --orange: #e7a86e;
    --violet: #b8a1e3;
    --red: #e98686;
    --cyan: #79c7d3;
    --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
    --sans: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

* { box-sizing: border-box; }
html { background: var(--bg); }
body {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: var(--sans);
    font-size: 13px;
}
code, pre, table { font-family: var(--mono); }

.dashboard {
    width: min(1500px, calc(100% - 32px));
    margin: 0 auto;
    padding: 24px 0 60px;
}

header.page-head {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 24px;
    padding: 0 0 18px;
    margin-bottom: 18px;
    border-bottom: 1px solid var(--line);
}

.page-title {
    margin: 0;
    color: var(--text-strong);
    font: 600 21px/1.2 var(--mono);
    letter-spacing: -0.02em;
}
.page-subtitle {
    margin-top: 5px;
    color: var(--muted);
    font: 11px/1.4 var(--mono);
}
.updated {
    color: var(--muted);
    font: 11px/1.4 var(--mono);
    white-space: nowrap;
}

.section {
    margin-top: 18px;
    border: 1px solid var(--line);
    background: var(--panel);
}
.section-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 16px;
    min-height: 44px;
    padding: 12px 14px;
    border-bottom: 1px solid var(--line);
    background: #0f1217;
}
.section-title {
    margin: 0;
    color: var(--text-strong);
    font: 600 12px/1.2 var(--mono);
    letter-spacing: .06em;
    text-transform: uppercase;
}
.section-note {
    color: var(--muted);
    font: 10px/1.2 var(--mono);
}
.section-body { padding: 14px; }

/* cycle stats */
.stats-wrap { overflow-x: auto; }
.stats-table {
    width: 100%;
    border-collapse: collapse;
    min-width: 760px;
    font-size: 12px;
}
.stats-table th,
.stats-table td {
    border-bottom: 1px solid var(--line);
    padding: 9px 12px;
    white-space: nowrap;
}
.stats-table th {
    color: var(--muted);
    font-weight: 600;
    font-size: 10px;
    letter-spacing: .04em;
    text-transform: uppercase;
    text-align: right;
    background: var(--panel-2);
}
.stats-table th:first-child,
.stats-table td:first-child { text-align: left; }
.stats-table td {
    text-align: right;
    color: #c7ced8;
}
.stats-table tbody tr:hover td { background: #151a21; }
.stats-table .num-msg { color: var(--orange); }
.stats-table .num-tool { color: var(--violet); }
.stats-table .num-combined { color: var(--blue); }
.stats-table .num-time { color: var(--green); }
.stats-table tr.summary-average td {
    color: var(--blue);
    font-weight: 700;
    background: #121821;
}
.stats-table tr.summary-total td {
    color: var(--green);
    font-weight: 700;
    background: #111913;
    border-bottom: 0;
}
.stats-table tbody tr:last-child td { border-bottom: 0; }

/* messages */
.messages-list { display: grid; gap: 8px; }
.message {
    display: grid;
    grid-template-columns: 145px minmax(0, 1fr);
    border: 1px solid var(--line);
    background: var(--panel-2);
}
.message-meta {
    padding: 10px 11px;
    border-right: 1px solid var(--line);
    background: #0f1318;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
    font-family: var(--mono);
}
.message-index { color: var(--dim); font-size: 10px; }
.message-role { font-weight: 700; font-size: 11px; letter-spacing: .05em; }
.message-chars { color: var(--muted); font-size: 10px; }
.message-tool-link {
    margin-top: 3px;
    color: var(--green);
    font-size: 9px;
    overflow-wrap: anywhere;
}
.message-body { min-width: 0; padding: 11px 13px; }
.message-content {
    color: var(--text);
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    font: 12px/1.55 var(--mono);
}
.role-user .message-role { color: var(--orange); }
.role-assistant .message-role { color: var(--blue); }
.role-tool .message-role { color: var(--green); }
.role-system .message-role { color: var(--muted); }
.role-developer .message-role { color: var(--violet); }
.role-user { border-left: 2px solid #8f6845; }
.role-assistant { border-left: 2px solid #4c76aa; }
.role-tool { border-left: 2px solid #4f825d; }
.role-developer { border-left: 2px solid #786798; }

/* synchronous tool call -> return exchanges */
.tool-calls {
    margin-top: 10px;
    display: grid;
    gap: 10px;
}
.tool-exchange {
    border: 1px solid #353b49;
    background: #0e1117;
    box-shadow: 0 1px 0 rgba(255,255,255,.02) inset;
}
.tool-call { background: #11151c; }
.tool-call-head,
.tool-return-head {
    min-height: 32px;
    display: flex;
    align-items: center;
    gap: 9px;
    padding: 7px 10px;
    font-family: var(--mono);
}
.tool-call-head {
    border-bottom: 1px solid #29303b;
    background: #171b24;
}
.tool-call-label,
.tool-return-label {
    min-width: 46px;
    font-size: 9px;
    font-weight: 800;
    letter-spacing: .08em;
}
.tool-call-label { color: var(--violet); }
.tool-call-name { color: #d6c5f3; font-weight: 700; font-size: 12px; }
.tool-call-id {
    color: var(--dim);
    font-size: 9px;
    overflow-wrap: anywhere;
    margin-left: auto;
}
.call-args { display: grid; }
.call-arg {
    display: grid;
    grid-template-columns: minmax(130px, 18%) minmax(0, 1fr);
    border-bottom: 1px solid #252b36;
}
.call-arg:last-child { border-bottom: 0; }
.call-arg-key {
    padding: 8px 10px;
    color: var(--cyan);
    background: #0f1319;
    border-right: 1px solid #252b36;
    overflow-wrap: anywhere;
}
.call-arg-value,
.tool-call-raw {
    margin: 0;
    padding: 8px 10px;
    color: #c4ccd7;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    font-size: 11px;
    line-height: 1.5;
}
.call-empty { padding: 8px 10px; }
.tool-return {
    border-top: 1px solid #35433a;
    background: #101713;
}
.tool-return-head {
    border-bottom: 1px solid #29362d;
    background: #141d17;
}
.tool-return-label { color: var(--green); }
.tool-return-time,
.tool-return-chars {
    color: #708077;
    font-size: 9px;
}
.tool-return-chars { margin-left: auto; }
.tool-return-value {
    margin: 0;
    padding: 10px 12px;
    color: #c1d2c5;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    font: 11px/1.55 var(--mono);
    max-height: 520px;
    overflow: auto;
}
.pending-return {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 10px;
    color: var(--muted);
    font: 10px/1.4 var(--mono);
}
.message-step {
    margin-bottom: 5px;
    color: var(--dim);
    font: 9px/1.2 var(--mono);
}

/* available tool definitions */
.tools-summary {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 18px;
    color: var(--muted);
    font: 10px/1.4 var(--mono);
    margin-bottom: 10px;
}
.tools-summary strong { color: var(--text); font-weight: 600; }
.tools-list { display: grid; gap: 7px; }
.tool-definition {
    border: 1px solid var(--line);
    background: #11151b;
}
.tool-definition > summary {
    list-style: none;
    cursor: pointer;
    display: grid;
    grid-template-columns: 18px minmax(0, 1fr);
    gap: 8px;
    align-items: start;
    padding: 11px 12px;
    user-select: text;
}
.tool-definition > summary::-webkit-details-marker { display: none; }
.tool-definition > summary:hover { background: #151a21; }
.tool-definition[open] > summary {
    background: #151a21;
    border-bottom: 1px solid var(--line);
}
.tool-disclosure {
    position: relative;
    width: 14px;
    height: 18px;
}
.tool-disclosure::before {
    content: '›';
    position: absolute;
    top: 0;
    left: 1px;
    color: #687382;
    font: 17px/18px var(--mono);
    transition: transform .12s ease;
    transform-origin: 45% 50%;
}
.tool-definition[open] .tool-disclosure::before { transform: rotate(90deg); }
.tool-summary-main { min-width: 0; }
.tool-signature {
    display: block;
    color: var(--text-strong);
    font-size: 12px;
    line-height: 1.45;
    white-space: normal;
    overflow-wrap: anywhere;
}
.sig-name { color: var(--cyan); font-weight: 750; }
.sig-param { color: #c7b6e5; }
.sig-punct { color: #65707e; }
.sig-optional { color: var(--dim); }
.tool-description {
    margin-top: 4px;
    max-width: 1100px;
    color: #98a2af;
    font: 11px/1.45 var(--mono);
    white-space: normal;
    overflow-wrap: anywhere;
}
.tool-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 5px 12px;
    margin-top: 6px;
    color: #626d7a;
    font: 9px/1.3 var(--mono);
}
.tool-meta span + span::before {
    content: '·';
    margin-right: 12px;
    color: #414a55;
}
.tool-body {
    padding: 10px 12px 12px 38px;
    background: #0e1116;
}
.schema-label {
    margin-bottom: 6px;
    color: #697582;
    font: 700 9px/1.2 var(--mono);
    letter-spacing: .07em;
    text-transform: uppercase;
}
.schema-params {
    border: 1px solid #252c35;
    background: #10141a;
}
.schema-param {
    display: grid;
    grid-template-columns: minmax(130px, .7fr) 100px 82px minmax(0, 2fr);
    align-items: baseline;
    min-height: 31px;
    border-bottom: 1px solid #252c35;
}
.schema-param:last-child { border-bottom: 0; }
.schema-param > * { padding: 7px 9px; }
.schema-param-name { color: var(--cyan); }
.schema-param-type { color: var(--violet); }
.schema-param-mode { color: var(--dim); font: 9px var(--mono); }
.schema-param-mode.is-required { color: var(--orange); }
.schema-param-detail {
    color: #89939f;
    font: 10px/1.4 var(--mono);
}
.raw-schema { margin-top: 9px; }
.raw-schema summary {
    cursor: pointer;
    color: #66717e;
    font: 9px var(--mono);
}
.raw-schema pre {
    margin: 7px 0 0;
    padding: 10px;
    max-height: 520px;
    overflow: auto;
    border: 1px solid var(--line);
    background: #090c10;
    color: #909aa6;
    font-size: 10px;
    line-height: 1.45;
}

.empty-state, .empty-note {
    color: var(--muted);
    font: 11px/1.5 var(--mono);
}
.fallback-pre {
    margin: 0;
    padding: 12px;
    white-space: pre-wrap;
    border: 1px solid var(--line);
    background: #0e1115;
    color: #b8c0ca;
    font: 11px/1.5 var(--mono);
}

@media (max-width: 900px) {
    .dashboard { width: min(100% - 18px, 1500px); padding-top: 12px; }
    header.page-head { align-items: flex-start; flex-direction: column; gap: 8px; }
    .message { grid-template-columns: 1fr; }
    .message-meta { border-right: 0; border-bottom: 1px solid var(--line); flex-direction: row; align-items: center; }
    .message-tool-link { margin-top: 0; margin-left: auto; }
    .tool-definition > summary { grid-template-columns: 1fr; }
    .tool-meta { flex-wrap: wrap; }
    .tool-heading { flex-direction: column; gap: 4px; }
    .tool-description-inline { white-space: normal; }
    .call-arg { grid-template-columns: 1fr; }
    .call-arg-key { border-right: 0; border-bottom: 1px solid #252b36; }
    .schema-param { grid-template-columns: 1fr 90px 80px; }
    .schema-param-detail { grid-column: 1 / -1; padding-top: 0; }
    .tool-body { padding-left: 12px; }
}

.message-reasoning {
    margin-top: 10px;
    border: 1px solid #35303f;
    background: #121017;
}
.message-reasoning-label {
    padding: 6px 9px;
    border-bottom: 1px solid #35303f;
    color: var(--violet);
    font: 700 9px/1.2 var(--mono);
    letter-spacing: .07em;
}
.message-reasoning-content {
    margin: 0;
    padding: 9px 10px;
    color: #b9aec9;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    font: 11px/1.5 var(--mono);
}
'''


def transform(messages, tools):
    try:
        import time as _time
        now = _time.localtime()
        now_ts = _time.time()
        now_str = '%d-%02d-%02d %02d:%02d:%02d UTC' % (now[0], now[1], now[2], now[3], now[4], now[5])

        total_msg_chars = 0
        if messages:
            for m in messages:
                total_msg_chars += _msg_len(m)

        total_tool_chars = _tools_len(tools)
        total_combined = total_msg_chars + total_tool_chars

        # ---- Load previous cycle state ----
        cycles = []
        if _exists(CYCLE_STATE):
            try:
                with open(CYCLE_STATE, 'r') as f:
                    cycles = json.loads(f.read())
            except Exception:
                cycles = []

        entry = {
            'ts': now_ts,
            'str': now_str,
            'msg_chars': total_msg_chars,
            'tool_chars': total_tool_chars,
            'combined_chars': total_combined,
        }

        cycles.append(entry)

        if len(cycles) > N_CYCLES + 1:
            cycles = cycles[-(N_CYCLES + 1):]

        with open(CYCLE_STATE, 'w') as f:
            f.write(json.dumps(cycles))

        # ---- Build cycle rows ----
        cycle_rows = []
        for i in range(1, len(cycles)):
            prev = cycles[i - 1]
            curr = cycles[i]
            dur = curr['ts'] - prev['ts']
            cycle_rows.append({
                'str': curr['str'],
                'msg_chars': curr.get('msg_chars', 0),
                'tool_chars': curr.get('tool_chars', 0),
                'combined_chars': curr.get('combined_chars', 0),
                'duration_sec': dur,
            })

        # ---- Compute stats ----
        if cycle_rows:
            avg_msg = sum(r['msg_chars'] for r in cycle_rows) / len(cycle_rows)
            avg_tool = sum(r['tool_chars'] for r in cycle_rows) / len(cycle_rows)
            avg_comb = sum(r['combined_chars'] for r in cycle_rows) / len(cycle_rows)
            avg_dur = sum(r['duration_sec'] for r in cycle_rows) / len(cycle_rows)
            sum_msg = sum(r['msg_chars'] for r in cycle_rows)
            sum_tool = sum(r['tool_chars'] for r in cycle_rows)
            sum_comb = sum(r['combined_chars'] for r in cycle_rows)
            sum_dur = sum(r['duration_sec'] for r in cycle_rows)
        else:
            avg_msg = avg_tool = avg_comb = avg_dur = 0
            sum_msg = sum_tool = sum_comb = sum_dur = 0

        # ---- Build stats table (same information as original) ----
        stats_html = '<div class="stats-wrap"><table class="stats-table">'
        stats_html += '<thead><tr>'
        stats_html += '<th>Timestamp</th>'
        stats_html += '<th>Msg Chars</th>'
        stats_html += '<th>Tool Chars</th>'
        stats_html += '<th>Combined</th>'
        stats_html += '<th>Cycle Time (s)</th>'
        stats_html += '</tr></thead><tbody>'

        for r in cycle_rows:
            stats_html += '<tr>'
            stats_html += '<td>' + _escape_html(r['str']) + '</td>'
            stats_html += '<td class="num-msg">' + _fmt_int(r['msg_chars']) + '</td>'
            stats_html += '<td class="num-tool">' + _fmt_int(r['tool_chars']) + '</td>'
            stats_html += '<td class="num-combined">' + _fmt_int(r['combined_chars']) + '</td>'
            stats_html += '<td class="num-time">' + "%.1f" % r['duration_sec'] + '</td>'
            stats_html += '</tr>'

        if cycle_rows:
            stats_html += '<tr class="summary-average">'
            stats_html += '<td>Average</td>'
            stats_html += '<td>' + "%.0f" % avg_msg + '</td>'
            stats_html += '<td>' + "%.0f" % avg_tool + '</td>'
            stats_html += '<td>' + "%.0f" % avg_comb + '</td>'
            stats_html += '<td>' + "%.1f" % avg_dur + '</td>'
            stats_html += '</tr>'

            stats_html += '<tr class="summary-total">'
            stats_html += '<td>Total</td>'
            stats_html += '<td>' + str(sum_msg) + '</td>'
            stats_html += '<td>' + str(sum_tool) + '</td>'
            stats_html += '<td>' + str(sum_comb) + '</td>'
            stats_html += '<td>' + "%.1f" % sum_dur + '</td>'
            stats_html += '</tr>'

        stats_html += '</tbody></table></div>'

        # ---- Build messages section ----
        if messages:
            msg_html = _msg_to_html(messages)
        elif _exists(MSGS_FILE):
            with open(MSGS_FILE, 'r') as f:
                msg_html = '<pre class="fallback-pre">' + _escape_html(f.read()) + '</pre>'
        else:
            msg_html = '<div class="empty-state">No messages available.</div>'

        # ---- Build tools section ----
        tools_html = _tools_to_html(tools)

        # ---- Build full HTML ----
        html_out = '<!doctype html><html><head><meta charset="utf-8">'
        html_out += '<meta name="viewport" content="width=device-width,initial-scale=1">'
        html_out += '<title>Dashboard Context</title><script>setTimeout(function(){window.location.reload();},15000);</script><style>' + CSS + '</style></head><body>'
        html_out += '<main class="dashboard">'
        html_out += '<header class="page-head">'
        html_out += '<div><h1 class="page-title">Eray Index <span style="color:#66707d;font-weight:400">/ Context Dashboard</span></h1>'
        html_out += '<div class="page-subtitle">Raw context visibility for the LLM in the current agent cycle.</div></div>'
        html_out += '<div class="updated">Last updated: ' + _escape_html(now_str) + '</div>'
        html_out += '</header>'

        html_out += '<section class="section">'
        html_out += '<div class="section-head"><h2 class="section-title">Cycle Stats</h2><span class="section-note">last ' + str(len(cycle_rows)) + ' cycles</span></div>'
        html_out += '<div class="section-body">' + stats_html + '</div></section>'

        html_out += '<section class="section">'
        html_out += '<div class="section-head"><h2 class="section-title">Messages</h2><span class="section-note">' + str(len(messages or [])) + ' entries · ' + _fmt_int(total_msg_chars) + ' chars</span></div>'
        html_out += '<div class="section-body">' + msg_html + '</div></section>'

        html_out += '<section class="section">'
        html_out += '<div class="section-head"><h2 class="section-title">Available Tools</h2><span class="section-note">' + str(len(tools or [])) + ' definitions · ' + _fmt_int(total_tool_chars) + ' chars</span></div>'
        html_out += '<div class="section-body">' + tools_html + '</div></section>'

        html_out += '</main></body></html>'

        with open(OUTPUT_HTML, 'w') as f:
            f.write(html_out)

        scp_cmd = ''


    except Exception as e:
        import sys as _sys
        try:
            with open(OUTPUT_HTML + ".err", "w") as _ef:
                _ef.write(str(e) + chr(10))
                _ef.write(str(type(e)) + chr(10))
                _ef.write(str(_sys.exc_info()) + chr(10))
        except:
            pass

    return messages, tools


