# The five-app foundry benchmark

Does IterBrow build apps that work the first time and keep working when changed? `scripts/foundry_bench/bench.py`
asks Iter for five small apps (`briefs.json`: todo, pomodoro, notes, convert, kanban), then checks each one
itself on the real page, the same way every time. Spec: `docs/milestones/M14_vault_and_foundry_loop.md` G.

## Running it

1. Start IterBrow, choose an apps folder (Apps ▸ Choose apps folder…), pick the model in Settings, and press
   **Start** so Iter is cycling (the bench checks its heartbeat and refuses to start otherwise).
2. Remove any earlier `todo`, `pomodoro`, `notes`, `convert`, `kanban` folders from the apps folder (the bench
   refuses to start while they exist) and make sure nothing is waiting in Iter's inbox.
3. From the repo:

   ```
   ITER_DIR="$PWD/iter" iter/.venv/bin/python3 scripts/foundry_bench/bench.py
   ```

   `--app todo` runs one brief; `--no-iterate` skips the second phase; `--model NAME` labels the run;
   `--baseline` tags it as the "before" run of a change you want to compare.

The bench moves on only after 10 minutes with no new reply from Iter (an hour at most per phase), so a build in
progress is never cut off by the next ask. Leave IterBrow alone while it runs.
Results land in `docs/bench/<date>-<model>.json` and a table is printed.

## What the numbers mean

- A **report** is evidence, not words: a passing `app_probe` of the app in Iter's own record, followed by a
  reply. A progress note that merely mentions the probe is not a report.
- **built**: the brief's own probe passed on the first check after Iter reported (the app's storage is
  cleared first, only its `iter:<id>:` keys).
- **kept**: after the iteration ask (a dark-mode toggle), the same probe still passes. `-` = not run.
- **theatre**: messages Iter sent with no tool result since its previous message — progress notes. The
  target is 0 (a question you'd need to answer counts too; the briefs need none).
- cycles, tools, cards, minutes: how much the loop did to get there. Cards should be 1–2 (the fork card,
  the offer card).

The asks name the element ids the probes use, so a probe written in advance can check whatever Iter builds.
An app that ignores the ids, or keeps its state outside `iter:<id>:` keys, fails — that is a finding about
following a brief, not a flaky test.
