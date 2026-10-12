#!/usr/bin/env python3
"""Deterministic OpenAI-compatible chat endpoint for end-to-end tests (no LLM).

Usage: fake_model.py PORT SCRIPT.json REQUESTS.jsonl

SCRIPT.json is a list of turns; each turn is a list of tool calls
{"name": ..., "arguments": {...}}.  Turn N answers the N-th request.  After
the script runs out the model idles with nop(wait_seconds=5).  Every request
is appended to REQUESTS.jsonl (message count, system prompt) so tests can
assert on what the agent was actually shown.

String arguments may contain {{memory_id}}: it is replaced with the id from
the most recent "REMEMBER-SUCCESS: stored <id>" tool result the agent has
seen, so a script can act on a memory whose id is minted at run time.
"""
import hashlib
import itertools
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT, SCRIPT, LOG = int(sys.argv[1]), sys.argv[2], sys.argv[3]
TURNS = json.load(open(SCRIPT))
COUNTER = itertools.count()
IDLE = [{"name": "nop", "arguments": {"wait_seconds": 5}}]


MEMORY_ID = re.compile(r"REMEMBER-SUCCESS: stored (\S+)")


def _last_memory_id(messages):
    found = None
    for message in messages:
        content = message.get("content")
        if isinstance(content, list):
            content = " ".join(str(part.get("text", part)) if isinstance(part, dict) else str(part)
                               for part in content)
        for match in MEMORY_ID.finditer(str(content or "")):
            found = match.group(1)
    return found


def _fill(value, memory_id):
    if isinstance(value, str) and "{{memory_id}}" in value:
        return value.replace("{{memory_id}}", memory_id or "NO-MEMORY-ID-YET")
    if isinstance(value, dict):
        return {key: _fill(item, memory_id) for key, item in value.items()}
    if isinstance(value, list):
        return [_fill(item, memory_id) for item in value]
    return value


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def _reply(self, payload):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _embeddings(self, body):
        """Deterministic 1024-d vectors: identical text -> identical vector."""
        texts = body.get("input") or []
        texts = [texts] if isinstance(texts, str) else texts
        data = []
        for index, text in enumerate(texts):
            seed = hashlib.sha256(str(text).encode("utf-8")).digest()
            vector = [((seed[i % 32] ^ (i * 31 % 251)) / 255.0) - 0.5 for i in range(body.get("dimensions", 1024))]
            data.append({"index": index, "embedding": vector})
        self._reply({"data": data, "model": body.get("model", "fake")})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path.rstrip("/").endswith("/embeddings"):
            return self._embeddings(body)
        n = next(COUNTER)
        with open(LOG, "a", encoding="utf-8") as log:
            log.write(json.dumps({
                "n": n,
                "n_messages": len(body["messages"]),
                "system": body["messages"][0]["content"] if body["messages"] else "",
                "tools": sorted(t["function"]["name"] for t in body.get("tools", [])),
            }) + "\n")
        turn = TURNS[n] if n < len(TURNS) else IDLE
        memory_id = _last_memory_id(body["messages"])
        calls = [{"id": "call_%d_%d" % (n, i), "type": "function",
                  "function": {"name": c["name"],
                               "arguments": json.dumps(_fill(c.get("arguments", {}), memory_id))}}
                 for i, c in enumerate(turn)]
        response = {"id": "fake-%d" % n, "object": "chat.completion", "created": 0, "model": "fake",
                    "choices": [{"index": 0, "finish_reason": "tool_calls",
                                 "message": {"role": "assistant", "content": None, "tool_calls": calls}}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}
        data = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
