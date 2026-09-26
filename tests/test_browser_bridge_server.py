#!/usr/bin/env python3
import json
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BrowserBridgeServerTests(unittest.TestCase):
    def test_live_endpoint_cannot_be_unlinked_or_stolen(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as td:
            socket_path = Path(td) / "bridge.sock"
            script = textwrap.dedent(
                f"""
                const net = require('net');
                const {{ startBridgeServer }} = require({json.dumps(str(ROOT / 'bridge' / 'browser_bridge_server.js'))});
                const socketPath = {json.dumps(str(socket_path))};
                const tabs = {{ list: () => [{{ id: 7, title: 'owner' }}] }};

                function call(method) {{
                  return new Promise((resolve, reject) => {{
                    const client = net.createConnection(socketPath);
                    let data = '';
                    client.once('connect', () => client.write(JSON.stringify({{ method, params: {{}} }}) + '\\n'));
                    client.on('data', (chunk) => data += chunk.toString('utf8'));
                    client.once('end', () => resolve(JSON.parse(data)));
                    client.once('error', reject);
                  }});
                }}

                (async () => {{
                  const first = startBridgeServer(tabs, () => {{}}, socketPath);
                  const firstReady = await first.bridgeReady;
                  if (firstReady.status !== 'listening') throw new Error(JSON.stringify(firstReady));
                  const second = startBridgeServer({{ list: () => [{{ id: 8, title: 'intruder' }}] }}, () => {{}}, socketPath);
                  const secondReady = await second.bridgeReady;
                  if (secondReady.status !== 'conflict') throw new Error(JSON.stringify(secondReady));
                  const response = await call('getTabs');
                  console.log(JSON.stringify({{ firstReady, secondReady, response }}));
                  await new Promise((resolve) => first.close(resolve));
                }})().catch((error) => {{ console.error(error); process.exitCode = 1; }});
                """
            )
            result = subprocess.run(
                ["node", "-e", script],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            observed = json.loads(result.stdout.strip())
            self.assertEqual(observed["firstReady"]["status"], "listening")
            self.assertEqual(observed["secondReady"]["status"], "conflict")
            self.assertTrue(observed["response"]["ok"])
            self.assertEqual(observed["response"]["result"][0]["title"], "owner")


if __name__ == "__main__":
    unittest.main()
