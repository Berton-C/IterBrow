#!/usr/bin/env python3
"""Regenerate disposable dashboards without running an Iter/LLM cycle."""

import argparse
import importlib.util
import json
import os
from pathlib import Path


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("dashboard generator cannot be loaded: %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def refresh(root):
    root = root.expanduser().resolve()
    iter_dir = root / "iter"
    transformations = iter_dir / "transformations"
    atomspace_source = transformations / "dashboard_atomspace.py"
    gallery_source = transformations / "dashboard_gallery.py"
    vendor = iter_dir / "vendor" / "force-graph.js"
    for required in (atomspace_source, gallery_source, vendor):
        if not required.is_file():
            raise RuntimeError("dashboard runtime asset is missing: %s" % required)

    previous = Path.cwd()
    try:
        os.chdir(iter_dir)
        atomspace = _load(atomspace_source, "iterbrow_dashboard_atomspace_refresh")
        atomspace.transform([], [])
        rendered = iter_dir / "dashboard_atomspace.html"
        content = rendered.read_text(encoding="utf-8")
        required_markers = (
            'src="vendor/force-graph.js"',
            "window._spaceVizGraph=graph",
            'id="space_viz_canvas"',
        )
        if any(marker not in content for marker in required_markers):
            raise RuntimeError("AtomSpace dashboard generation is incomplete")

        gallery = _load(gallery_source, "iterbrow_dashboard_gallery_refresh")
        gallery.transform([], [])
        gallery_path = iter_dir / "dashboard_gallery.html"
        gallery_content = gallery_path.read_text(encoding="utf-8")
        if 'id="frame-atomspace"' not in gallery_content or "_spaceVizGraph" not in gallery_content:
            raise RuntimeError("dashboard gallery did not embed the current AtomSpace view")
    finally:
        os.chdir(previous)

    return {
        "atomspace_dashboard": str(rendered),
        "atomspace_bytes": rendered.stat().st_size,
        "gallery": str(gallery_path),
        "gallery_bytes": gallery_path.stat().st_size,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(refresh(args.root), sort_keys=True))


if __name__ == "__main__":
    main()
