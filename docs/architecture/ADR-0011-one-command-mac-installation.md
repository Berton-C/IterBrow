# ADR-0011: One-command Mac installation and verified readiness

- Status: accepted
- Date: 2026-09-22
- Atlas scope: DIST-1, STATE-1, LIFE-1, QA-1, MAGIC-1

## Context

IterBrow's product promise begins before the first window opens. A new Mac user
must not need to understand Homebrew, Node, Python virtual environments,
Electron, Hyperon, sockets, or Iter process ownership before experiencing the
product.

The current root `install.sh` is a useful developer bootstrap, but it is not the
distribution contract. It installs source dependencies and optional development
tools, writes application scaffolding into the checkout, and then asks the user
to run `npm start`, configure a provider, and press Start. It does not resume
from an explicit stage ledger, distinguish code upgrades from user-state
migration, launch exactly one owner, or prove that the app, authoritative
AtomSpace, and Iter are healthy. The packaged application also bootstraps a
state-free writable workspace, but currently requires a separately provisioned
Python environment.

Treating either path as already "one shot" would turn installation success into
an unsupported claim.

## Implementation status — 2026-09-26

The first lifecycle slice is now operational without changing the readiness
contract below:

- a standalone `install.sh install` acquires the full branch, installs locked
  Electron/Python dependencies, repairs the pinned Hyperon 0.2.10 trie defect,
  and proves disposable journal crash/replay before launch;
- `repair` checkpoints manifest-declared state and rebuilds managed runtimes;
- `update` checkpoints state and secrets, builds and verifies new code in a
  sibling staging directory, restores state into that staged code, and only
  then swaps directories while retaining the exact prior installation; and
- `uninstall` preserves a reconstructable mode-`600` state archive before
  removing an installed copy.

The stock arm64 and x86_64 CPython 3.12 macOS Hyperon binaries are detected by
immutable extension hashes before native execution, avoiding their fatal
`space_iterate` path. The repaired build is accepted only after exact binding,
absent-belief, and 2,500-atom enumeration checks.

Still open from the full DIST-1 matrix: an interrupted-stage resume ledger,
Intel-Mac execution, signed/notarized release artifacts, automatic live-app
handoff during update, and a post-onboarding `assistant_ready` round trip. Until
those pass, `installed` is the strongest unattended terminal claim.

## Decision

### One user entry point

The supported Mac path is one downloaded installer script and one invocation.
The script may ask only for unavoidable macOS authority and for choices that
change product behavior. Provider credentials are entered through IterBrow's
private in-app onboarding surface, never as shell arguments or installer log
content.

The installer owns the journey through launch and verification. It does not end
with instructions to run a second command.

### Explicit readiness states

The installer reports three distinct states:

1. `installed`: versioned program files and the managed runtime exist.
2. `runtime_ready`: exactly one IterBrow owner is visible, the browser bridge is
   owned by it, and the authoritative AtomSpace reports a ready epoch, integer
   commit, state hash, and declared seeds.
3. `assistant_ready`: Iter is running on the stable generation and completes one
   labeled durable chat round trip after provider onboarding.

The user-facing "ready" or "success" claim requires `assistant_ready`. Before a
credential exists, the app may accurately say that installation is complete and
provider onboarding is required; it may not claim that Iter is responsive.

### Staged, resumable transaction

Each material stage has an identifier, input/version digest, start record,
completion evidence, and bounded rollback or retry instruction in a local
installer ledger. Re-running the installer:

- skips a stage only when its current evidence still verifies;
- retries an interrupted or failed stage without duplicating ownership;
- never interprets a partially created workspace as an empty new install;
- never deletes or overwrites user state to repair program files; and
- retains a redacted diagnostic log that the user can inspect or share.

The stage order is:

```text
preflight and architecture
  -> acquire/verify exact program version
  -> install minimal managed runtime
  -> verify state boundary and checkpoint existing state
  -> install or upgrade program code
  -> verify Python/Hyperon and Electron assets
  -> launch exactly one owner
  -> prove runtime_ready
  -> private provider onboarding when needed
  -> prove assistant_ready
```

### Core versus optional dependencies

The default path installs only what the shipped product needs. SWI-Prolog,
PeTTa development packages, Godot, test tooling, and repository-development
utilities are opt-in developer extras and cannot delay, fail, or enlarge the
default install.

Dependency versions come from repository-owned version/lock files. JavaScript
installation uses the committed lockfile. The Python environment is verified by
imports and a real disposable Hyperon probe, not merely by a successful package
manager exit. Apple Silicon and Intel-compatible execution are detected before
artifacts are selected.

### Code, state, and secrets remain separate

ADR-0007 remains authoritative:

- program artifacts are versioned and replaceable;
- one per-user writable workspace owns cognition and application state;
- secrets remain in the non-portable private boundary; and
- upgrades never merge a new template over an established workspace.

An upgrade checkpoints the manifest-approved portable state and records the
current program version before changing code. Failure restores the prior program
version and leaves the same workspace intact. State-schema migration must have
its own forward and rollback evidence; it cannot be hidden inside a code copy.

### Single ownership and health acceptance

The installer uses the existing Electron single-instance boundary and canonical
state-owner lock. It must distinguish "the requested instance became healthy"
from "some socket or process already exists." A responsive foreign checkout is
left untouched and reported clearly.

Acceptance consumes product surfaces rather than duplicating their policy:

- Electron single-instance ownership;
- checkout/application-scoped browser bridge identity;
- AtomSpace `status` with ready epoch/commit/hash;
- stable-generation Iter process/heartbeat evidence; and
- the durable sidebar chat journal for the labeled final round trip.

Installer logic may coordinate these checks, but it does not become a second
lifecycle supervisor or a cognitive authority.

### Distribution maturity

The first DIST-1 implementation may build or install the current repository
artifact, but partner-ready distribution additionally requires a release-owned
artifact, checksum verification, and a deliberate Gatekeeper/signing story.
Automatically removing quarantine is not an acceptable substitute for signing
and notarization in the partner-ready path.

## Non-goals for the first slice

- Installing every optional IterBrow development environment.
- Bundling a large local language model.
- Collecting provider secrets in the terminal.
- Creating a second updater, state database, or process supervisor.
- Claiming cross-platform support from a Mac-only acceptance run.
- Silently fixing an ambiguous or foreign existing installation.

## Verification matrix

DIST-1 is not complete until the same installer version passes:

| Scenario | Required result |
|---|---|
| Clean Apple Silicon profile | One invocation reaches `runtime_ready`, then `assistant_ready` after private onboarding. |
| Intel-compatible profile | The correct artifacts and runtime pass the same acceptance contract. |
| Interrupt at every material stage | Re-run resumes or safely retries without state loss or duplicate owners. |
| Immediate re-run | No duplicate downloads, state, services, or windows; readiness is re-proved. |
| Existing healthy install | State is unchanged and the existing owner is focused or intentionally upgraded. |
| Version upgrade | State checkpoint and exact prior program rollback are retained. |
| Dependency or network failure | Failure names the incomplete stage and a safe retry; no false success. |
| Foreign live checkout | It is not killed, unlinked, or mistaken for the requested installation. |
| Missing/invalid provider credential | Runtime health remains visible; assistant readiness remains honestly pending. |
| Log and support bundle audit | No secret value, portable-state violation, or unbounded personal content appears. |

## Consequences

- The root installer must be redesigned as a small orchestration and evidence
  layer instead of accumulating product and developer setup in one linear file.
- `scripts/setup_python_env.sh` becomes an idempotent bounded stage or helper,
  not a manual packaged-app repair instruction.
- Current README language must call the existing script a developer bootstrap
  until the DIST-1 matrix passes.
- Installation health reuses lifecycle truth and durable chat evidence, which
  prevents a new competing status authority.

## Rollback

If a new installer cannot prove readiness, it records the failed stage, stops
only processes it started, restores the exact prior program version when an
upgrade was attempted, and preserves the writable workspace and diagnostic
evidence. The user may continue using the prior healthy version. Rollback never
resets cognition or deletes credentials.
