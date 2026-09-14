DESCRIPTION = "Gallery wrapper for context, runtime, and atomspace dashboards"

GALLERY_PATH = "dashboard_gallery.html"
DASHBOARDS = [
    ("runtime", "dashboard_runtime.html", "Runtime"),
    ("context", "dashboard_context.html", "Context"),
    ("atomspace", "dashboard_atomspace.html", "Atomspace"),
]

GALLERY_CSS = r"""
:root{
  color-scheme:dark;
  --bg:#0b0d10;
  --panel:#111419;
  --panel2:#0f1217;
  --line:#2a3039;
  --text:#d8dee9;
  --strong:#eef2f7;
  --muted:#808a98;
  --dim:#5f6977;
  --blue:#6ea8fe;
  --mono:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono",monospace;
  --sans:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
}
*{box-sizing:border-box}
html,body{margin:0;width:100%;height:100%;background:var(--bg);color:var(--text);font-family:var(--sans)}
body{overflow:hidden}
.shell{height:100vh;display:grid;grid-template-rows:auto minmax(0,1fr)}
.topbar{
  display:flex;align-items:center;justify-content:space-between;gap:16px;
  min-height:58px;padding:9px 16px;background:var(--panel2);border-bottom:1px solid var(--line)
}
.brand{display:flex;align-items:baseline;gap:9px;min-width:0;white-space:nowrap}
.brand-title{color:var(--strong);font:700 14px/1.2 var(--mono)}
.brand-sub{color:var(--dim);font:10px/1.2 var(--mono)}
.tabs{display:flex;align-items:center;gap:6px;min-width:0}
.tab{
  appearance:none;border:1px solid var(--line);background:#12161c;color:#9aa4b1;
  padding:8px 13px;font:700 10px/1 var(--mono);letter-spacing:.04em;
  text-transform:uppercase;cursor:pointer
}
.tab:hover{border-color:#4a5564;color:#d2d8e1;background:#171c23}
.tab.active{border-color:#506b8f;background:#172231;color:#9ec9ff}
.actions{display:flex;align-items:center;gap:6px;white-space:nowrap}
.action{
  appearance:none;border:1px solid var(--line);background:#12161c;color:var(--muted);
  width:30px;height:30px;font:800 14px/1 var(--mono);cursor:pointer
}
.action:hover{color:var(--strong);border-color:#4a5564}
.stage{position:relative;min-width:0;min-height:0;background:#080a0d}

.frame{
  position:absolute;
  inset:0;
  width:100%;
  height:100%;
  border:0;
  display:block;
  visibility:hidden;
  pointer-events:none;
  background:var(--bg);
}
.frame.active{
  visibility:visible;
  pointer-events:auto;
}

@media(max-width:760px){
  .topbar{align-items:flex-start;flex-wrap:wrap;padding:8px}
  .brand{width:100%}
  .tabs{flex:1;overflow-x:auto;padding-bottom:1px}
  .tab{padding:8px 10px}
}
"""

def _escape_attr(value):
    return (str(value).replace("&", "&amp;").replace('"', "&quot;")
            .replace("<", "&lt;").replace(">", "&gt;"))

def _read_dashboard(filename):
    try:
        with open("" + filename) as f:
            return f.read()
    except Exception:
        return '<!doctype html><html><body style="background:#0b0d10;color:#808a98;font-family:monospace;padding:24px">Dashboard not available yet.</body></html>'

def _standalone_html(docs):
    frames = []
    for view, filename, label in DASHBOARDS:
        active = " active" if view == "runtime" else ""
        frames.append(
            '<iframe class="frame' + active + '" id="frame-' + view + '" srcdoc="' +
            _escape_attr(docs[view]) + '" title="' + label + ' Dashboard"></iframe>'
        )
    return """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Eray Index / Dashboard Gallery</title>
<style>""" + GALLERY_CSS + """</style>
</head>
<body>
<div class="shell">
  <header class="topbar">
    <div class="brand">
      <span class="brand-title">Eray Index</span>
      <span class="brand-sub">/ Dashboard Gallery</span>
    </div>
    <nav class="tabs" aria-label="Dashboard selection">
      <button class="tab active" data-view="runtime">Runtime</button>
      <button class="tab" data-view="context">Context</button>
      <button class="tab" data-view="atomspace">Atomspace</button>
    </nav>
    <div class="actions">
      <button class="action" id="prev" title="Previous dashboard">‹</button>
      <button class="action" id="next" title="Next dashboard">›</button>
    </div>
  </header>
  <main class="stage">""" + "".join(frames) + """</main>
</div>
<script>
(function(){
  var views=["context","runtime","atomspace"];
  var current=0;
  function show(name, updateHash){
    var index=views.indexOf(name);
    if(index<0) index=0;
    current=index;
    document.querySelectorAll(".tab").forEach(function(el){
      el.classList.toggle("active", el.dataset.view===views[current]);
    });
    document.querySelectorAll(".frame").forEach(function(el){
      el.classList.toggle("active", el.id==="frame-"+views[current]);
    });
    if(updateHash!==false) history.replaceState(null,"","#"+views[current]);
  }
  document.querySelectorAll(".tab").forEach(function(el){
    el.addEventListener("click",function(){ show(el.dataset.view,true); });
  });
  document.getElementById("prev").addEventListener("click",function(){
    show(views[(current-1+views.length)%views.length],true);
  });
  document.getElementById("next").addEventListener("click",function(){
    show(views[(current+1)%views.length],true);
  });
  document.addEventListener("keydown",function(e){
    if(e.key==="ArrowLeft") document.getElementById("prev").click();
    if(e.key==="ArrowRight") document.getElementById("next").click();
  });
  var initial=(location.hash||"").replace("#","");
  show(views.indexOf(initial)>=0 ? initial : "runtime", false);
})();
</script>
</body>
</html>"""

def _ensure_live_drawer(docs):
    try:
        import js
        doc = js.document
        app = doc.getElementById("app")
        if app is None:
            return

        drawer = doc.getElementById("gallery-drawer")
        if drawer is None:
            drawer = doc.createElement("details")
            drawer.id = "gallery-drawer"
            drawer.className = "drawer"

            summary = doc.createElement("summary")
            summary.textContent = "Iter Dashboard"
            drawer.appendChild(summary)

            host = doc.createElement("div")
            host.id = "gallery-live"
            host.innerHTML = (
                '<div class="iter-gallery-topbar">'
                '<div class="iter-gallery-brand"><span class="iter-gallery-title">Eray Index</span>'
                '<span class="iter-gallery-sub">/ Dashboard Gallery</span></div>'
                '<div class="iter-gallery-tabs">'
                '<button class="iter-gallery-tab active" data-view="runtime" onclick="'
                "document.querySelectorAll('#gallery-live .iter-gallery-tab').forEach(function(x){x.classList.toggle('active',x.dataset.view==='runtime')});"
                "document.querySelectorAll('#gallery-live .iter-gallery-frame').forEach(function(x){x.classList.toggle('active',x.id==='iter-gallery-frame-runtime')})"
                '">Runtime</button>'
                '<button class="iter-gallery-tab" data-view="context" onclick="'
                "document.querySelectorAll('#gallery-live .iter-gallery-tab').forEach(function(x){x.classList.toggle('active',x.dataset.view==='context')});"
                "document.querySelectorAll('#gallery-live .iter-gallery-frame').forEach(function(x){x.classList.toggle('active',x.id==='iter-gallery-frame-context')})"
                '">Context</button>'
                '<button class="iter-gallery-tab" data-view="atomspace" onclick="'
                "document.querySelectorAll('#gallery-live .iter-gallery-tab').forEach(function(x){x.classList.toggle('active',x.dataset.view==='atomspace')});"
                "document.querySelectorAll('#gallery-live .iter-gallery-frame').forEach(function(x){x.classList.toggle('active',x.id==='iter-gallery-frame-atomspace')})"
                '">Atomspace</button>'
                '</div></div>'
                '<div class="iter-gallery-stage">'
                '<iframe class="iter-gallery-frame active" id="iter-gallery-frame-runtime"></iframe>'
                '<iframe class="iter-gallery-frame" id="iter-gallery-frame-context"></iframe>'
                '<iframe class="iter-gallery-frame" id="iter-gallery-frame-atomspace"></iframe>'
                '</div>'
            )

            style = doc.createElement("style")
            style.textContent = """
#gallery-live{height:min(68vh,760px);display:grid;grid-template-rows:auto minmax(0,1fr);background:#0b0d10;color:#d8dee9}
#gallery-live *{box-sizing:border-box}
#gallery-live .iter-gallery-topbar{display:flex;align-items:center;justify-content:space-between;gap:16px;min-height:58px;padding:9px 16px;background:#0f1217;border-bottom:1px solid #2a3039}
#gallery-live .iter-gallery-brand{display:flex;align-items:baseline;gap:9px;min-width:0;white-space:nowrap}
#gallery-live .iter-gallery-title{color:#eef2f7;font:700 14px/1.2 ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono",monospace}
#gallery-live .iter-gallery-sub{color:#5f6977;font:10px/1.2 ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono",monospace}
#gallery-live .iter-gallery-tabs{display:flex;align-items:center;gap:6px;min-width:0}
#gallery-live .iter-gallery-tab{appearance:none;border:1px solid #2a3039;background:#12161c;color:#9aa4b1;padding:8px 13px;font:700 10px/1 ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono",monospace;letter-spacing:.04em;text-transform:uppercase;cursor:pointer;border-radius:0}
#gallery-live .iter-gallery-tab:hover{border-color:#4a5564;color:#d2d8e1;background:#171c23}
#gallery-live .iter-gallery-tab.active{border-color:#506b8f;background:#172231;color:#9ec9ff}
#gallery-live .iter-gallery-stage{position:relative;min-width:0;min-height:0;background:#080a0d}
#gallery-live .iter-gallery-frame{position:absolute;inset:0;width:100%;height:100%;border:0;display:block;visibility:hidden;pointer-events:none;background:#0b0d10}
#gallery-live .iter-gallery-frame.active{visibility:visible;pointer-events:auto}
@media(max-width:760px){#gallery-live .iter-gallery-topbar{align-items:flex-start;flex-wrap:wrap;padding:8px}#gallery-live .iter-gallery-brand{width:100%}#gallery-live .iter-gallery-tabs{flex:1;overflow-x:auto;padding-bottom:1px}#gallery-live .iter-gallery-tab{padding:8px 10px}}
"""
            drawer.appendChild(style)
            drawer.appendChild(host)
            app.appendChild(drawer)

        for view, filename, label in DASHBOARDS:
            frame = doc.getElementById("iter-gallery-frame-" + view)
            if frame is not None:
                raw = docs[view]
                if str(frame.getAttribute("data-dashboard-source") or "") != raw:
                    frame.srcdoc = raw
                    frame.setAttribute("data-dashboard-source", raw)
    except Exception:
        pass

def transform(messages, tools):
    docs = {}
    for view, filename, label in DASHBOARDS:
        docs[view] = _read_dashboard(filename)

    html_doc = _standalone_html(docs)
    try:
        with open(GALLERY_PATH, "w") as f:
            f.write(html_doc)
    except Exception:
        pass

    _ensure_live_drawer(docs)
    return messages, tools
