#!/usr/bin/env python3
"""M16-B1..B4: the model settings panel — provider presets, fetch the models and click one, test the connection
with a real chat ping, save & apply; keys never leave the main process.

Spec: docs/milestones/M16_shell_from_eaos.md section B. bridge/model_settings.js is pure and runs in node with
a fake fetch (m16_support.settings_node); the panel and main.js wiring are checked by source.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m16_support import pending, require_m16, settings_node, source  # noqa: E402

# Keyed by URL suffix: "/api/v1/…" is OpenRouter's; api.anthropic.com/v1/models has no fake (HTTP 404).
MODELS = json.dumps({"GET /api/v1/models": {"status": 200, "json": {"data": [
    {"id": "z-ai/glm-5.3", "pricing": {"prompt": "0.0000005", "completion": "0.000002"}},
    {"id": "deepseek/deepseek-v4.1-flash", "pricing": {"prompt": "0.0000001", "completion": "0.0000004"}},
    {"id": "anthropic/claude-sonnet-5.5"}]}},
    "POST /api/v1/chat/completions": {"status": 200, "json": {"choices": [{"message": {"role": "assistant", "content": "Hello from the model."}}],
                                                          "usage": {"prompt_tokens": 12, "completion_tokens": 5}}}})


class ProviderTests(unittest.TestCase):
    """M16-B1"""

    def test_presets_and_the_environment_iter_gets(self):
        out = settings_node("""
out.ids = Object.keys(S.PROVIDERS);
out.presets = Object.fromEntries(Object.entries(S.PROVIDERS).map(([id, p]) => [id, [p.endpoint, p.key, typeof p.label, typeof p.note]]));
const settings = { provider: 'openrouter', openrouter: { endpoint: 'https://openrouter.ai/api/v1', model: 'deepseek/deepseek-v4.1-flash', apiKey: 'sk-or-1' },
  openai: { model: 'gpt-6-luna', apiKey: 'sk-oa', reasoning: 'low' }, lmstudio: { endpoint: 'http://127.0.0.1:1234/v1', model: 'qwen/qwen3.8-27b' } };
out.openrouter = S.envFor(settings);
out.openai = S.envFor({ ...settings, provider: 'openai' });
out.lmstudio = S.envFor({ ...settings, provider: 'lmstudio' });
out.ollama = S.envFor({ ...settings, provider: 'ollama', ollama: { model: 'llama4' } });
out.anthropic = S.envFor({ ...settings, provider: 'anthropic', anthropic: { model: 'claude-sonnet-5.5', apiKey: 'sk-ant' } });
try { S.envFor({ ...settings, provider: 'anthropic', anthropic: { model: 'x' } }); out.noKey = 'allowed'; } catch (e) { out.noKey = e.message; }
try { S.envFor({ ...settings, provider: 'openai', openai: { model: 'gpt-6-luna', apiKey: '' } }); out.noOaKey = 'allowed'; } catch (e) { out.noOaKey = e.message; }
""")
        self.assertEqual(out["ids"], ["openrouter", "openai", "lmstudio", "ollama", "anthropic", "custom"])
        for pid, (endpoint, key, label, note) in out["presets"].items():
            self.assertEqual((label, note), ("string", "string"), pid)
        self.assertEqual(out["presets"]["openrouter"][:2], ["https://openrouter.ai/api/v1", True])
        self.assertEqual(out["presets"]["openai"][:2], ["https://api.openai.com/v1", True])
        self.assertEqual(out["presets"]["lmstudio"][:2], ["http://127.0.0.1:1234/v1", False])
        self.assertEqual(out["presets"]["ollama"][:2], ["http://localhost:11434/v1", False])
        self.assertEqual(out["presets"]["anthropic"][:2], ["https://api.anthropic.com/v1", True])
        self.assertEqual(out["presets"]["custom"][:2], ["", False])
        self.assertEqual(out["openrouter"], {"BASE_URL": "https://openrouter.ai/api/v1", "LLM_MODEL": "deepseek/deepseek-v4.1-flash",
                                             "LLM_PROVIDER": "openrouter", "LLM_REASONING_EFFORT": "", "AI_API_KEY": "sk-or-1"})
        self.assertEqual(out["openai"], {"BASE_URL": "https://api.openai.com/v1", "LLM_MODEL": "gpt-6-luna", "LLM_PROVIDER": "openai",
                                         "LLM_REASONING_EFFORT": "low", "AI_API_KEY": "sk-oa"})
        self.assertEqual(out["lmstudio"]["AI_API_KEY"], "lm-studio"); self.assertEqual(out["lmstudio"]["LLM_PROVIDER"], "lmstudio")
        self.assertEqual(out["ollama"]["BASE_URL"], "http://localhost:11434/v1"); self.assertEqual(out["ollama"]["AI_API_KEY"], "ollama")
        self.assertEqual(out["anthropic"]["LLM_PROVIDER"], "anthropic", "the loop treats everything but openai as compatible")
        self.assertIn("API key", out["noKey"]); self.assertIn("Settings", out["noKey"])
        self.assertIn("OpenAI API key", out["noOaKey"])

    def test_main_js_uses_env_for_and_keeps_the_embedding_key(self):
        require_m16()
        main = source("main.js")
        self.assertIn("model_settings", main)
        self.assertIn("envFor(", main)
        self.assertNotIn("function modelConfig", main)
        self.assertIn("OPENROUTER_API_KEY: (settings.openrouter && settings.openrouter.apiKey)", main)


class FetchAndTestTests(unittest.TestCase):
    """M16-B2"""

    def test_fetch_models_lists_ids_and_keeps_openrouter_pricing(self):
        out = settings_node("""
out.ok = await S.fetchModels('https://openrouter.ai/api/v1', 'sk-or-1', fakeFetch);
out.auth = calls[0].auth; out.url = calls[0].url;
out.bad = await S.fetchModels('https://api.anthropic.com/v1', 'sk-ant', fakeFetch);
out.notUrl = await S.fetchModels('nope', '', fakeFetch);
out.noFetch = await S.fetchModels('https://x.example/v1', '', null);
""", MODELS)
        self.assertTrue(out["ok"]["ok"]); self.assertEqual(out["ok"]["status"], 200)
        self.assertEqual(out["ok"]["models"], ["anthropic/claude-sonnet-5.5", "deepseek/deepseek-v4.1-flash", "z-ai/glm-5.3"])
        self.assertEqual(out["ok"]["pricing"]["z-ai/glm-5.3"], {"input": 0.5, "output": 2.0}, "USD per 1M tokens")
        self.assertNotIn("anthropic/claude-sonnet-5.5", out["ok"]["pricing"])
        self.assertEqual(out["auth"], "Bearer sk-or-1"); self.assertEqual(out["url"], "https://openrouter.ai/api/v1/models")
        self.assertFalse(out["bad"]["ok"]); self.assertEqual(out["bad"]["status"], 404); self.assertEqual(out["bad"]["models"], [])
        self.assertFalse(out["notUrl"]["ok"]); self.assertIn("http(s)", out["notUrl"]["error"])
        self.assertFalse(out["noFetch"]["ok"])

    def test_test_connection_pings_the_model_and_drops_what_it_refuses(self):
        out = settings_node("""
out.full = await S.testConnection({ endpoint: 'https://openrouter.ai/api/v1', key: 'sk', model: 'deepseek/deepseek-v4.1-flash', reasoning: 'off' }, fakeFetch);
out.ping = calls.find((c) => c.method === 'POST');
out.listOnly = await S.testConnection({ endpoint: 'https://openrouter.ai/api/v1', key: 'sk', model: '' }, fakeFetch);
""", MODELS)
        self.assertTrue(out["full"]["ok"])
        self.assertTrue(out["full"]["text"].startswith("ok — models: 3 listed"), out["full"]["text"])
        self.assertIn("chat: answered", out["full"]["text"]); self.assertIn("Hello from the model", out["full"]["text"])
        self.assertEqual(out["full"]["reply"], "Hello from the model."); self.assertEqual(out["full"]["dropped"], [])
        self.assertIsInstance(out["full"]["ms"], (int, float))
        self.assertEqual(out["ping"]["body"]["model"], "deepseek/deepseek-v4.1-flash")
        self.assertEqual(len(out["ping"]["body"]["messages"]), 1); self.assertLessEqual(out["ping"]["body"].get("max_tokens", 0), 64)
        self.assertTrue(out["listOnly"]["ok"]); self.assertIn("models: 3 listed", out["listOnly"]["text"]); self.assertIsNone(out["listOnly"]["reply"])
        refuses = json.dumps({"GET /v1/models": {"status": 200, "json": {"data": [{"id": "gpt-6-luna"}]}},
                              "POST /v1/chat/completions": [
                                  {"status": 400, "json": {"error": {"message": "Unsupported parameter: 'max_tokens' is not supported with this model.", "param": "max_tokens", "code": "unsupported_parameter"}}},
                                  {"status": 200, "json": {"choices": [{"message": {"content": "ok"}}]}}]})
        out = settings_node("""
out.r = await S.testConnection({ endpoint: 'https://api.openai.com/v1', key: 'sk', model: 'gpt-6-luna' }, fakeFetch);
out.posts = calls.filter((c) => c.method === 'POST').map((c) => Object.keys(c.body).sort());
""", refuses)
        self.assertTrue(out["r"]["ok"]); self.assertEqual(out["r"]["dropped"], ["max_tokens"])
        self.assertIn("max_tokens", out["posts"][0]); self.assertNotIn("max_tokens", out["posts"][1])
        down = json.dumps({"GET /v1/models": {"status": 401, "json": {"error": "bad key"}}})
        out = settings_node("""out.r = await S.testConnection({ endpoint: 'https://openrouter.ai/api/v1', key: 'bad', model: 'x' }, fakeFetch);""", down)
        self.assertFalse(out["r"]["ok"]); self.assertIn("401", out["r"]["text"])

    def test_main_js_exposes_fetch_and_test(self):
        require_m16()
        main = source("main.js")
        self.assertIn("settings:fetchModels", main); self.assertIn("settings:test", main)
        self.assertRegex(main, r"net\.fetch|fetch\b")
        preload = source("preload.js")
        self.assertIn("fetchModels", preload); self.assertIn("testConnection", preload)


class PanelTests(unittest.TestCase):
    """M16-B3"""

    def test_one_panel_for_every_provider(self):
        require_m16()
        html = source("renderer/index.html")
        for pid in ("panel-openrouter", "panel-openai", "panel-lmstudio"):
            self.assertNotIn('id="%s"' % pid, html, "the three provider blocks became one panel")
        for ident in ("settings-endpoint", "settings-model-select", "settings-model", "settings-key", "btn-settings-fetch", "btn-settings-test",
                      "btn-settings-apply", "settings-test-result", "oa-reasoning", "oa-price"):
            self.assertIn('id="%s"' % ident, html, ident)
        self.assertIn("stored — leave empty to keep it", html + source("renderer/renderer.js"))
        js = source("renderer/renderer.js")
        self.assertIn("fetchModels", js); self.assertIn("testConnection", js)
        self.assertRegex(js, r"settings-model-select[^\n]*change|modelSelect\.addEventListener\('change'", "click one → it is the model")
        self.assertIn("Save & apply", html)

    def test_apply_restarts_a_running_iter(self):
        require_m16()
        main = source("main.js")
        block = main[main.index("ipcMain.handle('settings:save'"):main.index("ipcMain.handle('settings:save'") + 2500]
        # main.js's stop/start are stopIter()/startIterWithAtomspace() (there is no stopIterProcess).
        self.assertRegex(block, r"stopIter\w*\(\)[\s\S]*startIter\w*\(\)", "running Iter restarts with the new route")
        self.assertRegex(block, r"if \(iterProcess\b|iterProcess &&", "a stopped Iter is left stopped")


class KeysStayHomeTests(unittest.TestCase):
    """M16-B4"""

    def test_panel_state_carries_no_key_and_apply_provider_keeps_it(self):
        out = settings_node("""
const stored = { provider: 'openrouter', openrouter: { endpoint: 'https://openrouter.ai/api/v1', model: 'a', apiKey: 'sk-or-1', models: ['a', 'b'], pricing: { a: { input: 1, output: 2 } } },
  openai: { model: 'gpt-6-luna', apiKey: 'sk-oa', reasoning: 'medium' }, vault: '/v', keepHistory: true };
out.state = S.panelState(stored);
out.text = JSON.stringify(out.state);
out.kept = S.applyProvider(stored, { provider: 'openrouter', openrouter: { endpoint: 'https://openrouter.ai/api/v1', model: 'b', apiKey: '' } });
out.replaced = S.applyProvider(stored, { provider: 'openai', openai: { model: 'gpt-6-sol', apiKey: 'sk-new', reasoning: 'high' } });
out.fresh = S.applyProvider({}, { provider: 'ollama', ollama: { model: 'llama4' } });
""")
        self.assertNotIn("sk-", out["text"], "no key reaches the renderer")
        self.assertEqual(out["state"]["provider"], "openrouter")
        self.assertEqual(out["state"]["providers"]["openrouter"]["hasKey"], True)
        self.assertEqual(out["state"]["providers"]["openrouter"]["models"], ["a", "b"])
        self.assertEqual(out["state"]["providers"]["lmstudio"]["hasKey"], False)
        self.assertEqual(out["state"]["providers"]["lmstudio"]["endpoint"], "http://127.0.0.1:1234/v1", "a missing entry shows the preset")
        self.assertEqual(out["state"]["providers"]["openai"]["reasoning"], "medium")
        self.assertEqual(out["kept"]["openrouter"]["apiKey"], "sk-or-1", "an empty key keeps the stored one")
        self.assertEqual(out["kept"]["openrouter"]["model"], "b"); self.assertEqual(out["kept"]["openrouter"]["models"], ["a", "b"])
        self.assertEqual((out["kept"]["vault"], out["kept"]["keepHistory"]), ("/v", True), "other settings untouched")
        self.assertEqual(out["replaced"]["openai"]["apiKey"], "sk-new"); self.assertEqual(out["replaced"]["provider"], "openai")
        self.assertEqual(out["replaced"]["openrouter"]["apiKey"], "sk-or-1", "the other provider's route is kept")
        self.assertEqual(out["fresh"]["ollama"]["endpoint"], "http://localhost:11434/v1")

    def test_main_js_never_sends_or_logs_a_key(self):
        require_m16()
        main = source("main.js")
        load = main[main.index("ipcMain.handle('settings:load'"):main.index("ipcMain.handle('settings:load'") + 1200]
        self.assertIn("panelState(", load)
        self.assertNotIn("...settings", load, "the raw settings (with keys) no longer go to the renderer")
        for name in ("settings:fetchModels", "settings:test"):
            block = main[main.index("ipcMain.handle('%s'" % name):main.index("ipcMain.handle('%s'" % name) + 800]
            self.assertRegex(block, r"resolveKey|storedKey|apiKey", name + " resolves the stored key in main")
        self.assertNotIn("apiKey", main[main.index("pushLog(`[iter] started"):main.index("pushLog(`[iter] started") + 200])


if __name__ == "__main__":
    unittest.main()
