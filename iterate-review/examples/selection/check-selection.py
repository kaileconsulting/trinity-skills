#!/usr/bin/env python3
"""Golden-fixture CLI for iterate-review's deterministic lens selection.

The selection ENGINE lives in ../../bin/selection_engine.py — promoted to
runtime by the runner-scripts plan (docs/runner-scripts-artifact-hygiene-
2026-08-06.md): `run-pass` calls the same select() these goldens pin, so
there is exactly ONE implementation of the rules. This file is only the
fixture harness: it runs the golden diffs in this directory against the
engine and explains selections for ad-hoc diffs.

SOURCE OF TRUTH is ../../lenses/README.md plus each lens's frontmatter --
never code. The engine *reads* the rule data instead of restating it; see
its module docstring.

Usage:
    ./check-selection.py                 # run the golden fixtures, exit 1 on mismatch
    ./check-selection.py FILE.diff ...   # explain the selection for specific diffs

Exit codes: 0 = goldens pass, 1 = fixture mismatch/missing, 2 = rule-data error.
"""

from __future__ import annotations

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE_PATH = os.path.normpath(
    os.path.join(HERE, "..", "..", "bin", "selection_engine.py"))
EXPECTED = os.path.join(HERE, "expected.tsv")


def _load_engine():
    spec = importlib.util.spec_from_file_location(
        "iterate_review_selection_engine", ENGINE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


engine = _load_engine()
RuleDataError = engine.RuleDataError


def read_expected() -> list[tuple[str, list[str], str]]:
    rows = []
    with open(EXPECTED, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                raise RuleDataError(f"{EXPECTED}: malformed row: {line!r}")
            fixture = parts[0].strip()
            lenses = sorted(p.strip() for p in parts[1].split(",") if p.strip())
            note = parts[2].strip() if len(parts) > 2 else ""
            rows.append((fixture, lenses, note))
    if not rows:
        raise RuleDataError(f"{EXPECTED}: no fixture rows found")
    return rows


def run_goldens() -> int:
    lenses = engine.load_lenses()
    cfg = engine.load_readme_config()
    rows = read_expected()

    print(f"engine:      {ENGINE_PATH}")
    print(f"lenses:      {', '.join(l['id'] for l in lenses)}")
    print(f"source_exts: {len(cfg['source_exts'])} extensions")
    print(f"test_globs:  {', '.join(cfg['test_globs'])}")
    print(f"threshold:   >= {cfg['threshold']} changed non-blank source lines")
    print()

    failures = []
    width = max(len(f) for f, _, _ in rows)
    for fixture, expected, _note in rows:
        path = os.path.join(HERE, fixture)
        if not os.path.exists(path):
            print(f"  {fixture:<{width}}  MISSING fixture file")
            failures.append(fixture)
            continue
        with open(path, encoding="utf-8") as fh:
            actual, reasons = engine.select(fh.read(), lenses, cfg)
        ok = actual == expected
        status = "PASS" if ok else "FAIL"
        print(f"  {fixture:<{width}}  {status}  {', '.join(actual) or '(none)'}")
        if not ok:
            print(f"  {'':<{width}}        expected: {', '.join(expected) or '(none)'}")
            for lid, why in reasons.items():
                for w in why:
                    print(f"  {'':<{width}}        {lid}: {w}")
            failures.append(fixture)

    print()
    if failures:
        print(f"{len(rows) - len(failures)}/{len(rows)} routing fixtures PASS "
              f"-- FAILED: {', '.join(failures)}")
        return 1
    print(f"{len(rows)}/{len(rows)} routing fixtures PASS")
    return 0


def explain(paths: list[str]) -> int:
    lenses = engine.load_lenses()
    cfg = engine.load_readme_config()
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        selected, reasons = engine.select(text, lenses, cfg)
        changed_paths, added, removed = engine.parse_diff(text)
        print(f"{path}")
        print(f"  changed paths: {', '.join(sorted(changed_paths)) or '(none)'}")
        print(f"  source lines:  "
              f"{engine.nontrivial_source_line_count(added, removed, cfg)} "
              f"(threshold {cfg['threshold']})")
        print(f"  lenses:        {', '.join(selected)}")
        for lid in selected:
            for why in reasons[lid]:
                print(f"    {lid}: {why}")
        print()
    return 0


def main(argv: list[str]) -> int:
    try:
        if len(argv) > 1:
            return explain(argv[1:])
        return run_goldens()
    except RuleDataError as exc:
        print(f"rule-data error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
