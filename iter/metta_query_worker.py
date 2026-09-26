#!/usr/bin/env python3
"""One-shot Hyperon evaluator for an authoritative AtomSpace snapshot.

The Hyperon native runtime can abort the entire host process on an internal
Rust panic. Read/compatibility programs also intentionally contain temporary
facts and rules, so they must not execute in the authoritative service's
persistent validation engine. The service therefore sends one named snapshot
to this disposable worker. A native failure kills only this process; success
returns one JSON response and the temporary engine is discarded.
"""
import json
import sys
import tempfile
from pathlib import Path


def evaluate(payload):
    from hyperon import Environment, MeTTa
    from metta_server import _logical_units, _add_atom_source

    workspace_root = Path(payload["working_dir"]).resolve()
    workspace_root.mkdir(parents=True, exist_ok=True)
    units = list(_logical_units(str(payload.get("code", ""))))
    setup_units = [unit for unit in units if not unit.lstrip().startswith("!")]
    evaluation_units = [unit for unit in units if unit.lstrip().startswith("!")]
    # A Hyperon Environment must not share its working directory with the
    # service's persistent validation engine or another worker. Native module
    # caches under a shared tree can corrupt the trie even across processes.
    with tempfile.TemporaryDirectory(prefix="query-", dir=workspace_root) as query_dir:
        environment = Environment.custom_env(
            working_dir=query_dir, config_dir=None, create_config=False
        )
        engine = MeTTa(env_builder=environment)
        for unit in payload.get("seed_units", []):
            _add_atom_source(engine, unit)
        # This Hyperon build can corrupt its trie when new rules are inserted
        # after a large data set. Program-local rules/facts are order-neutral,
        # so load them before the durable atom data and evaluate only after the
        # complete one-shot space exists.
        for unit in setup_units:
            engine.run(unit)
        atoms = payload.get("atoms") or {}
        for key in sorted(atoms):
            _add_atom_source(engine, atoms[key])
        results = []
        for unit in evaluation_units:
            current = engine.run(unit)
            if current:
                results.extend(current)
        return str(results)


def main():
    try:
        payload = json.load(sys.stdin)
        result = evaluate(payload)
        response = {"ok": True, "result": result}
    except Exception as exc:
        response = {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}
    sys.stdout.write(json.dumps(response, sort_keys=True) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
