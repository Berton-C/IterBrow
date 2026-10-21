import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _browser_bridge import call, refused

DESCRIPTION = (
    'Raw Chrome DevTools Protocol command to the attached tab (e.g. method=Network.enable; cdp_params: '
    'JSON object string), when browser_* tools do not cover it.'
)


def run(method, cdp_params="{}"):
    params = json.loads(cdp_params) if cdp_params else {}
    # bridge call() has its own first param named "method"; the CDP method and
    # params ride inside the bridge payload (server: tabs.cdp(id, params.method, params.cdpParams)).
    result = call("cdp", _raw_params={"method": method, "cdpParams": params})
    if refused(result):
        return result
    return json.dumps(result)
