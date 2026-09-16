import json

with open("atomspace_data.json") as fh:
    data = json.load(fh)

payload = json.dumps(data)

html = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Atom Space — Iter</title>
<style>
  body { margin:0; font-family: ui-monospace, 'SF Mono', Menlo, monospace; background:#0d1117; color:#c9d1d9; overflow:hidden; }
  #wrap { display:flex; height:100vh; }
  #graph { flex:1; position:relative; }
  #panel { width:340px; background:#161b22; border-left:1px solid #30363d; padding:16px; overflow-y:auto; }
  #panel h2 { margin-top:0; color:#58a6ff; font-size:16px; word-break:break-all; }
  #panel .tag { display:inline-block; background:#30363d; border-radius:4px; padding:2px 8px; font-size:11px; margin-right:6px; color:#8b949e; }
  #panel .kv { margin:6px 0; font-size:12px; line-height:1.5; }
  #panel .kv b { color:#7ee787; }
  #panel .section { margin-top:14px; border-top:1px solid #30363d; padding-top:10px; }
  #panel .empty { color:#8b949e; font-style:italic; }
  .edge { stroke:#30363d; stroke-width:1.2; }
  .edge.implies { stroke:#bc8cff; }
  .edge.is-a { stroke:#58a6ff; }
  .edge.class { stroke:#f0883e; }
  .node circle { fill:#21262d; stroke:#58a6ff; stroke-width:1.5; cursor:pointer; }
  .node.atom circle { stroke:#3fb950; }
  .node.class circle { stroke:#f0883e; }
  .node.has-stv circle { stroke:#e3b341; fill:#2d2226; }
  .node text { fill:#c9d1d9; font-size:10px; text-anchor:middle; pointer-events:none; }
  .node.selected circle { stroke:#f85149; stroke-width:3; }
  #legend { position:absolute; top:10px; left:10px; background:#161b22cc; padding:8px 12px; border-radius:6px; font-size:11px; border:1px solid #30363d; }
  #legend div { margin:3px 0; }
  #title { position:absolute; top:10px; right:10px; background:#161b22cc; padding:8px 12px; border-radius:6px; font-size:11px; border:1px solid #30363d; color:#8b949e; }
#controls { position:absolute; z-index:10; left:10px; top:10px; display:flex; gap:6px; align-items:center; background:rgba(22,27,34,.92); border:1px solid #30363d; border-radius:8px; padding:6px 8px; box-shadow:0 2px 8px rgba(0,0,0,.35); }
  #controls button { all:unset; cursor:pointer; line-height:26px; min-width:28px; text-align:center; border-radius:6px; color:#c9d1d9; border:1px solid #30363d; background:#21262d; font-size:14px; padding:0 7px; }
  #controls button:hover { background:#30363d; color:#fff; }
  #zoomLabel { color:#8b949e; font-size:12px; min-width:42px; text-align:center; }
  #panelToggle { position:absolute; z-index:10; right:10px; top:10px; cursor:pointer; line-height:26px; background:rgba(22,27,34,.92); border:1px solid #30363d; border-radius:8px; color:#c9d1d9; padding:2px 10px; font-size:12px; box-shadow:0 2px 8px rgba(0,0,0,.35); }
  #panelToggle:hover { background:#30363d; color:#fff; }
  #panel { transition: width .25s ease, padding .25s ease, border .25s ease; }
  #panel.collapsed { width:0; padding:0; border:none; overflow:hidden; }
</style>
</head>
<body>
<div id="wrap">
  <div id="graph">
    <svg id="svg" width="100%" height="100%"></svg>
    <div id="legend">
      <div><span style="color:#58a6ff">━</span> is-a (Inheritance)</div>
      <div><span style="color:#f0883e">━</span> property/class</div>
      <div><span style="color:#bc8cff">━</span> ==&gt; (Implication)</div>
      <div><span style="color:#e3b341">◉</span> node with NAL truth value</div>
    </div>
    <div id="title">Atom Space — __NNODES__ atoms / __NEDGES__ links · drag to move · click an atom for details</div>
  </div>
  <div id="panel">
    <h2>Atom Space Explorer</h2>
    <div class="kv">Click any atom node in the graph to inspect it.<br><br>Edges show relationships: inheritance (--&gt;), class/property membership, and implication (==&gt;).</div>
  </div>
</div>
<script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
<script>
const DATA = __PAYLOAD__;

const svg = d3.select("#svg");
const g = svg.append("g");
const width = () => window.innerWidth - 340;
const height = () => window.innerHeight;

const updZ = k => { const el = document.getElementById("zoomLabel"); if (el) el.textContent = Math.round(k*100) + "%"; };
const zb = d3.zoom().scaleExtent([0.2, 8]).on("zoom", e => { g.attr("transform", e.transform); updZ(e.transform.k); });
svg.call(zb);
function fitView(){ const cs = document.querySelectorAll("#svg circle"); if(!cs.length) return; let a=1e9,b=1e9,c=-1e9,d=-1e9; cs.forEach(n=>{const x=+n.getAttribute("cx"),y=+n.getAttribute("cy"); a=Math.min(a,x); c=Math.max(c,x); b=Math.min(b,y); d=Math.max(d,y);}); const r = document.getElementById("graph").getBoundingClientRect(); const k = Math.min(r.width/(c-a+100), r.height/(d-b+100), 4); svg.transition().duration(250).call(zb.transform, d3.zoomIdentity.translate(r.width/2-(a+c)/2*k, r.height/2-(b+d)/2*k).scale(k)); }
setTimeout(fitView, 900);
const bar = document.createElement("div"); bar.id = "controls"; bar.innerHTML = '<button id="zin">+</button><button id="zout">&#8722;</button><span id="zoomLabel">100%</span><button id="zfit">&#9975; Fit</button><button id="zreset">&#10226; Reset</button>'; document.getElementById("graph").appendChild(bar);
document.getElementById("zin").onclick = () => svg.transition().duration(150).call(zb.scaleBy, 1.3);
document.getElementById("zout").onclick = () => svg.transition().duration(150).call(zb.scaleBy, 0.75);
document.getElementById("zfit").onclick = fitView;
document.getElementById("zreset").onclick = () => svg.transition().duration(150).call(zb.transform, d3.zoomIdentity);
const pt = document.createElement("div"); pt.id = "panelToggle"; document.getElementById("graph").appendChild(pt);
function setCol(c){ document.getElementById("panel").classList.toggle("collapsed", c); pt.textContent = c ? "Explorer \u25B8" : "Explorer \u25BE"; }
pt.onclick = () => setCol(!document.getElementById("panel").classList.contains("collapsed"));
setCol(true);

const sim = d3.forceSimulation(DATA.nodes)
  .force("link", d3.forceLink(DATA.edges).id(d => d.id).distance(90).strength(0.3))
  .force("charge", d3.forceManyBody().strength(-200))
  .force("center", d3.forceCenter(width()/2, height()/2))
  .force("collide", d3.forceCollide(28));

const link = g.selectAll("line").data(DATA.edges).join("line")
  .attr("class", d => "edge " + d.kind.replace("implies","implies").replace("is-a","is-a").replace("class","class"));

const node = g.selectAll("g.node").data(DATA.nodes).join("g")
  .attr("class", d => "node " + d.type + (d.stvs ? " has-stv" : ""))
  .call(d3.drag()
    .on("start", (e, d) => { if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
    .on("drag", (e, d) => { d.fx = e.x; d.fy = e.y; })
    .on("end", (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }));

node.append("circle").attr("r", d => d.details && Object.keys(d.details).length ? 12 : (d.stvs ? 9 : 6));
node.append("text").attr("dy", -14).text(d => d.label);

node.on("click", (e, d) => {
  d3.selectAll(".node.selected").classed("selected", false);
  d3.select(e.currentTarget).classed("selected", true);
  showPanel(d);
});

function showPanel(d) {
  let html = "<h2>" + d.label + "</h2>";
  html += '<div><span class="tag">type: ' + d.type + "</span>";
  if (d.stvs) html += '<span class="tag">NAL truth values</span>';
  html += "</div>";
  if (d.details && Object.keys(d.details).length) {
    html += '<div class="section kv"><b>Properties</b>';
    for (const [k, v] of Object.entries(d.details)) html += '<div class="kv"><b>' + k + ':</b> ' + v + "</div>";
    html += "</div>";
  }
  if (d.stvs) {
    html += '<div class="section kv"><b>NAL Truth Values (f, c)</b>';
    for (const s of d.stvs) html += '<div class="kv">' + s.kind + ': <b>' + s.f + ', ' + s.c + "</b></div>";
    html += "</div>";
  }
  const rels = DATA.edges.filter(e => e.source.id === d.id || e.target.id === d.id);
  if (rels.length) {
    html += '<div class="section kv"><b>Relations (' + rels.length + ')</b>';
    for (const r of rels) {
      const other = r.source.id === d.id ? r.target.id : r.source.id;
      const dir = r.source.id === d.id ? "→" : "←";
      html += '<div class="kv">' + dir + ' <span style="color:' + (r.kind === "implies" ? "#bc8cff" : r.kind === "class" ? "#f0883e" : "#58a6ff") + '">' + r.kind + '</span> ' + other + "</div>";
    }
    html += "</div>";
  }
  document.getElementById("panel").innerHTML = html;
}

sim.on("tick", () => {
  link.attr("x1", d => d.source.x).attr("y1", d => d.source.y)
      .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
  node.attr("transform", d => "translate(" + d.x + "," + d.y + ")");
});
</script>
</body>
</html>"""

html = html.replace("__PAYLOAD__", payload).replace("__NNODES__", str(len(data["nodes"]))).replace("__NEDGES__", str(len(data["edges"])))
with open("atomspace_v3.html", "w") as fh:
    fh.write(html)
print("written:", len(html), "chars")
