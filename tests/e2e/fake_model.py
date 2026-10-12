#!/usr/bin/env python3
"""Deterministic OpenAI-compatible chat endpoint for end-to-end tests (no LLM).

Usage: fake_model.py PORT SCRIPT.json REQUESTS.jsonl

SCRIPT.json is a list of turns; each turn is a list of tool calls
{"name": ..., "arguments": {...}}.  Turn N answers the N-th request.  After
the script runs out the model idles with nop(wait_seconds=5).  Every request
is appended to REQUESTS.jsonl (message count, system prompt) so tests can
assert on what the agent was actually shown.
"""
import hashlib
import itertools
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT, SCRIPT, LOG = int(sys.argv[1]), sys.argv[2], sys.argv[3]
TURNS = json.load(open(SCRIPT))
COUNTER = itertools.count()
IDLE = [{"name": "nop", "arguments": {"wait_seconds": 5}}]


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
        calls = [{"id": "call_%d_%d" % (n, i), "type": "function",
                  "function": {"name": c["name"], "arguments": json.dumps(c.get("arguments", {}))}}
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
