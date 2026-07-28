#!/usr/bin/env python3
"""Reference implementation of iterate-review's deterministic lens selection.

TEST-ONLY. The skill does not call this at runtime -- step 9 of ../../SKILL.md
has Opus apply the rules directly. This script exists so the determinism
guarantee asserted in ../../lenses/README.md ("Two implementations applying
these rules to the same diff MUST select the same lens set") has an actual
second implementation. If this script and Opus disagree about a diff, one of
them misread the rules, and that is a defect worth surfacing.

SOURCE OF TRUTH is ../../lenses/README.md plus each lens's frontmatter --
never this file. To keep drift structurally impossible, the script *reads* the
rule data instead of restating it:

    path_globs / content_regexes / non_trivial_without_tests
        <- parsed from ../../lenses/*.md frontmatter
    source_exts / test_globs / non-trivial line threshold
        <- parsed from ../../lenses/README.md

Only the *evaluation algorithm* (glob semantics, case-insensitivity, which diff
lines count, how the threshold is applied) lives here. That is the irreducible
duplication; everything else has one home.

Usage:
    ./check-selection.py                 # run the golden fixtures, exit 1 on mismatch
    ./check-selection.py FILE.diff ...   # explain the selection for specific diffs
"""

from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LENS_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "lenses"))
README = os.path.join(LENS_DIR, "README.md")
EXPECTED = os.path.join(HERE, "expected.tsv")


class RuleDataError(Exception):
    """The rule data could not be parsed -- fail loudly, never silently default."""


# ---------------------------------------------------------------------------
# Minimal YAML-frontmatter reader
#
# Deliberately not PyYAML: this keeps the checker dependency-free. It handles
# exactly the shape the lens records use (see ../../lenses/README.md "Lens
# record format") and raises rather than guessing on anything else.
# ---------------------------------------------------------------------------

def _strip_comment(raw: str) -> str:
    """Drop a trailing ` # ...` comment, respecting double quotes."""
    out, in_quotes, i = [], False, 0
    while i < len(raw):
        ch = raw[i]
        if ch == '"' and (i == 0 or raw[i - 1] != "\\"):
            in_quotes = not in_quotes
        if ch == "#" and not in_quotes:
            break
        out.append(ch)
        i += 1
    return "".join(out).rstrip()


def _unquote(value: str) -> str:
    """Decode a YAML scalar. Double-quoted strings process backslash escapes,
    which is how `"\\b(jwt|...)\\b"` in the lens file becomes the regex \\b(jwt|...)\\b."""
    value = value.strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        body = value[1:-1]
        return body.replace('\\"', '"').replace("\\\\", "\\").replace("\\n", "\n")
    if len(value) >= 2 and value[0] == "'" and value[-1] == "'":
        return value[1:-1].replace("''", "'")
    return value


def parse_frontmatter_selection(path: str) -> dict:
    """Extract `id` and the `selection:` block from a lens record."""
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()

    if not lines or lines[0].strip() != "---":
        raise RuleDataError(f"{path}: expected frontmatter to open with '---'")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise RuleDataError(f"{path}: unterminated frontmatter") from None

    lens = {
        "id": None,
        "always": False,
        "path_globs": [],
        "content_regexes": [],
        "non_trivial_without_tests": False,
    }
    in_selection = False
    current_list = None

    for raw in lines[1:end]:
        line = _strip_comment(raw)
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        body = line.strip()

        # A list item belonging to the key we last saw.
        if body.startswith("- ") and current_list is not None:
            lens[current_list].append(_unquote(body[2:]))
            continue

        # Any non-list line ends the current list.
        current_list = None

        if indent == 0:
            in_selection = body.rstrip(":") == "selection" and body.endswith(":")
            if body.startswith("id:"):
                lens["id"] = _unquote(body[3:])
            continue

        if not in_selection:
            continue

        if body.endswith(":"):
            key = body[:-1].strip()
            if key in ("path_globs", "content_regexes"):
                current_list = key
            continue

        if ":" in body:
            key, _, value = body.partition(":")
            key, value = key.strip(), _unquote(value)
            if key == "always":
                lens["always"] = value == "true"
            elif key == "non_trivial_without_tests":
                lens["non_trivial_without_tests"] = value == "true"

    if not lens["id"]:
        raise RuleDataError(f"{path}: frontmatter has no `id`")
    return lens


def load_lenses() -> list[dict]:
    if not os.path.isdir(LENS_DIR):
        raise RuleDataError(f"lens directory not found: {LENS_DIR}")
    names = sorted(
        f for f in os.listdir(LENS_DIR) if f.endswith(".md") and f != "README.md"
    )
    if not names:
        raise RuleDataError(f"no lens records found in {LENS_DIR}")
    return [parse_frontmatter_selection(os.path.join(LENS_DIR, n)) for n in names]


def load_readme_config() -> dict:
    """Pull source_exts, test_globs and the non-trivial threshold out of the README.

    Parsed rather than hardcoded so that editing the README's Matching semantics
    flows through here automatically. Anything unparseable raises."""
    with open(README, encoding="utf-8") as fh:
        text = fh.read()

    m = re.search(r"`source_exts`:\s*`([^`]+)`", text)
    if not m:
        raise RuleDataError(f"{README}: could not find the `source_exts` list")
    source_exts = {e.lower() for e in m.group(1).split()}

    m = re.search(r"`test_globs`:\s*((?:`[^`]+`(?:,\s*)?)+)", text)
    if not m:
        raise RuleDataError(f"{README}: could not find the `test_globs` list")
    test_globs = re.findall(r"`([^`]+)`", m.group(1))

    m = re.search(r"[>≥]=?\s*(\d+)\s+changed non-blank", text)
    if not m:
        raise RuleDataError(
            f"{README}: could not find the non-trivial line threshold "
            '(expected a phrase like "≥ 8 changed non-blank")'
        )
    threshold = int(m.group(1))

    if not source_exts or not test_globs:
        raise RuleDataError(f"{README}: parsed an empty source_exts/test_globs list")
    return {
        "source_exts": source_exts,
        "test_globs": test_globs,
        "threshold": threshold,
    }


# ---------------------------------------------------------------------------
# Evaluation algorithm (README "Matching semantics")
# ---------------------------------------------------------------------------

def glob_to_regex(glob: str) -> re.Pattern:
    """Repo-relative, case-insensitive glob. `**` spans path separators, `*`
    does not. A leading `**/` matches zero or more leading segments, so
    `**/*auth*` matches both `auth.py` and `src/lib/auth.py`."""
    out, i = [], 0
    while i < len(glob):
        if glob.startswith("**/", i):
            out.append("(?:[^/]+/)*")
            i += 3
        elif glob.startswith("**", i):
            out.append(".*")
            i += 2
        elif glob[i] == "*":
            out.append("[^/]*")
            i += 1
        elif glob[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(glob[i]))
            i += 1
    return re.compile("".join(out) + r"\Z", re.IGNORECASE)


def path_matches_any(path: str, globs: list[str]) -> str | None:
    for g in globs:
        if glob_to_regex(g).match(path):
            return g
    return None


def parse_diff(text: str) -> tuple[set[str], dict[str, list[str]]]:
    """Return (changed paths, changed content lines per path).

    Changed content lines are added (`+`) and removed (`-`) lines only --
    never the `+++`/`---`/`@@` headers and never context lines."""
    changed_paths: set[str] = set()
    per_file: dict[str, list[str]] = {}
    current: str | None = None

    for line in text.splitlines():
        if line.startswith("diff --git "):
            m = re.match(r"diff --git a/(.+?) b/(.+)$", line)
            if m:
                old, new = m.group(1), m.group(2)
                for p in (old, new):
                    if p != "/dev/null":
                        changed_paths.add(p)
                current = new if new != "/dev/null" else old
            continue
        if line.startswith("--- ") or line.startswith("+++ "):
            path = line[4:].strip()
            path = re.sub(r"^[ab]/", "", path)
            if path != "/dev/null":
                changed_paths.add(path)
                if line.startswith("+++ "):
                    current = path
            continue
        if line.startswith("@@"):
            continue
        if line.startswith("+") or line.startswith("-"):
            if current is None:
                continue
            per_file.setdefault(current, []).append(line[1:])

    return changed_paths, per_file


def is_test_path(path: str, cfg: dict) -> bool:
    return path_matches_any(path, cfg["test_globs"]) is not None


def nontrivial_source_line_count(per_file: dict[str, list[str]], cfg: dict) -> int:
    """Changed non-blank lines in source files. A source file has an extension in
    source_exts AND a path that does not match test_globs. A modified line counts
    twice (once as `-`, once as `+`) -- deliberately mechanical, per the README."""
    total = 0
    for path, lines in per_file.items():
        ext = os.path.splitext(path)[1].lower()
        if ext not in cfg["source_exts"] or is_test_path(path, cfg):
            continue
        total += sum(1 for ln in lines if ln.strip())
    return total


def select(diff_text: str, lenses: list[dict], cfg: dict) -> tuple[list[str], dict]:
    changed_paths, per_file = parse_diff(diff_text)
    changed_lines = [ln for lines in per_file.values() for ln in lines]

    selected: list[str] = []
    reasons: dict[str, list[str]] = {}

    for lens in lenses:
        lid = lens["id"]
        why: list[str] = []

        if lens["always"]:
            why.append("always: true (floor lens)")

        hit = None
        for path in sorted(changed_paths):
            g = path_matches_any(path, lens["path_globs"])
            if g:
                hit = (path, g)
                break
        if hit:
            why.append(f"path_glob {hit[1]!r} matched {hit[0]}")

        for rx in lens["content_regexes"]:
            try:
                pat = re.compile(rx, re.IGNORECASE)
            except re.error as exc:
                raise RuleDataError(
                    f"lens {lid}: content_regex {rx!r} is not a valid regex: {exc}"
                ) from None
            match = next((ln for ln in changed_lines if pat.search(ln)), None)
            if match is not None:
                why.append(f"content_regex {rx!r} matched: {match.strip()[:70]}")
                break

        if lens["non_trivial_without_tests"]:
            count = nontrivial_source_line_count(per_file, cfg)
            tests_changed = any(is_test_path(p, cfg) for p in changed_paths)
            if count >= cfg["threshold"] and not tests_changed:
                why.append(
                    f"non_trivial_without_tests: {count} changed non-blank source "
                    f"lines (>= {cfg['threshold']}), no test file changed"
                )

        if why:
            selected.append(lid)
            reasons[lid] = why

    return sorted(selected), reasons


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

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
    lenses = load_lenses()
    cfg = load_readme_config()
    rows = read_expected()

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
            actual, reasons = select(fh.read(), lenses, cfg)
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
    lenses = load_lenses()
    cfg = load_readme_config()
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        selected, reasons = select(text, lenses, cfg)
        changed_paths, per_file = parse_diff(text)
        print(f"{path}")
        print(f"  changed paths: {', '.join(sorted(changed_paths)) or '(none)'}")
        print(f"  source lines:  {nontrivial_source_line_count(per_file, cfg)} "
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
