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

    # --- diff parsing: each side classified by its OWN path ----------------
    # Regression guard for the Phase 4 review's HIGH finding: attributing a
    # rename's `-` lines to the new path undercounts a source file renamed to a
    # non-source extension.
    rename = (
        "diff --git a/lib/calc.py b/notes/calc.txt\n"
        "rename from lib/calc.py\n"
        "rename to notes/calc.txt\n"
        "--- a/lib/calc.py\n"
        "+++ b/notes/calc.txt\n"
        "@@ -1,2 +1,1 @@\n"
        "-def f():\n"
        "-    return 1\n"
        "+a note\n"
    )
    _paths, added, removed = cs.parse_diff(rename)
    record("selection: rename attributes each side to its own path",
           list(removed) == ["lib/calc.py"] and list(added) == ["notes/calc.txt"],
           f"removed={list(removed)} added={list(added)}")

    # A deleted source file is `diff --git a/x b/x` + `+++ /dev/null`, so its
    # removed lines must still land on the source path.
    deletion = (
        "diff --git a/lib/gone.py b/lib/gone.py\n"
        "deleted file mode 100644\n"
        "--- a/lib/gone.py\n"
        "+++ /dev/null\n"
        "@@ -1,2 +0,0 @@\n"
        "-def f():\n"
        "-    return 1\n"
    )
    _paths, added, removed = cs.parse_diff(deletion)
    record("selection: deletion keeps removed lines on the source path",
           list(removed) == ["lib/gone.py"] and added == {},
           f"removed={list(removed)}")

    # `--- ` inside a hunk is a removed content line, not a file header.
    ambiguous = (
        "diff --git a/x.py b/x.py\n"
        "--- a/x.py\n"
        "+++ b/x.py\n"
        "@@ -1,2 +1,2 @@\n"
        "--- not a header, this is removed content\n"
        "+++ not a header, this is added content\n"
    )
    paths, added, removed = cs.parse_diff(ambiguous)
    record("selection: in-hunk ---/+++ lines are content, not headers",
           paths == {"x.py"} and list(removed) == ["x.py"] and list(added) == ["x.py"],
           f"paths={sorted(paths)}")

    # --- accepted diff formats ---------------------------------------------
    # Regression guards for the Phase 4 review pass 2, which found quoted paths
    # and tab-separated timestamps each silently yielding zero source lines.
    record("selection: git C-quoting decoded (escapes)",
           cs._unquote_c(r'a/lib/my \"odd\" \\name.py')
           == 'a/lib/my "odd" \\name.py')
    record("selection: git C-quoting decoded (octal UTF-8)",
           cs._unquote_c(r"a/lib/caf\303\251.py") == "a/lib/café.py",
           cs._unquote_c(r"a/lib/caf\303\251.py"))

    record("selection: quoted diff --git line parsed",
           cs._parse_diff_git('diff --git "a/lib/my calc.py" "b/notes/my calc.txt"')
           == ("lib/my calc.py", "notes/my calc.txt"))
    record("selection: bare diff --git line still parsed",
           cs._parse_diff_git("diff --git a/lib/x.py b/lib/x.py")
           == ("lib/x.py", "lib/x.py"))

    record("selection: quoted header path normalised",
           cs._normalise_header_path('"a/lib/my calc.py"', "a") == "lib/my calc.py")
    record("selection: tab timestamp stripped from header path",
           cs._normalise_header_path(
               "lib/report.py\t2026-07-28 09:00:00.000000000 +0000", "a")
           == "lib/report.py")
    record("selection: /dev/null header yields no path",
           cs._normalise_header_path("/dev/null", "b") is None)

    # Pass 3's MEDIUM: `--- a/lib/foo.py` is genuinely ambiguous. In git format the
    # `a/` is a side prefix; in a plain diff it is a real directory named `a`.
    # Format context decides, so a plain diff must preserve the leading component.
    plain_a = (
        "--- a/lib/foo.py\t2026-07-28 09:00:00 +0000\n"
        "+++ a/lib/foo.py\t2026-07-28 09:05:00 +0000\n"
        "@@ -1,1 +1,1 @@\n-x = 1\n+x = 2\n"
    )
    paths, _added, _removed = cs.parse_diff(plain_a)
    record("selection: plain diff keeps a literal top-level a/ component",
           paths == {"a/lib/foo.py"}, f"paths={sorted(paths)}")

    git_a = (
        "diff --git a/lib/foo.py b/lib/foo.py\n"
        "--- a/lib/foo.py\n+++ b/lib/foo.py\n"
        "@@ -1,1 +1,1 @@\n-x = 1\n+x = 2\n"
    )
    paths, _added, _removed = cs.parse_diff(git_a)
    record("selection: git diff still strips the a//b/ side prefix",
           paths == {"lib/foo.py"}, f"paths={sorted(paths)}")

    # A pure addition has `--- /dev/null`; its added lines must still be counted.
    addition = (
        "diff --git a/lib/new.py b/lib/new.py\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        "+++ b/lib/new.py\n"
        "@@ -0,0 +1,2 @@\n"
        "+def f():\n"
        "+    return 1\n"
    )
    _p, added, removed = cs.parse_diff(addition)
    record("selection: addition counts added lines, no phantom old path",
           list(added) == ["lib/new.py"] and removed == {},
           f"added={list(added)} removed={list(removed)}")

    # Multi-file: hunk state must reset per file, not leak across the boundary.
    multi = (
        "diff --git a/one.py b/one.py\n--- a/one.py\n+++ b/one.py\n"
        "@@ -1,1 +1,1 @@\n-a = 1\n+a = 2\n"
        "diff --git a/two.py b/two.py\n--- a/two.py\n+++ b/two.py\n"
        "@@ -1,1 +1,1 @@\n-b = 1\n+b = 2\n"
    )
    paths, added, removed = cs.parse_diff(multi)
    record("selection: multi-file diff attributes each file separately",
           paths == {"one.py", "two.py"}
           and sorted(added) == ["one.py", "two.py"]
           and sorted(removed) == ["one.py", "two.py"],
           f"paths={sorted(paths)}")

    # Rule data that cannot be parsed must raise, never default to empty.
    real_readme, real_lensdir, real_expected = cs.README, cs.LENS_DIR, cs.EXPECTED

    # --- threshold is read from its DEFINING bullet ------------------------
    # Guard for the Phase 4 review's MEDIUM finding: an unanchored search would
    # let unrelated earlier prose become the threshold.
    p = os.path.join(tmp, "decoy_threshold.md")
    open(p, "w").write(
        "Historically we used >= 99 changed non-blank lines as a smoke test.\n\n"
        "`source_exts`: `.py .ts`\n"
        "`test_globs`: `**/*test*`, `**/tests/**`\n"
        "  - *non-trivial source change* = **>= 8 changed non-blank content "
        "lines across source files**\n"
    )
    cs.README = p
    try:
        parsed = quiet(cs.load_readme_config)
        got = parsed["threshold"]
    except Exception as exc:  # noqa: BLE001 - surfaced as a failed record
        got = f"raised {type(exc).__name__}"
    cs.README = real_readme
    record("selection: threshold anchored to its defining bullet",
           got == 8, f"parsed {got}, decoy was 99")

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

    # --- per-skill patterns ------------------------------------------------
    # Guard for the Phase 4 review's MEDIUM finding: a shared pattern let one
    # skill satisfy a rule via text referencing the sibling's behaviour.
    cp.RULES = [("per-skill", "d", {
        "iterate-plan": [r"dedupe plan_corrections"],
        "iterate-review": [r"dedupe code_corrections"],
    })]
    rc, out = loud(cp.main, [])
    record("parity: per-skill patterns accepted and satisfied", rc == 0, f"exit {rc}")

    # Give iterate-plan a pattern that only exists in iterate-review: the rule
    # must fail rather than being satisfied by the sibling's text.
    cp.RULES = [("per-skill-crossed", "d", {
        "iterate-plan": [r"dedupe code_corrections"],
        "iterate-review": [r"dedupe code_corrections"],
    })]
    rc, out = loud(cp.main, [])
    record("parity: per-skill patterns are not satisfied by the sibling's text",
           rc == 1 and "PARITY GAP" in out and "absent from iterate-plan" in out)

    # A per-skill rule that forgets a skill is a config error, not a silent pass.
    cp.RULES = [("incomplete", "d", {"iterate-plan": [r"worst-of"]})]
    rc = quiet(cp.main, [])
    cp.RULES = real_rules
    record("parity: per-skill rule missing a skill -> exit 2", rc == 2, f"exit {rc}")


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

    # --- new_questions classification is enforced, not optional ------------
    # 2.1 made new_questions objects. If the schema still accepted bare strings,
    # a lens could silently skip classifying and the loop guardrail would have
    # nothing to route on.
    import json as _json
    try:
        import jsonschema
    except ImportError:
        record("examples: new_questions classification enforced", False,
               "jsonschema not installed")
        return

    base = {"verdict": "APPROVE", "findings": [], "new_questions": []}
    shapes = {
        "iterate-plan": dict(base, plan_corrections=[], open_question_answers=[]),
        "iterate-review": dict(base, code_corrections=[]),
    }
    for skill, doc in shapes.items():
        schema = _json.load(open(os.path.join(REPO, skill, "reviewer-output.schema.json")))
        v = jsonschema.Draft202012Validator(schema)

        legacy = dict(doc, new_questions=["a bare string question"])
        record(f"examples: {skill} rejects unclassified new_questions",
               bool(list(v.iter_errors(legacy))))

        classified = dict(doc, new_questions=[{
            "question": "q", "settled_by": "needs_human", "why": "author's call"}])
        record(f"examples: {skill} accepts classified new_questions",
               not list(v.iter_errors(classified)))

        bad_class = dict(doc, new_questions=[{
            "question": "q", "settled_by": "ask_someone", "why": "w"}])
        record(f"examples: {skill} rejects an unknown settled_by",
               bool(list(v.iter_errors(bad_class))))

        no_why = dict(doc, new_questions=[{
            "question": "q", "settled_by": "needs_human"}])
        record(f"examples: {skill} requires the audit trail (why)",
               bool(list(v.iter_errors(no_why))))


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
