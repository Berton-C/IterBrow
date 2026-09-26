# ADR-0008: Checkout-Scoped Browser Bridge Ownership

Status: Accepted

Date: 2026-09-21

## Context

The browser-control bridge historically used the global Unix socket
`/tmp/iter-browser-bridge.sock`. A live source application was observed with
the listener file descriptor still open while the pathname itself was gone.
This leaves the original server alive but unreachable. A competing launch or
another checkout can cause exactly that state because the old startup path
unconditionally unlinked the shared pathname before listening.

The checkout-scoped Electron single-instance lock prevents two current main
processes for one checkout, but it cannot make one generic filesystem endpoint
safe for multiple checkouts.

## Decision

- The default browser bridge endpoint is derived from the same checkout
  instance identity used by the AtomSpace endpoint.
- Electron passes that exact endpoint both to the in-process bridge server and
  to its supervised Iter child as `ITER_BRIDGE_SOCKET`.
- An explicit `ITER_BRIDGE_SOCKET` override remains supported for controlled
  environments.
- Startup probes an existing endpoint. A responsive listener is never
  unlinked or replaced. Only a connection-refused stale socket is removed.
- A bridge endpoint conflict fails closed and is surfaced in the runtime log.
- Automatic, manual, and recovery Iter starts wait for the bridge ownership
  result and refuse to launch cognition unless this checkout is listening.

## Consequences

Different checkouts cannot steal one another's browser-control endpoint, and a
second server cannot make a live first server unreachable. A process already
running the previous code retains its old open-but-unlinked endpoint until the
next controlled application restart; source edits do not mutate a live main
process.

Directly launched browser tools still honor an explicit
`ITER_BRIDGE_SOCKET`. The supervised Iter process always receives the correct
checkout-scoped value.

## Rollback

Restore the generic endpoint only together with an ownership protocol that
proves the existing listener belongs to this checkout before replacement.
Never reintroduce unconditional unlink of a potentially live socket.
