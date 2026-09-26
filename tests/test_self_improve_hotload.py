#!/usr/bin/env python3
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ITER = ROOT / "iter"
TOOLS = ITER / "tools"
for path in (str(ITER), str(TOOLS)):
    if path not in sys.path:
        sys.path.insert(0, path)

from iterbrow_runtime.hotload_manager import IterHeartbeat


BASE = 'DESCRIPTION = "base"\n\ndef run():\n    return "base"\n'
CANDIDATE = 'DESCRIPTION = "fixed"\n\ndef run():\n    return "fixed"\n'


class SelfImproveHotloadIntegrationTests(unittest.TestCase):
    def test_ordinary_apply_and_failed_probation_restore_parent(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary)
            for name in ("tools", "transformations", "channels", "memory"):
                (runtime / name).mkdir(parents=True)
            target = runtime / "tools" / "sample.py"
            target.write_text(BASE, encoding="utf-8")
            old_cwd = Path.cwd()
            module_name = "self_improve_hotload_integration"
            try:
                os.chdir(runtime)
                spec = importlib.util.spec_from_file_location(module_name, TOOLS / "self_improve.py")
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                parent = module.HOTLOAD.active()
                parent_heartbeat = IterHeartbeat(runtime, "live-parent", pid=os.getpid())
                parent_heartbeat.write(parent["generation_id"], "cycle_complete", 0)
                result = json.loads(module.run(
                    action="apply",
                    target="tools/sample.py",
                    content=CANDIDATE,
                    description="repair sample behavior",
                ))
                self.assertEqual(result["status"], "probation")
                self.assertEqual(target.read_text(encoding="utf-8"), BASE)

                active = module.HOTLOAD.active()
                self.assertEqual(active["status"], "probation")
                snapshot = module.HOTLOAD.component_snapshot()
                self.assertEqual(
                    (snapshot["roots"]["tools"] / "sample.py").read_text(encoding="utf-8"),
                    CANDIDATE,
                )
                heartbeat = IterHeartbeat(runtime, "failed-candidate", pid=99)
                heartbeat.write(result["generation_id"], "error", 1, hard_floor_ok=False)
                recovered = module.HOTLOAD.supervisor_check(True, iter_pid=99)
                self.assertEqual(recovered["action"], "rolled_back")
                self.assertEqual(module.HOTLOAD.active()["generation_id"], result["rollback_target"])
                restored = module.HOTLOAD.component_snapshot()
                self.assertEqual(
                    (restored["roots"]["tools"] / "sample.py").read_text(encoding="utf-8"),
                    BASE,
                )
            finally:
                os.chdir(old_cwd)
                sys.modules.pop(module_name, None)


if __name__ == "__main__":
    unittest.main()
