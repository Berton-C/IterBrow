"""
Recap / Episode Summarization System.

Detects unrecapped episodes in history.metta and signals for summarization.
Also injects existing recap summaries into the system message so the agent
has self-awareness of what it's been doing.

How it works:
1. Reads history.metta line count and compares to last-recapped line count
   stored in ./memory/recap/.recap_state
2. If there are new unrecapped lines, writes ./memory/recap/.recap_needed
   flag with details about how many lines need recapping
3. Reads all JSON episode files from ./memory/recap/ and injects a summary
   block into the system message so the agent can see its episode history
4. The agent (LLM) then performs the actual summarization by reading the
   episode data via the episodes tool and writing JSON files
"""
import os, json

DESCRIPTION = "Episode recap: segments completed tasks into episode records and injects a recap of recent episodes."

HISTORY_PATH = "history.metta"
RECAP_DIR = "memory/recap"
STATE_PATH = os.path.join(RECAP_DIR, ".recap_state")
FLAG_PATH = os.path.join(RECAP_DIR, ".recap_needed")

# Minimum lines of new history before triggering a recap
RECAP_THRESHOLD = 20

def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False

def _read_file(path):
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except Exception:
        return ""

def _count_lines(path):
    try:
        with open(path, "r") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0

def _load_state():
    """Load the last-recapped line count."""
    if _exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r") as f:
                return int(f.read().strip())
        except Exception:
            return 0
    return 0

def _save_state(count):
    try:
        with open(STATE_PATH, "w") as f:
            f.write(str(count))
    except Exception:
        pass

def _list_episode_files():
    """List episode JSON files without glob."""
    files = []
    try:
        for entry in os.listdir(RECAP_DIR):
            if entry.startswith("episode_") and entry.endswith(".json"):
                files.append(os.path.join(RECAP_DIR, entry))
    except Exception:
        pass
    return sorted(files)

def _check_recap_needed():
    """Check if new episodes need recapping. Write flag if so."""
    total_lines = _count_lines(HISTORY_PATH)
    recapped_lines = _load_state()
    new_lines = total_lines - recapped_lines
    
    if new_lines >= RECAP_THRESHOLD:
        lines_info = "New lines: {} (lines {}-{} of {} total)\n"
        lines_info = lines_info.format(new_lines, recapped_lines + 1, total_lines, total_lines)
        lines_info += "Use episodes tool to read the new history, then create recap JSON files.\n"
        lines_info += "JSON format: {\"e\": episode_number, \"s\": short_summary, \"t\": optional_type}\n"
        lines_info += "  t is an optional typed-memory tag (fact/belief/value/todo/preference) - omit if not applicable.\n"
        lines_info += "Save each episode as ./memory/recap/episode_NNNN.json (new file only - existing episodes are immutable, overwrites are blocked).\n"
        lines_info += "After creating new episodes, call rebuild_tiers to refresh the tier pyramid - never hand-edit memory/tiers/ files."
        try:
            with open(FLAG_PATH, "w") as f:
                f.write(lines_info)
        except Exception:
            pass
    else:
        # Clear flag if exists
        if _exists(FLAG_PATH):
            try:
                os.remove(FLAG_PATH)
            except Exception:
                pass

def _load_episodes():
    """Load all episode JSON files from recap directory."""
    episodes = []
    for fpath in _list_episode_files():
        try:
            with open(fpath, "r") as f:
                ep = json.loads(f.read())
                episodes.append(ep)
        except Exception:
            continue
    return episodes

def _format_recap_block(episodes):
    """Format episodes into a compact summary block for system message.

    Real on-disk schema (verified against live episode_*.json): {"e" or
    "id": episode_number, "s": short_summary, optional "t": type}. Falls
    back to the older, more verbose {title, start_time, ...} shape too, in
    case any episode was ever written in that form."""
    if not episodes:
        return ""

    lines = ["## Episode Recap ({} episodes)".format(len(episodes))]
    for ep in episodes:
        num = ep.get("e", ep.get("id", "?"))
        summary = ep.get("s", ep.get("summary", ""))
        mem_type = ep.get("t", "")
        title = ep.get("title", "")

        header = "### E{}".format(num)
        if title:
            header += ": {}".format(title)
        if mem_type:
            header += " [{}]".format(mem_type)
        lines.append(header)
        if summary:
            lines.append(summary)

        themes = ep.get("themes", [])
        if themes:
            lines.append("Themes: {}".format(", ".join(themes)))

        notable = ep.get("notable_steps", [])
        if notable:
            for step in notable[:3]:  # max 3 per episode
                lines.append("  - {}".format(step))
        lines.append("")

    return "\n".join(lines)

def transform(messages, tools):
    try:
        if not messages:
            return messages, tools
        
        # Ensure recap directory exists
        if not _exists(RECAP_DIR):
            try:
                os.mkdir(RECAP_DIR)
            except Exception:
                pass
        
        # Check if recap is needed (side-effect: may write/clear flag)
        _check_recap_needed()
        
        # Load existing episodes and inject into system message
        episodes = _load_episodes()
        if episodes:
            recap_block = _format_recap_block(episodes)
            if recap_block:
                first_msg = messages[0]
                if isinstance(first_msg, dict):
                    content = first_msg.get("content", "")
                    if isinstance(content, str):
                        first_msg["content"] = content.rstrip() + "\n\n" + recap_block
                    elif isinstance(content, list):
                        first_msg["content"] = content + [{"type": "text", "text": "\n\n" + recap_block}]
        
    except Exception:
        pass
    
    return messages, tools
