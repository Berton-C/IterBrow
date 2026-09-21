import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _browser_bridge import call

DESCRIPTION = (
    "Advanced/raw escape hatch: send an arbitrary Chrome DevTools Protocol command to the attached tab "
    "(e.g. method='Network.enable' or method='Emulation.setDeviceMetricsOverride'). cdp_params must be a JSON "
    "object string. Only use this when the simpler browser_* tools do not cover what you need."
)


def run(method, cdp_params="{}"):
    params = json.loads(cdp_params) if cdp_params else {}
    # bridge call() has its own first param named "method"; the CDP method and
    # params ride inside the bridge payload (server: tabs.cdp(id, params.method, params.cdpParams)).
    result = call("cdp", _raw_params={"method": method, "cdpParams": params})
    return json.dumps(result)
