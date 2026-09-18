# COS Command Center — Handoff Document

**For:** Haley (COS) + her Iter instance · **From:** Iter (this laptop) · **Date:** 2026-09-18
**TL;DR:** A personal ops-hub CRM for the COS role is built and live — Briefing, People, Tasks, Events, and a Signals feed are all working against a local JSON store. Two feed scanners (Mattermost, Gmail) are half-built: Mattermost is fully coded but unconfigured; Gmail is a skeleton. Remaining work = finish the Gmail scanner, configure both, and let real signals flow into the morning Briefing. Everything below is verified against the on-disk code as of writing — no claims from memory.

---

## 1. Inspiration & Design Intent

This was built so the COS of SingularityNET.io never drops a ball:

- **The anti-drop-ball backbone:** every contact, task, and event *must* carry a `next_step` + `next_step_due` (contacts) or `due` (tasks). The Briefing surfaces anything overdue or due soon. The system's job is to make inaction visible.
- **Signals · needs her eyes:** a feed of things that deserve her attention — Gmail items (incl. LinkedIn notification emails) and Mattermost mentions/replies/CEO-COO posts — collected by read-only scanners into `crm/data/captures.json`, rendered as cards in the Briefing.
- **Aesthetic:** cream palette, ✦ sigil, calm command-deck feel (her preference, confirmed by the user). One page, zero dependencies, opens from a local file.
- **Disk is the API:** all data lives in plain JSON under `crm/data/`. The page reads/writes those files; an Iter agent reads/writes them directly. No server, no database, no sync service — local-only by design.

## 2. What Exists (verified on disk 2026-09-18)

```
crm/
  index.html          # the whole app (~15KB, single file, no deps)
  data/
    schema.md          # canonical schema for all four JSON files
    contacts.json      # []  (empty — ready for real data)
    tasks.json         # []
    events.json        # []
    captures.json      # []  (signals land here)
  HANDOFF.md           # this file
private/crm/           # config folder (gitignored-style, local-only)
  README.txt           # connector setup instructions
iter/tools/
  mm_scan.py           # Mattermost scanner — FULLY IMPLEMENTED (REST v4, urllib)
  gmail_scan.py        # Gmail scanner — SKELETON only
```

**Working now (open `crm/index.html` in any browser):**

*Honest caveat (2026-09-18): in a plain browsed tab the page renders but has NO disk bridge — it can neither read nor write `crm/data/*.json` (live-probed `window.iterApi` = undefined in the open tab). Since all four JSONs are currently empty, the bridge-less empty state looks identical to the real quiet state. Disk JSONs are the source of truth; edit them directly (schema: `crm/data/schema.md`) until the page is opened in a bridged window.*
- **Briefing view** — overdue/soon tasks, hot relationships, upcoming events, empty state messaging, and the Signals section (renders whatever is in `captures.json`)
- **People / Tasks / Events** — full CRUD against the JSON files, with the next-step fields enforced
- **Persistence (design intent, not yet exercised end-to-end)** — page saves via `window.iterApi.crmWrite` → `crm:write` IPC (whitelist: the 4 CRM JSONs; `fs.writeFileSync` in main.js). The bridge is exposed only in the app's chrome views (sidebar/toolbar/tabstrip preloads), which no page can be opened in — so the write path is verified by code-read only. In browsed tabs the save bar will show `SAVE FAILED` on edit.

**Verified live 2026-09-17 and again 2026-09-18 post-restart:** the page renders, the Briefing shows the quiet state correctly, the Signals section appears (empty until scanners run).

## 3. Status Ledger (the honest four-state split)

| State | Item | Detail |
|---|---|---|
| ✅ Render verified / 🟡 disk round-trip NOT exercised | CRM page (Briefing/People/Tasks/Events) | in-browser render + in-memory CRUD verified 09-17/09-18; the disk save path needs the app bridge, which browsed tabs lack (probed 09-18). JSONs remain the source of truth |
| ✅ Built & verified live | Signals display in Briefing | renders `captures.json` cards; test cards confirmed rendering (in-memory only, then cleared) |
| ✅ Built & verified live | Data schemas | `crm/data/schema.md` is canonical |
| 🟡 Built but blocked on config | Mattermost scanner | `tools/mm_scan.py` is fully coded (REST v4 via urllib, read-only, NOAUTH-safe). Needs: `mm_token.txt`, `mm_server.txt`, `mm_watchers.txt` in `private/crm/` |
| 🔴 Skeleton — code needed | Gmail scanner | `tools/gmail_scan.py` registers the tool and handles NOAUTH, but the pull/filter/dedupe logic was never written. Needs: `google-auth` + `google-api-python-client` (pip), unread/inbox pull, signal filters, dedupe by message id, append to `captures.json` |
| 🔴 Blocked on human action | OAuth credentials | `private/crm/gmail_credentials.json` (Google OAuth *Desktop* client, Gmail API, console.cloud.google.com). `gmail_token.json` is created automatically on first authorized run — do not create manually |
| 🔴 Blocked on human action | LinkedIn notification setting | set LinkedIn notifications to **Individual emails** (not digest) so they arrive as discrete parseable emails |
| ⬜ Not started | First real scan runs | both scanners wired into the morning routine; she fine-tunes `mm_watchers.txt` over time |
| ⬜ Not started | Data entry | contacts/tasks/events are all empty; first session should add her real people |

## 4. Decisions Locked (do not re-litigate)

1. **Read-only, always.** Gmail scope is `gmail.readonly`; scanners never send, modify, or delete anything. Mattermost is read-only REST.
2. **No LinkedIn scraping.** LinkedIn personal APIs are marketing/talent-only; scraping violates ToS. LinkedIn signals come *only* via notification emails through Gmail. (One Gmail OAuth covers email + LinkedIn.)
3. **Local-only data.** Nothing leaves the machine. No cloud sync, no third-party services beyond the two read-only API pulls.
4. **Disk is the API.** JSON files in `crm/data/` are the single source of truth; the page and any Iter instance both read/write them directly.
5. **Every record carries a next step.** The backbone of the whole design; don't build views that let a record exist without one.

## 5. Decisions Open (hers to make)

- Page/app name (currently "COS Command Center" — renaming is a one-line title change)
- Watcher list (`mm_watchers.txt` — start with CEO/COO, tune over time)
- Signal thresholds: which emails count as "needs her eyes" (start: LinkedIn notifications + sender allowlist; refine)
- Task kinds / event types / contact tiers vocabulary in `schema.md` (extendable freely)

## 6. Safety Rails (inherited constraints)

- `gmail.readonly` scope only — never send/modify/delete mail
- Mattermost: personal access token, read-only endpoints only
- No LinkedIn API/scraping — email-only path
- All credentials live in `private/crm/`, never in `crm/` proper, never committed
- Scanner failures must be silent-safe (NOAUTH / network-down → skip, never crash the Briefing)

## 7. First Session Quickstart (15 minutes to first win)

1. **Open the app:** `crm/index.html` in a browser → you'll see the empty Briefing (all data files are empty — expected). To add real contacts *now*, edit `crm/data/contacts.json` directly (schema in `crm/data/schema.md`); the page's click-to-edit save needs the app bridge, which browsed tabs don't have (see §2 caveat).
2. **Mattermost (5 min):** Mattermost → Account Settings → Security → Personal Access Tokens → create token. Write three files in `private/crm/`: `mm_token.txt`, `mm_server.txt` (e.g. `https://yourteam.mattermost.cloud`), `mm_watchers.txt` (one username per line, start with CEO/COO).
3. **Gmail OAuth (5 min):** console.cloud.google.com → new project → enable **Gmail API** → OAuth consent screen (External, add her Google account as test user) → Credentials → **Desktop app** client → download JSON → save as `private/crm/gmail_credentials.json`.
4. **First authorized run** (her Iter): `gmail_scan` tool → browser opens once for consent → `gmail_token.json` saved automatically → first pull lands in `captures.json`.
5. **Check the Briefing:** Signals section now shows real items. LinkedIn: set notifications to Individual emails, then invite/message alerts flow into the same feed.

## 8. For Her Iter (machine notes)

- `tools/mm_scan.py`: real implementation — `urlopen` against Mattermost REST v4 `/api/v4/users/me/...` endpoints; returns NOAUTH-string when unconfigured; writes candidates to `crm/data/captures.json`; dedupe included. Read its docstring before extending.
- `tools/gmail_scan.py`: replace the `pending activation` return with real logic: pip install `google-auth google-auth-oauthlib google-api-python-client`; `InstalledAppFlow` + `credentials.json` → token cache at `private/crm/gmail_token.json`; pull recent inbox (label INBOX, unread-first), filter: from-LinkedIn (`*linkedin.com` senders) → high priority; apply her allowlist; dedupe by Gmail message id; append `{ts,
 raw, parsed}` objects per `schema.md`.
- **Integrity rule (inherited lesson):** never claim a file is written/scanned/done without checking it on disk in the same session. This doc's status ledger exists so you can trust it without re-verifying — but re-verify your own additions.
- **Failure mode is flap:** if chroma/memory stores are slow or down, work from `crm/data/*.json` + this doc; both are plain files, always readable.

## 9. Verification Recipes (trust but check)

1. **CRM page alive:** opens and renders empty-state in a browser tab (no bridge there, so 'renders' means chrome + empty state, not a data round-trip); disk integrity separately: `python3 -m json.tool crm/data/*.json`.
2. **Mattermost scanner:** with the three `private/crm/` files present, run the mm_scan tool → expect candidates appended to `captures.json` (or an honest no-new-items result).
3. **Gmail scanner:** after credentials + first authorized run, `private/crm/gmail_token.json` must exist and `captures.json` must grow; LinkedIn test: trigger a LinkedIn notification → next scan catches it.
4. **Everything is local:** unplug the network — the CRM page still opens and every view still works (only the two scans skip).

*End of handoff. Built with care by Iter (laptop instance), verified against disk 2026-09-18 10:35. Haley — this is yours now. Take good care of the next steps; the system exists so nothing important slips past you. ✦*
