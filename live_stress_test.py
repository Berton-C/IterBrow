import json
import os
import socket
import sys

SOCKET_PATH = os.environ.get("ITER_METTA_SOCKET", "/tmp/iter-metta-bridge.sock")


def call(method, params=None, timeout=15.0):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect(SOCKET_PATH)
    s.sendall((json.dumps({"method": method, "params": params or {}}) + "\n").encode())
    buf = b""
    while b"\n" not in buf:
        chunk = s.recv(1 << 20)
        if not chunk:
            break
        buf += chunk
    s.close()
    line, _, _ = buf.partition(b"\n")
    return json.loads(line.decode())


st = call("status")
print("BEFORE status:", json.dumps(st))

N = 1600
added = 0
failed = 0
for i in range(N):
    r = call("run", {"code": f"!(add-atom &self (StressTest triefix{i} {i}))"})
    if r.get("ok"):
        added += 1
    else:
        failed += 1
        if failed <= 5:
            print("ADD FAILED:", r)

print(f"added={added} failed={failed}")

# Now enumerate/query back -- this is exactly the read-back path that
# decodes trie key ids and used to corrupt/panic past 1024 stored keys.
r = call("run", {"code": "!(match &self (StressTest $label $n) $n)"})
print("QUERY ok:", r.get("ok"))
if r.get("ok"):
    result_str = r["result"]
    # crude count of returned bindings
    count = result_str.count("triefix") if "triefix" not in result_str else None
    print("QUERY result length (chars):", len(result_str))
    print("QUERY result sample (first 300 chars):", result_str[:300])
else:
    print("QUERY ERROR:", r.get("error"))

st2 = call("status")
print("AFTER status:", json.dumps(st2))
print("LIVE_STRESS_TEST_DONE")
