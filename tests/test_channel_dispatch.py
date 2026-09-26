import importlib.util
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_SEND = REPO_ROOT / "iter" / "tools" / "send.py"


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ChannelDispatchTests(unittest.TestCase):
    def test_send_normalizes_whitespace_and_uses_its_own_generation(self):
        with tempfile.TemporaryDirectory() as raw:
            generation = Path(raw) / "generation"
            tools = generation / "tools"
            channels = generation / "channels"
            tools.mkdir(parents=True)
            channels.mkdir()
            (tools / "send.py").write_bytes(SOURCE_SEND.read_bytes())
            (channels / "electron_ui.py").write_text(
                "def send(content):\n"
                "    (OUT / 'result.txt').write_text(content, encoding='utf-8')\n",
                encoding="utf-8",
            )
            # Give the relocated channel its output destination without relying
            # on cwd or the source checkout.
            channel_path = channels / "electron_ui.py"
            channel_path.write_text(
                "from pathlib import Path\n"
                f"OUT = Path({str(generation)!r})\n"
                + channel_path.read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            module = load_module(tools / "send.py", "relocated_send")
            self.assertEqual(
                module.run("\nelectron_ui\t", "round trip"),
                "SUCCESS",
            )
            self.assertEqual(
                (generation / "result.txt").read_text(encoding="utf-8"),
                "round trip",
            )

    def test_send_rejects_path_traversal_after_normalization(self):
        module = load_module(SOURCE_SEND, "source_send")
        self.assertEqual(module.run("../electron_ui", "no"), "Invalid channel: ../electron_ui")


if __name__ == "__main__":
    unittest.main()
