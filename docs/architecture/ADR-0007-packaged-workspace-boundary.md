# ADR-0007: Packaged Template and Writable Workspace Boundary

Status: Accepted

Date: 2026-09-21

## Context

The source checkout historically served as both executable program and mutable
Iter state. Electron Builder therefore copied `iter/**/*` into the application
bundle. A real package audit found that this captured live settings, private
credential containers, the authoritative AtomSpace, PWQ and hot-load ledgers,
experience, memory, indexes, and chat queue. It also made the installed bundle
the runtime write target, which is incompatible with durable upgrades and code
signing.

## Decision

- A packaged application contains an allowlisted, state-free Iter template.
- On first packaged launch, Electron atomically copies that template into a
  per-user writable workspace beneath Electron's `userData` directory.
- `ITERBROW_WORKSPACE_DIR` may select an isolated packaged workspace for
  controlled verification. Source-development launches continue to use the
  checkout's `iter/` directory unchanged.
- The writable workspace is the packaged runtime's canonical `ITER_DIR`; all
  queues, ledgers, projections, indexes, secrets, immutable generations, and
  cognitive state remain rooted there.
- Existing packaged workspaces are never merged with or overwritten by the
  bootstrap path. An incomplete pre-existing workspace fails closed.
- Export/import continues to move only `state_manifest.json` entries marked
  `portable: true`. Credentials remain outside both the template and portable
  archives.

## Consequences

The `.app` can be distributed without the builder's identity or cognition and
runtime writes no longer mutate application resources. A later upgrade slice
must define an explicit versioned template-to-workspace code upgrade protocol;
this decision deliberately does not overwrite an established workspace during
launch.

## Rollback

Source mode is unaffected. For a packaged build, remove only the newly created
isolated workspace after preserving any portable state export, then launch an
older application version. Never copy live state back into the application
bundle.
