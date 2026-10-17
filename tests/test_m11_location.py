#!/usr/bin/env python3
"""M11-A1..A4: native location for Map Station — the pure helper logic, the main-process wiring,
the page's fallback chain, and the helper on disk.

Spec: docs/milestones/M11_browser_track.md section A.
"""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m11_support import (pending, require_m11, bridge_json, main_js, section, run_playwright, playwright_available,  # noqa: E402
                         NODE, REPO, ITER_SRC)


@unittest.skipUnless(NODE, "needs node")
class PureLocationTests(unittest.TestCase):
    """M11-A1"""

    @pending("M11-A1")
    def test_parse_location_accepts_corelocationcli_shapes_and_rejects_junk(self):
        require_m11()
        out = bridge_json("location.js", """process.stdout.write(JSON.stringify([
  M.parseLocation('{"latitude": -34.6037, "longitude": -58.3816, "altitude": 25, "h_accuracy": 35, "time": "2026-10-17T12:00:00Z"}'),
  M.parseLocation('Waiting for fix...\\n{"latitude": 47.6, "longitude": -122.3, "horizontalAccuracy": 10.5, "time": 1760702400}'),
  M.parseLocation('{"latitude": 47.6, "longitude": -122.3}'),
  M.parseLocation('{"latitude": 91, "longitude": 0}'), M.parseLocation('{"latitude": "x", "longitude": 1}'),
  M.parseLocation(''), M.parseLocation('not json'), M.parseLocation(null) ]));""")
        self.assertEqual(out[0], {"lat": -34.6037, "lon": -58.3816, "accuracy": 35, "at": "2026-10-17T12:00:00.000Z"})
        self.assertEqual(out[1]["lat"], 47.6)
        self.assertEqual(out[1]["accuracy"], 10.5)
        self.assertEqual(out[1]["at"], "2026-10-17T12:00:00.000Z")
        self.assertEqual(out[2], {"lat": 47.6, "lon": -122.3, "accuracy": None, "at": None})
        self.assertEqual(out[3:], [None] * 5)

    @pending("M11-A1")
    def test_helper_command_resolution_order(self):
        out = bridge_json("location.js", """
const rt = '/x/.runtime';
const pick = (env, present) => M.helperCommand({ env, runtimeDir: rt, exists: (p) => present.includes(p) });
process.stdout.write(JSON.stringify([
  pick({ ITERBROW_LOCATION_HELPER: '/me/loc' }, ['/me/loc', rt + '/bin/iter_location', '/opt/homebrew/bin/CoreLocationCLI']),
  pick({ ITERBROW_LOCATION_HELPER: '/me/missing' }, [rt + '/bin/iter_location', '/opt/homebrew/bin/CoreLocationCLI']),
  pick({}, ['/opt/homebrew/bin/CoreLocationCLI', '/usr/local/bin/CoreLocationCLI']),
  pick({}, ['/usr/local/bin/CoreLocationCLI']),
  pick({}, []) ]));""")
        self.assertEqual(out[0], {"file": "/me/loc", "args": [], "source": "env"})
        self.assertEqual(out[1], {"file": "/x/.runtime/bin/iter_location", "args": [], "source": "built"})
        self.assertEqual(out[2], {"file": "/opt/homebrew/bin/CoreLocationCLI", "args": ["-once", "-json"], "source": "brew"})
        self.assertEqual(out[3]["file"], "/usr/local/bin/CoreLocationCLI")
        self.assertIsNone(out[4])

    @pending("M11-A1")
    def test_failure_reasons(self):
        out = bridge_json("location.js", """process.stdout.write(JSON.stringify([
  M.failure(2, null, 'location services denied for this app'), M.failure(1, null, 'Error Domain=kCLErrorDomain Code=1'),
  M.failure(null, 'SIGKILL', ''), M.failure(null, 'SIGTERM', ''), M.failure(3, null, 'no fix'), M.failure(1, null, '') ]));""")
        self.assertEqual(out, ["denied", "denied", "timeout", "timeout", "unavailable", "unavailable"])


class WiringTests(unittest.TestCase):
    """M11-A2"""

    @pending("M11-A2")
    def test_main_runs_the_helper_only_for_map_station(self):
        main = main_js()
        self.assertIn("require('./bridge/location')", main)
        handler = section(main, "ipcMain.handle('location:current'", after=2500)
        self.assertIn("isMapStationPageOrigin(", handler, "the sender must be the Map Station page")
        self.assertIn("'not-allowed'", handler)
        self.assertIn("'no-helper'", handler)
        self.assertIn("corelocationcli", handler.lower(), "the hint names the brew route")
        self.assertIn("execFile(", handler)
        self.assertIn("15000", handler, "15 s timeout")
        self.assertIn("SIGKILL", handler)
        self.assertRegex(handler, r"pushLog\(`\[location\]")
        self.assertNotIn("GOOGLE_API_KEY", main, "no Google network location")

    @pending("M11-A2")
    def test_app_preload_exposes_locate_and_stays_in_sync(self):
        preload = (REPO / "bridge" / "app_preload.js").read_text(encoding="utf-8")
        self.assertRegex(preload, r"locate:\s*\(\)\s*=>\s*ipcRenderer\.invoke\('location:current'\)")
        check = subprocess.run([NODE, str(REPO / "scripts" / "sync_margin_preload.js"), "--check"], capture_output=True, text=True)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)


@unittest.skipUnless(NODE and playwright_available(), "needs node and system Playwright")
class MapStationTests(unittest.TestCase):
    """M11-A3"""

    PAGE = "file://" + str(ITER_SRC / "mapstation" / "index.html")

    def _page(self, locate_js, geolocation_js, probe):
        return json.loads(run_playwright("""
import json
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1100, "height": 800})
    pg.add_init_script(\"\"\"
      window.__requests = [];
      window.iterApp = { locate: %s };
      Object.defineProperty(navigator, 'geolocation', { value: %s, configurable: true });
    \"\"\")
    # No network: Leaflet is replaced by a chainable stand-in (every call returns itself), tiles are refused.
    LEAFLET = "const chain = new Proxy(function(){}, { get: (t, k) => (k === 'then' ? undefined : (k === 'lat' || k === 'lng' ? 0 : chain)), apply: () => chain }); window.L = chain;"
    def route(r):
        if r.request.url.startswith("file://"): return r.continue_()
        if "leaflet.js" in r.request.url: return r.fulfill(status=200, content_type="application/javascript", body=LEAFLET)
        if "leaflet.css" in r.request.url: return r.fulfill(status=200, content_type="text/css", body="")
        return r.abort()
    pg.route("**/*", route)
    seen = []
    pg.on("request", lambda r: seen.append(r.url))
    pg.goto(%s); pg.wait_for_timeout(900)   # the page locates itself on load
    out = pg.evaluate(%s); out["requests"] = seen
    print(json.dumps(out)); b.close()
""" % (locate_js, geolocation_js, json.dumps(self.PAGE), json.dumps(probe))).strip().splitlines()[-1])

    # Status line plus the chat log: the page reports the reason in the log and the state in the status.
    PROBE = "(() => ({ status: document.getElementById('statusText').textContent + ' | ' + document.getElementById('chatlog').textContent, button: document.getElementById('locateBtn').textContent }))()"

    @pending("M11-A3")
    def test_native_route_first(self):
        require_m11()
        out = self._page("() => Promise.resolve({ ok: true, lat: -34.6037, lon: -58.3816, accuracy: 30, at: null, source: 'brew' })",
                         "{ getCurrentPosition: (ok, err) => { window.__geoCalled = true; err({ code: 2 }); } }", self.PROBE)
        self.assertIn("-34.6037", out["status"])
        self.assertIn("native", out["status"])
        self.assertFalse(any("google" in u or "geolocation" in u for u in out["requests"]), out["requests"])

    @pending("M11-A3")
    def test_falls_back_and_names_the_real_reason(self):
        out = self._page("() => Promise.resolve({ ok: false, reason: 'no-helper', hint: 'brew install corelocationcli' })",
                         "undefined", self.PROBE)
        self.assertIn("corelocationcli", out["status"].lower())
        denied = self._page("() => Promise.resolve({ ok: false, reason: 'denied' })",
                            "{ getCurrentPosition: (ok, err) => err({ code: 1 }) }", self.PROBE)
        self.assertIn("Location Services", denied["status"])
        self.assertIn("Locate me", denied["button"], "the button is usable again")


class HelperOnDiskTests(unittest.TestCase):
    """M11-A4"""

    @pending("M11-A4")
    def test_swift_source_and_build_script(self):
        swift = (REPO / "scripts" / "location" / "iter_location.swift").read_text(encoding="utf-8")
        for needle in ("CLLocationManager", "requestWhenInUseAuthorization", "\"latitude\"", "\"longitude\"", "h_accuracy", "denied"):
            self.assertIn(needle, swift, needle)
        build = REPO / "scripts" / "build_location_helper.sh"
        self.assertTrue(os.access(build, os.X_OK), "build script is executable")
        env = {**os.environ, "PATH": "/nonexistent", "ITER_DIR": str(REPO / "iter")}
        run = subprocess.run(["/bin/bash", str(build), "--check"], capture_output=True, text=True, env=env)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("corelocationcli", run.stdout.lower())
        install = (REPO / "install.sh").read_text(encoding="utf-8")
        self.assertIn("build_location_helper.sh", install)
        self.assertIn("NSLocationWhenInUseUsageDescription", (REPO / "package.json").read_text(encoding="utf-8"))
        self.assertIn("ITERBROW_LOCATION_HELPER", (REPO / "README.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
