import json
with open("atomspace_data.json") as fh:
    data = json.load(fh)
payload = json.dumps(data)
css = open("build_v3/css.part").read()
js = open("build_v3/js.part").read().replace("__PAYLOAD__", payload)
hud = ("Atom Space - " + str(len(data["nodes"])) + " atoms / " + str(len(data["edges"])) +
       " links | blue=is-a orange=class/prop purple=implies yellow=NAL truth | "
       "wheel=zoom, drag bg=pan, drag node=rearrange, click atom=details")
html = ("<!DOCTYPE html><html><head><meta charset=\"utf-8\"><title>Atom Space - Iter</title>"
        "<style>" + css + "</style></head><body>"
        "<svg id=\"svg\"></svg>"
        "<div id=\"hud\">" + hud + "</div>"
        "<div id=\"zoomer\">"
        "<button id=\"zout\">&minus;</button>"
        "<span id=\"zl\">100%</span>"
        "<button id=\"zin\">+</button>"
        "<button id=\"zfit\" class=\"wide\">Fit All</button>"
        "<button id=\"zreset\" class=\"wide\">Reset View</button>"
        "</div>"
        "<div id=\"panel\"></div>"
        "<script>" + js + "</script></body></html>")
with open("atomspace_v3.html", "w") as fh:
    fh.write(html)
print("written", len(html))
