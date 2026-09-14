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

DESCRIPTION = "Atom-space dashboard with raw space.metta and visualization"

ROOT = "."
SPACE_FILE = ROOT + "/transformations/.runtime/space.metta"


def upload_html(html_doc):
    try:
        with open(ROOT + "/dashboard_atomspace.html", "w") as f:
            f.write(html_doc)
    except Exception:
        pass


def parse_space_metta():
    """Build a hierarchical shared-subterm graph.

    Top-level MeTTa statements are statement nodes. Any meaningful term that
    occurs in at least two statements becomes a structural node. Statements
    connect only to their outermost shared terms; shared compound terms then
    connect downward to their nearest shared subterms. Therefore, if two
    statements share (& a b), they connect through (& a b), not redundantly
    through a and b as well.
    """
    try:
        space_text = open(SPACE_FILE).read()
    except Exception:
        return '{"nodes":[],"links":[]}'

    clean_lines = []
    for line in space_text.split('\n'):
        line = line.strip()
        if not line or line.startswith(';;'):
            continue
        clean_lines.append(line)
    text = ' '.join(clean_lines)

    def find_top_level_exprs(src):
        exprs = []
        depth = 0
        in_quote = False
        escaped = False
        current = ''
        for ch in src:
            if escaped:
                if depth > 0:
                    current += ch
                escaped = False
                continue
            if ch == '\\' and in_quote:
                if depth > 0:
                    current += ch
                escaped = True
                continue
            if ch == '"':
                in_quote = not in_quote
                if depth > 0:
                    current += ch
                continue
            if in_quote:
                if depth > 0:
                    current += ch
                continue
            if ch == '(':
                if depth == 0:
                    current = ''
                depth += 1
                current += ch
            elif ch == ')' and depth > 0:
                current += ch
                depth -= 1
                if depth == 0:
                    exprs.append(current.strip())
                    current = ''
            elif depth > 0:
                current += ch
        return exprs

    def tokenize(expr):
        tokens = []
        cur = ''
        in_quote = False
        escaped = False
        for ch in expr:
            if escaped:
                cur += ch
                escaped = False
                continue
            if ch == '\\' and in_quote:
                cur += ch
                escaped = True
                continue
            if ch == '"':
                cur += ch
                in_quote = not in_quote
                continue
            if in_quote:
                cur += ch
                continue
            if ch in '()':
                if cur.strip():
                    tokens.append(cur.strip())
                cur = ''
                tokens.append(ch)
            elif ch.isspace():
                if cur.strip():
                    tokens.append(cur.strip())
                cur = ''
            else:
                cur += ch
        if cur.strip():
            tokens.append(cur.strip())
        return tokens

    def parse_expr(expr):
        toks = tokenize(expr)
        pos = 0

        def parse_one():
            nonlocal pos
            if pos >= len(toks):
                return None
            tok = toks[pos]
            if tok != '(':
                pos += 1
                return tok
            pos += 1
            out = []
            while pos < len(toks) and toks[pos] != ')':
                out.append(parse_one())
            if pos < len(toks) and toks[pos] == ')':
                pos += 1
            return out

        return parse_one()

    def sexpr(term):
        if isinstance(term, list):
            return '(' + ' '.join(sexpr(x) for x in term) + ')'
        return str(term)

    STRUCTURAL = {
        'stv', '-->', '<-->', '<->', '==>', '=~>', '=/>', '=|>',
        '</>', '<|>', '|-', 'Inheritance', 'Member', 'Similarity',
        'Implication', 'Evaluation', 'Concept', 'Predicate', 'x', '×', '[]'
    }

    def is_variable(atom):
        return isinstance(atom, str) and atom.startswith('$')

    def meaningful_atom(atom):
        if not isinstance(atom, str):
            return False
        if atom in STRUCTURAL or is_variable(atom):
            return False
        try:
            float(atom)
            return False
        except ValueError:
            return True

    term_trees = {}

    def children_of(term):
        """Semantic children: skip STV and do not expose list heads as atoms."""
        if not isinstance(term, list) or not term:
            return []
        head = term[0] if isinstance(term[0], str) else None
        if head == 'stv':
            return []
        out = []
        if isinstance(term[0], list):
            out.append(term[0])
        out.extend(term[1:])
        return out

    def collect_subterms(term, out, is_root=False):
        if isinstance(term, str):
            if meaningful_atom(term):
                out.add(term)
            return
        if not isinstance(term, list) or not term:
            return
        head = term[0] if isinstance(term[0], str) else None
        if head == 'stv':
            return

        for child in children_of(term):
            collect_subterms(child, out, False)

        if not is_root:
            # Keep a compound only when it contains some meaningful content.
            contained = set()
            for child in children_of(term):
                collect_subterms(child, contained, False)
            if contained:
                rendered = sexpr(term)
                out.add(rendered)
                term_trees.setdefault(rendered, term)

    exprs = find_top_level_exprs(text)
    statement_nodes = []
    statement_trees = []
    term_sets = []
    term_occurs = {}

    for expr in exprs:
        tree = parse_expr(expr)
        if tree is None:
            continue
        terms = set()
        collect_subterms(tree, terms, True)
        idx = len(statement_nodes)
        stmt_id = 'stmt_' + str(idx)
        statement_nodes.append({
            'id': stmt_id,
            'name': expr,
            'statement': expr,
            'kind': 'statement',
            'subterms': sorted(terms)
        })
        statement_trees.append(tree)
        term_sets.append(terms)
        for term in terms:
            term_occurs.setdefault(term, set()).add(idx)

    shared_terms = {term for term, owners in term_occurs.items() if len(owners) >= 2}

    # Prune structurally redundant descendants. If (& a b), a, and b occur in
    # exactly the same set of statements, (& a b) already captures all of that
    # overlap, so separate a/b nodes add no information. A child remains when
    # it also participates elsewhere, giving a genuine lower hierarchical level.
    redundant_terms = set()
    for bigger in list(shared_terms):
        tree = term_trees.get(bigger)
        if tree is None:
            continue
        descendants = set()
        collect_subterms(tree, descendants, True)
        for smaller in descendants.intersection(shared_terms):
            if smaller != bigger and term_occurs.get(smaller) == term_occurs.get(bigger):
                redundant_terms.add(smaller)
    shared_terms.difference_update(redundant_terms)

    def shared_frontier(term, allow_self=False):
        """Return nearest/outermost shared terms below this tree position."""
        if isinstance(term, str):
            if meaningful_atom(term) and term in shared_terms:
                return {term}
            return set()
        if not isinstance(term, list) or not term:
            return set()
        head = term[0] if isinstance(term[0], str) else None
        if head == 'stv':
            return set()

        rendered = sexpr(term)
        if allow_self and rendered in shared_terms:
            return {rendered}

        found = set()
        for child in children_of(term):
            found.update(shared_frontier(child, True))
        return found

    nodes = list(statement_nodes)
    term_node_ids = {}
    for term in sorted(shared_terms, key=lambda t: (0 if t.startswith('(') else 1, -len(t), t)):
        term_id = 'term_' + str(len(term_node_ids))
        term_node_ids[term] = term_id
        nodes.append({
            'id': term_id,
            'name': term,
            'term': term,
            'kind': 'compound' if term.startswith('(') else 'atom',
            'statement_count': len(term_occurs[term])
        })

    links = []
    seen_links = set()

    def add_link(source, target, link_type, term):
        key = (source, target, link_type)
        if key in seen_links:
            return
        seen_links.add(key)
        links.append({
            'source': source,
            'target': target,
            'type': link_type,
            'term': term
        })

    # Statement -> outermost shared structure only.
    for i, tree in enumerate(statement_trees):
        for term in sorted(shared_frontier(tree, False)):
            add_link(statement_nodes[i]['id'], term_node_ids[term], 'shares', term)

    # Shared compound -> nearest shared descendants. This is the hierarchy.
    for term, tree in term_trees.items():
        if term not in shared_terms:
            continue
        parent_id = term_node_ids[term]
        for child_term in sorted(shared_frontier(tree, False)):
            if child_term == term:
                continue
            add_link(parent_id, term_node_ids[child_term], 'contains', child_term)

    return json.dumps({
        'nodes': nodes,
        'links': links,
        'statementCount': len(statement_nodes),
        'structuralCount': len(term_node_ids)
    })


def transform(messages, tools):
    t = time.localtime(); now = "%04d-%02d-%02d %02d:%02d:%02d" % (t[0], t[1], t[2], t[3], t[4], t[5])

    space_content = ""
    if _exists(SPACE_FILE):
        space_content = open(SPACE_FILE).read()
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
        '<section class="card"><div class="card-head"><h2 class="card-title">space.metta</h2><span class="card-note">raw symbolic space</span></div>'
        '<div class="card-body space"><pre class="source-pre">' + space_escaped + '</pre></div></section>'
    )

    # Space Visualization section
    space_graph_data = parse_space_metta()
    space_viz_section = (
        '<section class="card">'
        '<div class="card-head"><h2 class="card-title">Space Visualization</h2>'
        '<span class="card-note">statement nodes · shared compounds form hierarchy over shared atoms</span></div>'
        '<div class="graph-shell"><div id="space_viz" class="graph-frame">'
        '<div class="graph-loading">Loading graph...</div>'
        '<div class="graph-hud graph-hud-top">'
        '<span class="graph-chip">statements <strong id="graph_statement_count">0</strong></span>'
        '<span class="graph-chip">structure <strong id="graph_structure_count">0</strong></span>'
        '<span class="graph-chip">links <strong id="graph_edge_count">0</strong></span>'
        '</div>'
        '<div id="graph_legend" class="graph-legend"></div>'
        '</div>'
        '<script>if(typeof ForceGraph==="undefined"){var _fg=document.createElement("script");_fg.src="vendor/force-graph.js";_fg.onerror=function(){var el=document.getElementById("space_viz");if(el)el.innerHTML="<div class=\\"graph-loading\\">Graph library unavailable offline; raw space.metta shown above.</div>";};document.head.appendChild(_fg);}</script>'
        '<script>'
        'if(!window._spaceVizInit){window._spaceVizInit=true;'
        'var gData=' + space_graph_data + ';'
        'var graphEl=document.getElementById("space_viz");'
        'var degrees={};'
        'gData.nodes.forEach(function(n){degrees[n.id]=0;});'
        'gData.links.forEach(function(l){var s=(l.source&&typeof l.source==="object")?l.source.id:l.source;var t=(l.target&&typeof l.target==="object")?l.target.id:l.target;degrees[s]=(degrees[s]||0)+1;degrees[t]=(degrees[t]||0)+1;});'
        'gData.nodes.forEach(function(n){n._degree=degrees[n.id]||0;});'
        'document.getElementById("graph_statement_count").textContent=gData.statementCount||gData.nodes.filter(function(n){return n.kind==="statement";}).length;'
        'document.getElementById("graph_structure_count").textContent=gData.structuralCount||gData.nodes.filter(function(n){return n.kind!=="statement";}).length;'
        'document.getElementById("graph_edge_count").textContent=gData.links.length;'
        'var legend=document.getElementById("graph_legend");'
        '[["#6ea8fe","statement"],["#e7a86e","compound shared term"],["#7ccf91","atomic shared term"]].forEach(function(x){var item=document.createElement("span");item.className="graph-legend-item";var sw=document.createElement("i");sw.className="graph-swatch";sw.style.background=x[0];item.appendChild(sw);item.appendChild(document.createTextNode(x[1]));legend.appendChild(item);});'
        'function nodeColor(n){if(n.kind==="statement")return "#6ea8fe";if(n.kind==="compound")return "#e7a86e";return "#7ccf91";}'
        'function nodeRadius(n){if(n.kind==="statement")return 4.8+Math.min(5.2,Math.log2((n._degree||0)+1)*1.25);if(n.kind==="compound")return 5.2+Math.min(3.5,Math.log2((n._degree||0)+1));return 3.8+Math.min(2.8,Math.log2((n._degree||0)+1)*.8);}'
        'function drawRound(ctx,x,y,w,h,r){r=Math.min(r,w/2,h/2);ctx.beginPath();ctx.moveTo(x+r,y);ctx.arcTo(x+w,y,x+w,y+h,r);ctx.arcTo(x+w,y+h,x,y+h,r);ctx.arcTo(x,y+h,x,y,r);ctx.arcTo(x,y,x+w,y,r);ctx.closePath();}'
        'var graph=ForceGraph()(graphEl);'
        'var loadingEl=graphEl.querySelector(".graph-loading");if(loadingEl)loadingEl.remove();'
        'graph.graphData(gData);'
        'graph.nodeRelSize(6);'
        'graph.warmupTicks(300);'
        'graph.cooldownTicks(0);'
        'graph.nodeLabel(function(n){if(n.kind==="statement")return n.statement||n.name||n.id;return (n.kind==="compound"?"shared compound: ":"shared atom: ")+(n.term||n.name||n.id)+" · links "+(n._degree||0)+" statements";});'
        'graph.nodeCanvasObject(function(node,ctx,globalScale){'
        'var label=String(node.name||node.id);var r=nodeRadius(node);var base=nodeColor(node);ctx.save();'
        'ctx.fillStyle=base;ctx.strokeStyle="rgba(225,232,240,.62)";ctx.lineWidth=.75/globalScale;'
        'if(node.kind==="compound"){ctx.beginPath();ctx.moveTo(node.x,node.y-r);ctx.lineTo(node.x+r,node.y);ctx.lineTo(node.x,node.y+r);ctx.lineTo(node.x-r,node.y);ctx.closePath();ctx.fill();ctx.stroke();}'
        'else{ctx.beginPath();ctx.arc(node.x,node.y,r,0,2*Math.PI);ctx.fill();ctx.stroke();}'
        'var fontSize=(node.kind==="statement"?8.6:8.2)/globalScale;ctx.font=(node.kind==="statement"?"500 ":"700 ")+fontSize+"px ui-monospace,SFMono-Regular,Menlo,monospace";'
        'var maxLen=node.kind==="statement"?72:46;var shown=label.length>maxLen?label.slice(0,maxLen-1)+"…":label;var tw=ctx.measureText(shown).width,padX=5/globalScale,padY=3/globalScale;'
        'var x=node.x+r+4/globalScale,y=node.y-(fontSize+padY*2)/2;drawRound(ctx,x,y,tw+padX*2,fontSize+padY*2,3/globalScale);'
        'ctx.fillStyle="rgba(10,13,17,.88)";ctx.fill();ctx.strokeStyle=node.kind==="statement"?"rgba(80,105,140,.72)":"rgba(105,91,68,.76)";ctx.lineWidth=.6/globalScale;ctx.stroke();'
        'ctx.fillStyle=node.kind==="statement"?"#c9d1dc":base;ctx.textAlign="left";ctx.textBaseline="middle";ctx.fillText(shown,x+padX,node.y);ctx.restore();'
        '});'
        'graph.linkColor(function(l){if(l.type==="contains")return "rgba(140,148,160,.32)";var t=l.target;if(t&&typeof t==="object"){return t.kind==="compound"?"rgba(231,168,110,.52)":"rgba(124,207,145,.46)";}return "rgba(120,131,145,.45)";});'
        'graph.linkWidth(function(){return 1.15;});'
        'graph.linkDirectionalParticles(0);'
        'graph.linkDirectionalArrowLength(0);'
        'graph.linkLabel(function(l){return (l.type==="contains"?"contains shared: ":"shares: ")+(l.term||"");});'
        'graph.d3AlphaDecay(0.03);'
        'graph.d3VelocityDecay(0.3);'
        'graph.d3Force("charge").strength(function(n){return n.kind==="statement"?-360:-220;});'
        'graph.d3Force("link").distance(function(l){var t=l.target;return (t&&typeof t==="object"&&t.kind==="compound")?74:64;});'
        'window._spaceVizGraph=graph;'
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
        '}'
        '</script>'
        '</div></div></section>'
    )

    html_doc = (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<script>'
        'window._vizRestoring=true;'
        'function _saveVizState(){try{if(window._vizRestoring) return;var s=window._spaceVizGraph;if(!s){return;}var p=new URLSearchParams(window.location.search);p.set("z",s.zoom().toFixed(3));var c=s.screen2GraphCoords(s.width()/2,s.height()/2);p.set("cx",c.x.toFixed(1));p.set("cy",c.y.toFixed(1));p.set("sy",Math.round(window.scrollY));history.replaceState(null,"",window.location.pathname+"?"+p.toString());}catch(e){}}'
        'setInterval(_saveVizState,2000);'
        'window.addEventListener("beforeunload",function(){_saveVizState();});'
        'setTimeout(function(){window.location.reload();},15000);'
        '</script>'
        '<style>' + css + '</style></head><body><main class="c">'
        '<header class="page-head"><div><h1 class="page-title">Eray Index <span style="color:#66707d;font-weight:400">/ Atom Space</span></h1>'
        '<div class="page-subtitle">Raw symbolic space and hierarchical shared-subterm visualization.</div></div>'
        '<div class="clock"><span class="clock-label">Local snapshot</span>' + _escape_html(now) + '</div></header>'
        + '<div class="grid">' + space_section + space_viz_section + '</div>'
        + '<div class="f">Generated by Iter · transformations/dashboard_atomspace.py · refresh 15s</div>'
        '</main></body></html>'
    )

    upload_html(html_doc)
    return messages, tools
