#!/usr/bin/env python3
"""Tests for the checkers themselves — do they fail when they should?

A checker that always passes is worse than no checker: it reads as coverage. All
three checkers in this directory passed on their first run against the real repo,
which is exactly when to distrust them. This file exercises their failure paths
by monkeypatching module internals, so "the checkers have teeth" stays verified
instead of being something someone confirmed once by hand.

Being internals-coupled, this is the file most likely to need updating when a
checker is refactored. That cost is deliberate: the alternative is trusting a
green run.

Usage:
    tools/test-checkers.py
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import sys
import tempfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TOOLS)
SELECTION = os.path.join(
    REPO, "iterate-review", "examples", "selection", "check-selection.py")

results: list[tuple[str, bool, str]] = []


def load(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def record(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))


def quiet(fn, *args):
    """Run fn capturing stdout/stderr, returning its value."""
    with contextlib.redirect_stdout(io.StringIO()), \
         contextlib.redirect_stderr(io.StringIO()):
        return fn(*args)


def loud(fn, *args) -> tuple[object, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
        rv = fn(*args)
    return rv, buf.getvalue()


def raises(fn, exc) -> bool:
    try:
        quiet(fn)
    except exc:
        return True
    except Exception:
        return False
    return False


# ---------------------------------------------------------------------------
# check-selection.py
# ---------------------------------------------------------------------------

def test_selection() -> None:
    cs = load(SELECTION, "cs")
    tmp = tempfile.mkdtemp()

    record("selection: baseline passes", quiet(cs.run_goldens) == 0)

    # Rule data that cannot be parsed must raise, never default to empty.
    real_readme, real_lensdir, real_expected = cs.README, cs.LENS_DIR, cs.EXPECTED

    p = os.path.join(tmp, "no_exts.md")
    open(p, "w").write("# lenses\nnothing parseable\n")
    cs.README = p
    record("selection: README without source_exts raises",
           raises(cs.load_readme_config, cs.RuleDataError))
    cs.README = real_readme

    p = os.path.join(tmp, "no_threshold.md")
    open(p, "w").write("`source_exts`: `.py`\n`test_globs`: `**/*test*`\n")
    cs.README = p
    record("selection: README without threshold raises",
           raises(cs.load_readme_config, cs.RuleDataError))
    cs.README = real_readme

    d = os.path.join(tmp, "empty_lenses")
    os.makedirs(d, exist_ok=True)
    cs.LENS_DIR = d
    record("selection: empty lens dir raises",
           raises(cs.load_lenses, cs.RuleDataError))
    cs.LENS_DIR = real_lensdir

    d = os.path.join(tmp, "noid_lenses")
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "x.md"), "w").write("---\nskill: y\n---\nbody\n")
    cs.LENS_DIR = d
    record("selection: lens without id raises",
           raises(cs.load_lenses, cs.RuleDataError))
    cs.LENS_DIR = real_lensdir

    d = os.path.join(tmp, "badrx_lenses")
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "x.md"), "w").write(
        '---\nid: x\nselection:\n  content_regexes:\n    - "([unclosed"\n---\nb\n')
    cs.LENS_DIR = d
    record("selection: invalid content_regex raises", raises(
        lambda: cs.select("diff --git a/a.py b/a.py\n+x\n",
                          cs.load_lenses(), cs.load_readme_config()),
        cs.RuleDataError))
    cs.LENS_DIR = real_lensdir

    # A wrong golden must be reported, not tolerated.
    p = os.path.join(tmp, "wrong.tsv")
    open(p, "w").write("01-local-rename.diff\tqa,security,senior-dev\twrong on purpose\n")
    cs.EXPECTED = p
    record("selection: wrong golden -> exit 1", quiet(cs.run_goldens) == 1)
    cs.EXPECTED = real_expected

    p = os.path.join(tmp, "missing.tsv")
    open(p, "w").write("nope.diff\tsenior-dev\t\n")
    cs.EXPECTED = p
    record("selection: missing fixture -> exit 1", quiet(cs.run_goldens) == 1)
    cs.EXPECTED = real_expected


# ---------------------------------------------------------------------------
# check-parity.py
# ---------------------------------------------------------------------------

def test_parity() -> None:
    cp = load(os.path.join(TOOLS, "check-parity.py"), "cp")
    real_load, real_rules, real_skills = cp.load, list(cp.RULES), cp.SKILLS

    rc, _ = loud(cp.main, [])
    record("parity: baseline passes", rc == 0, f"exit {rc}")

    def stripper(target_skill, phrase):
        def _load(skill):
            norm, lines = real_load(skill)
            if target_skill is None or skill == target_skill:
                norm = norm.replace(phrase, "REDACTED")
            return norm, lines
        return _load

    cp.load = stripper("iterate-review", "worst-of")
    rc, out = loud(cp.main, [])
    cp.load = real_load
    record("parity: one-sided gap detected",
           rc == 1 and "PARITY GAP" in out and "verdict-worst-of" in out)

    cp.load = stripper("iterate-plan", "block is preserved")
    rc, out = loud(cp.main, [])
    cp.load = real_load
    record("parity: gap names the offending skill",
           rc == 1 and "absent from iterate-plan" in out)

    cp.load = stripper(None, "retried once")
    rc, out = loud(cp.main, [])
    cp.load = real_load
    record("parity: absent-from-both distinguished from a gap",
           rc == 1 and "MISSING FROM BOTH" in out and "PARITY GAP" not in out)

    cp.RULES = [("bogus", "d", [r"one codex call per selected lens",
                                r"zzz-cannot-match-zzz"])]
    rc, out = loud(cp.main, [])
    cp.RULES = real_rules
    record("parity: every pattern in a rule is required", rc == 1)

    cp.SKILLS = ("iterate-plan", "does-not-exist")
    rc = quiet(cp.main, [])
    cp.SKILLS = real_skills
    record("parity: absent SKILL.md -> exit 2, not a pass", rc == 2, f"exit {rc}")


# ---------------------------------------------------------------------------
# check-examples.py
# ---------------------------------------------------------------------------

def test_examples() -> None:
    ce = load(os.path.join(TOOLS, "check-examples.py"), "ce")

    rc = quiet(ce.main)
    record("examples: baseline passes", rc == 0, f"exit {rc}")

    patchy = {"verdict": "REVISE", "findings": [{
        "title": "t", "severity": "HIGH",
        "description": "*** Begin Patch\n--- a/x.ts\n+++ b/x.ts\n@@ -1,2 +1,3 @@\n",
        "suggested_action": "a"}], "code_corrections": [], "new_questions": []}
    record("examples: patch markers detected inside JSON strings",
           len(ce.find_patch_markers(patchy)) >= 3,
           f"{len(ce.find_patch_markers(patchy))} marker kinds")

    clean = {"verdict": "APPROVE", "findings": [], "code_corrections": [],
             "new_questions": ["is web/lib/parse.ts public API?"]}
    record("examples: clean response reports no markers",
           ce.find_patch_markers(clean) == [])

    real_skills = ce.SKILLS
    ce.SKILLS = ("nonexistent-skill",)
    rc = quiet(ce.main)
    ce.SKILLS = real_skills
    record("examples: skill without a schema -> exit 1", rc == 1, f"exit {rc}")


def main() -> int:
    test_selection()
    test_parity()
    test_examples()

    print("checker self-tests\n")
    width = max(len(n) for n, _, _ in results)
    for name, ok, detail in results:
        mark = "ok  " if ok else "FAIL"
        suffix = f"  ({detail})" if detail else ""
        print(f"  {mark}  {name:<{width}}{suffix}")

    bad = [n for n, ok, _ in results if not ok]
    print()
    if bad:
        print(f"{len(results) - len(bad)}/{len(results)} passed -- FAILED: "
              f"{', '.join(bad)}")
        return 1
    print(f"{len(results)}/{len(results)} passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
