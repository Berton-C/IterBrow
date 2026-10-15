import os
import time

import json



def _escape_html(value):
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#x27;")



def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False

DESCRIPTION = "Atom-space dashboard: knowledge-base counts and graph from the AtomSpace authority, plus the unloaded space.metta projection"

ROOT = "."
SPACE_FILE = ROOT + "/transformations/.runtime/space.metta"


def upload_html(html_doc):
    try:
        with open(ROOT + "/dashboard_atomspace.html", "w") as f:
            f.write(html_doc)
    except Exception:
        pass


KB_KEYS = ("statements", "terms_known", "terms_provisional", "evidence", "derived", "nace_beliefs",
           "soul_choices", "soul_last")
_SOUL_CHOICE = None


def soul_choice_counts(atoms):
    """(count, last {kind, pick, at} or None) from state:soul_choice:* atoms (M6)."""
    import re
    global _SOUL_CHOICE
    if _SOUL_CHOICE is None:
        _SOUL_CHOICE = re.compile(r'\(soul-choice "(?:[^"\\]|\\.)*" "((?:[^"\\]|\\.)*)" "(?:[^"\\]|\\.)*" "((?:[^"\\]|\\.)*)" (\d+)\)')
    last = None
    count = 0
    for key, atom in atoms.items():
        if not key.startswith("state:soul_choice:"):
            continue
        count += 1
        match = _SOUL_CHOICE.match(atom)
        if match and (last is None or int(match.group(3)) > last["at"]):
            last = {"kind": match.group(1), "pick": match.group(2), "at": int(match.group(3))}
    return count, last
CACHE_FILE = ROOT + "/transformations/.runtime/dashboard_kb_cache.json"


def authority_counts(read_atoms, derive):
    """What the AtomSpace authority holds, counted from its atoms (never from space.metta text).

    read_atoms(prefix) -> {key: atom}; derive() -> list of derivations (depth 1).
    Any failure to read the authority yields status "authority unreachable" and
    no numbers at all, so the page never shows stale or invented counts.
    """
    try:
        kb = read_atoms("state:kb_")
        nace = read_atoms("state:nace_belief:")
        soul = read_atoms("state:soul_choice:")
    except Exception:
        return dict({"status": "authority unreachable", "loaded": False}, **{key: None for key in KB_KEYS})
    from iterbrow_runtime.kb_terms import parse_term_atom
    known = provisional = 0
    for key, atom in kb.items():
        if key.startswith("state:kb_term:"):
            try:
                status = parse_term_atom(atom)["status"]
            except (ValueError, IndexError):
                continue
            if status == "known":
                known += 1
            else:
                provisional += 1
    try:
        derived = len(derive())
    except Exception:
        derived = None
    return {
        "status": "ok", "loaded": True,
        "statements": sum(1 for key in kb if key.startswith("state:kb_statement:")),
        "terms_known": known, "terms_provisional": provisional,
        "evidence": sum(1 for key in kb if key.startswith("state:kb_evidence:")),
        "derived": derived,
        "nace_beliefs": len(nace),
        "soul_choices": soul_choice_counts(soul)[0],
        "soul_last": soul_choice_counts(soul)[1],
    }


def build_kb_graph(kb_atoms, derived):
    """Graph of what is real: stored statements, derived statements, and the registry
    terms they mention (an edge only for a term in the statement's canonical term list)."""
    from iterbrow_runtime import kb_terms
    registry = kb_terms.Registry({k: v for k, v in kb_atoms.items() if k.startswith(kb_terms.TERM_PREFIX)})
    nodes, links, term_ids = [], [], {}

    def term_node(term):
        if term not in term_ids:
            term_ids[term] = "term:" + term
            nodes.append({"id": term_ids[term], "kind": "term", "label": term,
                          "status": registry.status(term) or kb_terms.PROVISIONAL})
        return term_ids[term]

    def statement_node(node_id, kind, statement, stv, extra=None):
        node = {"id": node_id, "kind": kind, "label": statement, "stv": list(stv)}
        node.update(extra or {})
        nodes.append(node)
        for term in kb_terms.statement_terms(statement):
            links.append({"source": node_id, "target": term_node(term), "type": "mentions", "term": term})

    for key in sorted(kb_atoms):
        if key.startswith(kb_terms.STATEMENT_PREFIX):
            try:
                statement, stv = kb_terms.parse_statement_atom(kb_atoms[key])
            except ValueError:
                continue
            statement_node("stmt:" + key[len(kb_terms.STATEMENT_PREFIX):], "statement", statement, stv)
    for index, item in enumerate(derived or []):
        statement_node("derived:%d" % index, "derived", item["statement"], item["stv"],
                       {"premises": item["premises"]})
    return {"nodes": nodes, "links": links}


def _read_authority():
    """(read_atoms, derive, commit) against the live service, or raise."""
    import sys
    iter_dir = os.environ.get("ITER_DIR") or os.getcwd()
    if iter_dir not in sys.path:
        sys.path.insert(0, iter_dir)
    from iterbrow_runtime.cognitive_events import _call_atomspace
    from iterbrow_runtime import kb_inference
    state = {}

    def read_atoms(prefix):
        snapshot = _call_atomspace("read_atoms", timeout=10, prefix=prefix)
        state["commit"] = snapshot.get("commit")
        return snapshot["atoms"]

    def derive():
        # Conclusions depend only on the kb statements: key the cache by their
        # digest, so commits that touch nothing else (NACE writes every cycle)
        # never pay for re-deriving.
        if "derived" in state:
            return state["derived"]
        import hashlib
        statements = _call_atomspace("read_atoms", timeout=10, prefix="state:kb_statement:")["atoms"]
        digest = hashlib.sha256(json.dumps(statements, sort_keys=True).encode()).hexdigest()
        try:
            with open(CACHE_FILE) as handle:
                cached = json.load(handle)
            if cached.get("statements_digest") == digest:
                state["derived"] = cached["derived"]
                return state["derived"]
        except Exception:
            pass
        state["derived"] = [dict(item) for item in kb_inference.derive(kb_inference.service_query, depth=1)]
        try:
            os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
            with open(CACHE_FILE + ".tmp", "w") as handle:
                json.dump({"statements_digest": digest, "computed_at": time.time(), "derived": state["derived"]}, handle)
            os.replace(CACHE_FILE + ".tmp", CACHE_FILE)
        except Exception:
            pass
        return state["derived"]

    return read_atoms, derive, state


def _authority_view():
    """(counts, graph, commit) for the page; unreachable authority -> no numbers, empty graph."""
    try:
        read_atoms, derive, state = _read_authority()
    except Exception:
        def read_atoms(_prefix):
            raise ConnectionError("authority unreachable")
        derive, state = (lambda: []), {}
    counts = authority_counts(read_atoms, derive)
    graph = {"nodes": [], "links": []}
    if counts["loaded"]:
        try:
            graph = build_kb_graph(read_atoms("state:kb_"), derive())
        except Exception:
            pass
    return counts, graph, state.get("commit")


def _soul_section(counts):
    """Soul card (M6): who is here, features on, choices recorded. Numbers from atoms."""
    try:
        import sys
        iter_dir = os.environ.get("ITER_DIR") or os.getcwd()
        if iter_dir not in sys.path:
            sys.path.insert(0, iter_dir)
        from iterbrow_runtime import soul_settings
        person = soul_settings.person()
        features = soul_settings.enabled_features()
    except Exception:
        person, features = "unknown", []
    if not counts.get("loaded"):
        body = '<span class="label">authority unreachable</span>'
    elif not counts.get("soul_choices"):
        body = '<span class="label">no Soul activity yet</span>'
    else:
        last = counts.get("soul_last") or {}
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(last.get("at", 0) / 1000.0)) if last else ""
        body = ('<span class="graph-chip">choices <strong>%s</strong></span>'
                '<span class="graph-chip">last <strong>%s → %s</strong> %s</span>'
                % (counts["soul_choices"], _escape_html(last.get("kind", "")), _escape_html(last.get("pick", "")),
                   _escape_html(when)))
    note = "%s · features on: %s" % (person, ", ".join(features) if features else "none")
    return ('<section class="card"><div class="card-head"><h2 class="card-title">Soul</h2>'
            '<span class="card-note">' + _escape_html(note) + '</span></div>'
            '<div class="card-body" style="display:flex;flex-wrap:wrap;gap:6px">' + body + '</div></section>')


def _comment_json(value):
    """JSON safe inside an HTML comment (no '--' sequences)."""
    return json.dumps(value, ensure_ascii=True).replace("--", "-\\u002d")


def transform(messages, tools):
    t = time.localtime(); now = "%04d-%02d-%02d %02d:%02d:%02d" % (t[0], t[1], t[2], t[3], t[4], t[5])

    space_content = ""
    if _exists(SPACE_FILE):
        with open(SPACE_FILE) as source:
            space_content = source.read()
    space_escaped = _escape_html(space_content)

    css = r'''
:root{
  color-scheme:dark;
  --bg:#0b0d10;--panel:#111419;--panel3:#0f1217;
  --line:#2a3039;--text:#d8dee9;--strong:#eef2f7;
  --muted:#808a98;--dim:#5f6977;--blue:#6ea8fe;--green:#7ccf91;
  --orange:#e7a86e;--violet:#b8a1e3;--cyan:#79c7d3;
  --mono:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono",monospace;
  --sans:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif
}
*{box-sizing:border-box}html{background:var(--bg)}
body{margin:0;background:var(--bg);color:var(--text);font-family:var(--sans);font-size:13px}
code,pre{font-family:var(--mono)}
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
.space{max-height:400px;overflow:auto}.source-pre{margin:0;color:#c9d1d9;white-space:pre-wrap;overflow-wrap:anywhere;font:10px/1.5 var(--mono)}
.graph-shell{padding:0}
.graph-frame{
  width:100%;height:600px;position:relative;overflow:hidden;background-color:#090c10;
  background-image:
    radial-gradient(circle at 50% 48%,rgba(110,168,254,.055),transparent 36%),
    linear-gradient(rgba(255,255,255,.018) 1px,transparent 1px),
    linear-gradient(90deg,rgba(255,255,255,.018) 1px,transparent 1px);
  background-size:auto,32px 32px,32px 32px;background-position:center
}
.graph-frame canvas{outline:none}
.graph-loading{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);color:var(--muted);font:10px var(--mono);letter-spacing:.03em}
.graph-hud{position:absolute;z-index:3;display:flex;gap:6px;pointer-events:none}
.graph-hud-top{top:10px;left:10px}
.graph-chip{display:inline-flex;align-items:baseline;gap:5px;padding:5px 7px;background:rgba(11,14,18,.86);border:1px solid rgba(56,65,77,.86);backdrop-filter:blur(8px);font:8px/1 var(--mono);color:var(--muted)}
.graph-chip strong{color:#c7d0dc;font-size:9px;font-weight:700}
.graph-actions{position:absolute;z-index:4;top:10px;right:10px;display:flex;gap:6px}
.graph-button{appearance:none;border:1px solid rgba(56,65,77,.92);background:rgba(11,14,18,.88);color:#9ca7b5;padding:6px 8px;font:800 8px/1 var(--mono);letter-spacing:.07em;cursor:pointer}
.graph-button:hover{color:#d7dee8;border-color:#596577;background:#12171d}.graph-frame{touch-action:none}
.graph-legend{position:absolute;z-index:3;left:10px;bottom:10px;max-width:min(70%,760px);display:flex;flex-wrap:wrap;gap:5px;pointer-events:none}
.graph-legend-item{display:inline-flex;align-items:center;gap:5px;padding:4px 6px;background:rgba(11,14,18,.84);border:1px solid rgba(45,53,64,.82);font:8px/1 var(--mono);color:#8792a0;backdrop-filter:blur(7px)}
.graph-swatch{width:13px;height:1px;display:inline-block}
.graph-inspector{position:absolute;z-index:3;right:10px;bottom:10px;width:min(310px,42%);min-height:45px;padding:8px 10px;background:rgba(11,14,18,.88);border:1px solid rgba(56,65,77,.86);backdrop-filter:blur(8px);pointer-events:none}
.graph-inspector-title{color:#d8dee9;font:700 9px/1.3 var(--mono);overflow-wrap:anywhere}
.graph-inspector-meta{margin-top:4px;color:#707b89;font:8px/1.35 var(--mono)}
@media(max-width:700px){.graph-frame{height:500px}.graph-inspector{display:none}.graph-legend{max-width:calc(100% - 20px)}}
@media(max-width:980px){.c{width:min(100% - 18px,1600px);padding-top:12px}.page-head{align-items:flex-start;flex-direction:column;gap:8px}.clock{text-align:left}}
'''

    space_section = (
        '<section class="card"><div class="card-head"><h2 class="card-title">space.metta</h2><span class="card-note">projection (not loaded) · text mirror of the kb statement atoms; the engine never reads this file</span></div>'
        '<div class="card-body space"><pre class="source-pre">' + space_escaped + '</pre></div></section>'
    )

    # Space Visualization section
    counts, graph_data, commit = _authority_view()
    space_graph_data = _comment_json(graph_data)
    if counts["loaded"]:
        state_line = "loaded in engine · commit %s" % commit
        chips = "".join(
            '<span class="graph-chip">%s <strong>%s</strong></span>' % (_escape_html(label), _escape_html(
                "unavailable" if counts[key] is None else counts[key]))
            for label, key in (("statements", "statements"), ("evidence links", "evidence"),
                               ("derived (depth 1)", "derived"), ("known terms", "terms_known"),
                               ("provisional terms", "terms_provisional"), ("NACE beliefs", "nace_beliefs")))
    else:
        state_line = "authority unreachable"
        chips = '<span class="label">The AtomSpace service did not answer; no counts are shown rather than stale ones.</span>'
    kb_section = (
        '<section class="card"><div class="card-head"><h2 class="card-title">Knowledge base</h2>'
        '<span class="card-note">' + _escape_html(state_line) + '</span></div>'
        '<div class="card-body" style="display:flex;flex-wrap:wrap;gap:6px">' + chips + '</div></section>'
        '<!--counts:' + _comment_json(counts) + '-->'
        '<!--graph:' + space_graph_data + '-->'
    )
    soul_section = _soul_section(counts)
    space_viz_section = (
        '<section class="card">'
        '<div class="card-head"><h2 class="card-title">Space Visualization</h2>'
        '<span class="card-note">stored and derived statements · edges only to registry terms each statement mentions</span></div>'
        '<div class="graph-shell"><div id="space_viz" class="graph-frame">'
        '<div id="space_viz_canvas" style="position:absolute;inset:0"></div>'
        '<div class="graph-loading">Loading graph...</div>'
        '<div class="graph-hud graph-hud-top">'
        '<span class="graph-chip">statements <strong id="graph_statement_count">0</strong></span>'
        '<span class="graph-chip">derived <strong id="graph_derived_count">0</strong></span>'
        '<span class="graph-chip">terms <strong id="graph_structure_count">0</strong></span>'
        '<span class="graph-chip">mentions <strong id="graph_edge_count">0</strong></span>'
        '</div>'
        '<div id="graph_legend" class="graph-legend"></div>'
        '</div>'
        '<script src="vendor/force-graph.js"></script>'
        '<script>'
        'if(!window._spaceVizInit){try{'
        'var gData=' + space_graph_data + ';'
        'var graphEl=document.getElementById("space_viz");'
        'var degrees={};'
        'gData.nodes.forEach(function(n){degrees[n.id]=0;});'
        'gData.links.forEach(function(l){var s=(l.source&&typeof l.source==="object")?l.source.id:l.source;var t=(l.target&&typeof l.target==="object")?l.target.id:l.target;degrees[s]=(degrees[s]||0)+1;degrees[t]=(degrees[t]||0)+1;});'
        'gData.nodes.forEach(function(n){n._degree=degrees[n.id]||0;});'
        'document.getElementById("graph_statement_count").textContent=gData.nodes.filter(function(n){return n.kind==="statement";}).length;'
        'document.getElementById("graph_derived_count").textContent=gData.nodes.filter(function(n){return n.kind==="derived";}).length;'
        'document.getElementById("graph_structure_count").textContent=gData.nodes.filter(function(n){return n.kind==="term";}).length;'
        'document.getElementById("graph_edge_count").textContent=gData.links.length;'
        'var legend=document.getElementById("graph_legend");'
        '[["#6ea8fe","stored statement"],["#b8a1e3","derived statement (computed, not stored)"],["#7ccf91","known term"],["#e7a86e","provisional term"]].forEach(function(x){var item=document.createElement("span");item.className="graph-legend-item";var sw=document.createElement("i");sw.className="graph-swatch";sw.style.background=x[0];item.appendChild(sw);item.appendChild(document.createTextNode(x[1]));legend.appendChild(item);});'
        'function isStmt(n){return n.kind==="statement"||n.kind==="derived";}'
        'function nodeColor(n){if(n.kind==="statement")return "#6ea8fe";if(n.kind==="derived")return "#b8a1e3";return n.status==="known"?"#7ccf91":"#e7a86e";}'
        'function nodeRadius(n){if(isStmt(n))return 4.8+Math.min(5.2,Math.log2((n._degree||0)+1)*1.25);return 3.8+Math.min(3.5,Math.log2((n._degree||0)+1));}'
        'function drawRound(ctx,x,y,w,h,r){r=Math.min(r,w/2,h/2);ctx.beginPath();ctx.moveTo(x+r,y);ctx.arcTo(x+w,y,x+w,y+h,r);ctx.arcTo(x+w,y+h,x,y+h,r);ctx.arcTo(x,y+h,x,y,r);ctx.arcTo(x,y,x+w,y,r);ctx.closePath();}'
        'var graph=ForceGraph()(document.getElementById("space_viz_canvas"));'
        'function resizeGraph(){graph.width(graphEl.clientWidth).height(graphEl.clientHeight);}'
        'resizeGraph();'
        'new ResizeObserver(resizeGraph).observe(graphEl);'
        'var loadingEl=graphEl.querySelector(".graph-loading");if(loadingEl)loadingEl.remove();'
        'graph.graphData(gData);'
        'graph.nodeRelSize(6);'
        'graph.warmupTicks(300);'
        'graph.cooldownTicks(0);'
        'graph.nodeLabel(function(n){if(n.kind==="statement")return n.label+" (stv "+n.stv.join(" ")+")";if(n.kind==="derived")return "derived: "+n.label+" (stv "+n.stv.join(" ")+") from "+(n.premises||[]).join(", ");return n.status+" term: "+n.label+" · mentioned by "+(n._degree||0)+" statements";});'
        'graph.nodeCanvasObject(function(node,ctx,globalScale){'
        'var label=String(node.label||node.id);var r=nodeRadius(node);var base=nodeColor(node);ctx.save();'
        'ctx.fillStyle=base;ctx.strokeStyle="rgba(225,232,240,.62)";ctx.lineWidth=.75/globalScale;'
        'if(node.kind==="term"){ctx.beginPath();ctx.moveTo(node.x,node.y-r);ctx.lineTo(node.x+r,node.y);ctx.lineTo(node.x,node.y+r);ctx.lineTo(node.x-r,node.y);ctx.closePath();if(node.status!=="known"){ctx.setLineDash([2/globalScale,2/globalScale]);ctx.fillStyle="rgba(231,168,110,.25)";ctx.strokeStyle=base;}ctx.fill();ctx.stroke();ctx.setLineDash([]);}'
        'else if(node.kind==="derived"){ctx.beginPath();ctx.arc(node.x,node.y,r,0,2*Math.PI);ctx.setLineDash([2/globalScale,1.5/globalScale]);ctx.fillStyle="rgba(184,161,227,.35)";ctx.strokeStyle=base;ctx.fill();ctx.stroke();ctx.setLineDash([]);}'
        'else{ctx.beginPath();ctx.arc(node.x,node.y,r,0,2*Math.PI);ctx.fill();ctx.stroke();}'
        'var fontSize=(isStmt(node)?8.6:8.2)/globalScale;ctx.font=(isStmt(node)?"500 ":"700 ")+fontSize+"px ui-monospace,SFMono-Regular,Menlo,monospace";'
        'var maxLen=isStmt(node)?72:46;var shown=label.length>maxLen?label.slice(0,maxLen-1)+"…":label;var tw=ctx.measureText(shown).width,padX=5/globalScale,padY=3/globalScale;'
        'var x=node.x+r+4/globalScale,y=node.y-(fontSize+padY*2)/2;drawRound(ctx,x,y,tw+padX*2,fontSize+padY*2,3/globalScale);'
        'ctx.fillStyle="rgba(10,13,17,.88)";ctx.fill();ctx.strokeStyle=isStmt(node)?"rgba(80,105,140,.72)":"rgba(105,91,68,.76)";ctx.lineWidth=.6/globalScale;ctx.stroke();'
        'ctx.fillStyle=isStmt(node)?"#c9d1dc":base;ctx.textAlign="left";ctx.textBaseline="middle";ctx.fillText(shown,x+padX,node.y);ctx.restore();'
        '});'
        'graph.linkColor(function(l){var s=l.source;if(s&&typeof s==="object"&&s.kind==="derived")return "rgba(184,161,227,.45)";var t=l.target;if(t&&typeof t==="object"){return t.status==="known"?"rgba(124,207,145,.46)":"rgba(231,168,110,.46)";}return "rgba(120,131,145,.45)";});'
        'graph.linkWidth(function(){return 1.15;});'
        'graph.linkDirectionalParticles(0);'
        'graph.linkDirectionalArrowLength(0);'
        'graph.linkLabel(function(l){return "mentions: "+(l.term||"");});'
        'graph.d3AlphaDecay(0.03);'
        'graph.d3VelocityDecay(0.3);'
        'graph.d3Force("charge").strength(function(n){return isStmt(n)?-360:-220;});'
        'graph.d3Force("link").distance(function(){return 64;});'
        'window._spaceVizGraph=graph;'
        'window._spaceVizInit=true;'
        'graph.onEngineStop(function(){if(window._graphReady) return; window._graphReady=true;'
        'setTimeout(function(){'
        'try{'
        'var p=new URLSearchParams(window.location.search);'
        'var z=parseFloat(p.get("z"));'
        'if(z&&z>0){'
        'graph.zoom(z,0);'
        'graph.centerAt(parseFloat(p.get("cx")||0),parseFloat(p.get("cy")||0),0);'
        'window.scrollTo(0,parseInt(p.get("sy")||0));'
        '}else{graph.zoomToFit(400,40);}'
        'window._vizRestoring=false;'
        '}catch(e){graph.zoomToFit(400,40);window._vizRestoring=false;}'
        '},50);'
        '});'
        'setTimeout(function(){'
        'if(!window._graphReady){'
        'try{'
        'var p=new URLSearchParams(window.location.search);'
        'var z=parseFloat(p.get("z"));'
        'if(z&&z>0){'
        'graph.zoom(z,0);'
        'graph.centerAt(parseFloat(p.get("cx")||0),parseFloat(p.get("cy")||0),0);'
        'window.scrollTo(0,parseInt(p.get("sy")||0));'
        '}else{graph.zoomToFit(400,40);}'
        'window._vizRestoring=false;'
        '}catch(e){graph.zoomToFit(400,40);window._vizRestoring=false;}'
        '}'
        '},1000);'
        '}catch(e){window._spaceVizInit=false;window._spaceVizError=String(e);'
        'var failure=document.createElement("div");failure.className="graph-loading";'
        'failure.textContent="Graph could not load: "+e.message;'
        'document.getElementById("space_viz").appendChild(failure);}}'
        '</script>'
        '</div></div></section>'
    )

    html_doc = (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<script>'
        'window._vizRestoring=true;'
        'function _saveVizState(){try{if(window._vizRestoring||location.protocol!=="file:") return;var s=window._spaceVizGraph;if(!s){return;}var p=new URLSearchParams(window.location.search);p.set("z",s.zoom().toFixed(3));var c=s.screen2GraphCoords(s.width()/2,s.height()/2);p.set("cx",c.x.toFixed(1));p.set("cy",c.y.toFixed(1));p.set("sy",Math.round(window.scrollY));history.replaceState(null,"",window.location.pathname+"?"+p.toString());}catch(e){}}'
        'setInterval(_saveVizState,2000);'
        'window.addEventListener("beforeunload",function(){_saveVizState();});'
        'setTimeout(function(){if(location.href==="about:srcdoc"){location.replace(new URL("dashboard_atomspace.html",document.baseURI).href);}else{location.reload();}},15000);'
        '</script>'
        '<style>' + css + '</style></head><body><main class="c">'
        '<header class="page-head"><div><h1 class="page-title">Eray Index <span style="color:#66707d;font-weight:400">/ Atom Space</span></h1>'
        '<div class="page-subtitle">Knowledge base as the AtomSpace authority holds it: statements, evidence, derived conclusions, terms.</div></div>'
        '<div class="clock"><span class="clock-label">Local snapshot</span>' + _escape_html(now) + '</div></header>'
        + '<div class="grid">' + kb_section + soul_section + space_viz_section + space_section + '</div>'
        + '<div class="f">Generated by Iter · transformations/dashboard_atomspace.py · refresh 15s</div>'
        '</main></body></html>'
    )

    upload_html(html_doc)
    return messages, tools
