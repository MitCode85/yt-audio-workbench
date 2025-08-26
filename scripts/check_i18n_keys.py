#!/usr/bin/env python
"""
Fail if locale JSON files in lang/ don’t share the same leaf keys.
- Treat keys literally (do NOT split on ".")
- Report missing keys per locale
- Also flag structural mismatches (leaf vs dict)
"""

from __future__ import annotations
import json, sys
from pathlib import Path
from collections.abc import Iterable

ROOT = Path(__file__).resolve().parents[1]
LANG_DIR = ROOT / "lang"


def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def walk_leaves(d: dict, prefix: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], str]]:
    for k, v in d.items():
        if isinstance(v, dict):
            yield from walk_leaves(v, prefix + (k,))
        else:
            yield (prefix + (k,)), v


def walk_shapes(
    d: dict, prefix: tuple[str, ...] = (), out: dict[tuple[str, ...], str] | None = None
):
    if out is None:
        out = {}
    for k, v in d.items():
        path = prefix + (k,)
        if isinstance(v, dict):
            out[path] = "dict"
            walk_shapes(v, path, out)
        else:
            out[path] = "leaf"
    return out


def main() -> int:
    if not LANG_DIR.exists():
        print("No lang/ directory found.", file=sys.stderr)
        return 1

    locales = sorted(LANG_DIR.glob("*.json"))
    if not locales:
        print("No locale files found in lang/.", file=sys.stderr)
        return 1

    data = {p.name: load_json(p) for p in locales}
    leaf_sets = {name: {path for path, _ in walk_leaves(obj)} for name, obj in data.items()}
    shapes = {name: walk_shapes(obj) for name, obj in data.items()}

    # Union of all leaf paths across locales
    union_leaves = set().union(*leaf_sets.values())

    ok = True

    # Report missing keys per locale
    for name, leaves in leaf_sets.items():
        missing = sorted(".".join(p) for p in (union_leaves - leaves))
        if missing:
            ok = False
            print(f"\n❌ Missing in {name}:")
            for m in missing:
                print(f"  - {m}")

    # Check for structural inconsistencies (leaf in one, dict in another)
    # Build a union of all paths seen in any shape map.
    union_paths = set().union(*[set(s.keys()) for s in shapes.values()])
    for path in sorted(union_paths):
        shapes_here = {name: s.get(path) for name, s in shapes.items() if path in s}
        if len(set(shapes_here.values())) > 1:
            ok = False
            dotted = ".".join(path)
            print(f"\n[FAIL] Structural mismatch at '{dotted}':")
            for name, kind in sorted(shapes_here.items()):
                print(f"  - {name}: {kind}")

    if ok:
        print("[OK] i18n key sets match across locales.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
