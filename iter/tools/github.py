"""Read GitHub for ideas: search repositories, list a repository's files, read one file
(docs/milestones/M14_vault_and_foundry_loop.md E1). Unauthenticated, read-only; nothing is ever pushed.
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _files  # noqa: E402
from iterbrow_runtime.tool_results import ToolOutput, READ_WIRE_CHARS  # noqa: E402

DESCRIPTION = (
    'Read GitHub (read-only). action=search: query -> repos by stars; tree: repo=owner/name -> files; '
    "read: repo + path -> numbered lines. Credit what you adopt in the app's README. 10 searches a "
    'minute.'
)

USER_AGENT = "IterBrow"
TIMEOUT = 10
MAX_TREE = 400
REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def valid_repo(repo):
    return bool(REPO.match(str(repo or ""))) and ".." not in str(repo)


def valid_path(path):
    path = str(path or "").strip()
    return bool(path) and not path.startswith("/") and ".." not in path.split("/") and "\\" not in path


def raw_url(repo, path):
    return "https://raw.githubusercontent.com/%s/HEAD/%s" % (repo, urllib.parse.quote(path.strip("/")))


def parse_tree(data):
    """[(path, size)] for every file (blob) in a git tree response, sorted by path."""
    items = data.get("tree") if isinstance(data, dict) else None
    return sorted((item["path"], int(item.get("size") or 0)) for item in items or []
                  if isinstance(item, dict) and item.get("type") == "blob" and item.get("path"))


def format_search(data):
    """One line per repository of a search response."""
    lines = []
    for item in (data.get("items") if isinstance(data, dict) else None) or []:
        license_info = item.get("license") or {}
        spdx = license_info.get("spdx_id") if isinstance(license_info, dict) else None
        lines.append("%s ★%d — %s (%s) %s" % (
            item.get("full_name", "?"), int(item.get("stargazers_count") or 0),
            " ".join(str(item.get("description") or "").split()) or "(no description)",
            spdx if spdx and spdx != "NOASSERTION" else "no license", item.get("html_url", "")))
    return lines


class _RateLimited(Exception):
    pass


def _get(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.read(3_000_000).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        if error.code in (403, 429) and error.headers.get("X-RateLimit-Remaining") == "0":
            reset = error.headers.get("X-RateLimit-Reset")
            when = time.strftime("%H:%M:%S", time.localtime(int(reset))) if reset and reset.isdigit() else "a minute"
            raise _RateLimited(when)
        raise


def _cap(text):
    if len(text) <= READ_WIRE_CHARS:
        return text
    return text[:READ_WIRE_CHARS - 80].rsplit("\n", 1)[0] + "\n… cut at %d characters" % READ_WIRE_CHARS


def run(action, repo="", path="", query="", max_results="8"):
    action = str(action or "").strip()
    repo, path, query = str(repo or "").strip(), str(path or "").strip(), str(query or "").strip()
    if action not in ("search", "tree", "read"):
        return _files.input_error("ERROR: action is search, tree or read")
    if action == "search" and not query:
        return _files.input_error("ERROR: search needs a query")
    if action in ("tree", "read") and not valid_repo(repo):
        return _files.input_error("ERROR: repo is owner/name (got %r)" % repo)
    if action == "read" and not valid_path(path):
        return _files.input_error("ERROR: path is a file inside the repository, without .. (got %r)" % path)
    try:
        count = max(1, min(20, int(str(max_results or "8"))))
    except ValueError:
        return _files.input_error("ERROR: max_results is a number")
    try:
        if action == "search":
            body = _get("https://api.github.com/search/repositories?q=%s&sort=stars&per_page=%d"
                        % (urllib.parse.quote(query), count))
            lines = format_search(json.loads(body))
            return "\n".join(lines) if lines else "NO RESULTS: %s" % query
        if action == "tree":
            files = parse_tree(json.loads(_get("https://api.github.com/repos/%s/git/trees/HEAD?recursive=1" % repo)))
            lines = ["%s  %d" % item for item in files[:MAX_TREE]]
            if len(files) > MAX_TREE:
                lines.append("… and %d more files" % (len(files) - MAX_TREE))
            return _cap("\n".join(lines)) if lines else "NO FILES in %s" % repo
        text = _get(raw_url(repo, path))
        rows = text.splitlines()
        body = _cap("\n".join(_files.numbered(rows, 1)))
        shown = sum(1 for line in body.split("\n") if re.match(r"^\s*\d+\| ", line))
        return "%s:%s (lines 1–%d of %d)\n%s" % (repo, path, min(shown, len(rows)), len(rows), body)
    except _RateLimited as limited:
        what = "10 searches a minute" if action == "search" else "60 requests an hour from this address"
        return ToolOutput("RATE-LIMITED: GitHub allows %s without a token; try again at %s" % (what, limited),
                          False, state="failed")
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return _files.input_error("ERROR: not found on GitHub: %s" % (repo + (":" + path if path else "") or query))
        return ToolOutput("FAILED: GitHub answered HTTP %d" % error.code, False, state="failed")
    except (urllib.error.URLError, OSError, ValueError) as error:
        return ToolOutput("FAILED: GitHub could not be reached (%s)" % error, False, state="failed")
