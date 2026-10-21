"""Read private captured tool output; never repeat the producing action."""
import os
from pathlib import Path
import sys


ROOT = Path(os.getenv("ITER_DIR") or Path.cwd()).resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from iterbrow_runtime.tool_results import read_tool_output


DESCRIPTION = (
    'Read retained text. Give result_id or the original tool_call_id explicitly; never infer one. '
    'pointer: JSON pointer into captured tool JSON (empty pages exact text). offset: character index; '
    'limit 1..2000; follow next_offset until eof. Never reruns an action.'
)


def run(result_id="", tool_call_id="", pointer="", offset=0, limit=2000):
    return read_tool_output(ROOT, result_id=result_id, tool_call_id=tool_call_id,
                            pointer=pointer, offset=offset, limit=limit)
