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

    # Anchored to the bullet that DEFINES the rule, not just any nearby phrase
    # mentioning a changed-line count. An unanchored search would let a future
    # worked example or caveat that mentions a different number silently become
    # the threshold -- which would quietly break the claim that the README is the
    # source of truth.
    m = re.search(
        r"non-trivial source change.{0,40}?[>≥]=?\s*(\d+)\s+changed non-blank",
        text,
        re.DOTALL,
    )
    if not m:
        raise RuleDataError(
            f"{README}: could not find the non-trivial line threshold. Expected a "
            'bullet defining "non-trivial source change" followed by a phrase like '
            '"≥ 8 changed non-blank" -- the threshold is read from that bullet '
            "specifically, so rewording it requires updating this pattern."
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


_C_ESCAPES = {"\\": "\\", '"': '"', "t": "\t", "n": "\n", "r": "\r",
              "a": "\a", "b": "\b", "f": "\f", "v": "\v"}


def _unquote_c(body: str) -> str:
    """Decode git's C-style path quoting (the text inside the double quotes).

    Git quotes a diff path when it contains a space, a quote, a backslash or a
    non-printable byte. Octal escapes carry raw UTF-8 bytes, so consecutive ones
    are buffered and decoded together rather than one byte at a time."""
    out: list[str] = []
    raw = bytearray()

    def flush() -> None:
        if raw:
            out.append(raw.decode("utf-8", "replace"))
            raw.clear()

    i = 0
    while i < len(body):
        ch = body[i]
        if ch == "\\" and i + 1 < len(body):
            nxt = body[i + 1]
            if nxt in _C_ESCAPES:
                flush()
                out.append(_C_ESCAPES[nxt])
                i += 2
                continue
            m = re.match(r"\\([0-7]{1,3})", body[i:])
            if m:
                raw.append(int(m.group(1), 8) & 0xFF)
                i += len(m.group(0))
                continue
        flush()
        out.append(ch)
        i += 1
    flush()
    return "".join(out)


def _normalise_header_path(
    payload: str, side: str, strip_prefix: bool = True
) -> str | None:
    """Normalise a `---`/`+++` header payload to a repo-relative path.

    Handles the three diff forms this checker accepts (see README.md, "Accepted
    diff formats"):

        git             a/lib/foo.py                -> lib/foo.py
        git, quoted     "a/lib/my foo.py"           -> lib/my foo.py
        plain unified   lib/foo.py<TAB>2026-07-28.. -> lib/foo.py

    Returns None for /dev/null. The tab split happens before unquoting, which is
    safe because a quoted path's closing quote precedes any timestamp, and a tab
    *inside* a quoted path is escaped as `\\t` rather than appearing raw.

    `strip_prefix` resolves a genuine ambiguity: `--- a/lib/foo.py` could be a git
    side prefix, or a plain diff of a real path under a top-level directory named
    `a`. The header alone cannot say. The caller decides from format context --
    `parse_diff` strips only when the diff carries a `diff --git` line."""
    payload = payload.split("\t", 1)[0].strip()
    if len(payload) >= 2 and payload.startswith('"') and payload.endswith('"'):
        payload = _unquote_c(payload[1:-1])
    if payload == "/dev/null":
        return None
    return re.sub(rf"^{side}/", "", payload) if strip_prefix else payload


def _parse_diff_git(line: str) -> tuple[str | None, str | None]:
    """Return (old, new) from a `diff --git` line, or (None, None) if unparseable.

    Best-effort by design: for any diff carrying content the `---`/`+++` headers
    are authoritative, so an unparseable `diff --git` costs nothing. It matters
    only for a pure rename with no hunks, which contributes no changed lines but
    can still match a path_glob."""
    rest = line[len("diff --git "):].strip()
    m = re.match(r'^("(?:[^"\\]|\\.)*"|\S+)\s+("(?:[^"\\]|\\.)*"|\S+)$', rest)
    if not m:
        return None, None
    paths: list[str | None] = []
    for tok, side in zip(m.groups(), ("a", "b")):
        if tok.startswith('"') and tok.endswith('"'):
            tok = _unquote_c(tok[1:-1])
        paths.append(None if tok == "/dev/null" else re.sub(rf"^{side}/", "", tok))
    return paths[0], paths[1]


def parse_diff(text: str) -> tuple[set[str], dict[str, list[str]], dict[str, list[str]]]:
    """Return (changed paths, added lines by NEW path, removed lines by OLD path).

    The two sides are tracked separately because a rename can move content across
    the `source_exts` boundary: the `-` lines belong to the *old* path and the `+`
    lines to the *new* one. Attributing both to the new path undercounts a source
    file renamed to a non-source extension, since the README counts changed lines
    "across source files" and a modified line counts as both its `-` and its `+`.

    Changed content lines are added (`+`) and removed (`-`) lines only -- never the
    `+++`/`---`/`@@` headers and never context lines. `in_hunk` tracking keeps a
    removed line that happens to read `--- foo` from being mistaken for a file
    header, which is a real ambiguity in the unified-diff format."""
    changed_paths: set[str] = set()
    added: dict[str, list[str]] = {}
    removed: dict[str, list[str]] = {}
    old_path: str | None = None
    new_path: str | None = None
    in_hunk = False
    # A `diff --git` line anywhere marks the whole input as git format, which is
    # what licenses stripping the `a/` / `b/` side prefixes. Without one, a leading
    # `a/` is a real path component and must be preserved.
    git_format = "\ndiff --git " in "\n" + text

    for line in text.splitlines():
        if line.startswith("diff --git "):
            in_hunk = False
            old_path, new_path = _parse_diff_git(line)
            for p in (old_path, new_path):
                if p:
                    changed_paths.add(p)
            continue

        if line.startswith("@@"):
            in_hunk = True
            continue

        if not in_hunk and line.startswith("--- "):
            old_path = _normalise_header_path(line[4:], "a", git_format)
            if old_path:
                changed_paths.add(old_path)
            continue

        if not in_hunk and line.startswith("+++ "):
            new_path = _normalise_header_path(line[4:], "b", git_format)
            if new_path:
                changed_paths.add(new_path)
            continue

        if line.startswith("+"):
            if new_path:
                added.setdefault(new_path, []).append(line[1:])
        elif line.startswith("-"):
            if old_path:
                removed.setdefault(old_path, []).append(line[1:])

    return changed_paths, added, removed


def is_test_path(path: str, cfg: dict) -> bool:
    return path_matches_any(path, cfg["test_globs"]) is not None


def is_source_path(path: str, cfg: dict) -> bool:
    ext = os.path.splitext(path)[1].lower()
    return ext in cfg["source_exts"] and not is_test_path(path, cfg)


def nontrivial_source_line_count(
    added: dict[str, list[str]], removed: dict[str, list[str]], cfg: dict
) -> int:
    """Changed non-blank lines in source files. A source file has an extension in
    source_exts AND a path that does not match test_globs. A modified line counts
    twice (once as `-`, once as `+`) -- deliberately mechanical, per the README.

    Each side is classified by its own path, so a rename across the source_exts
    boundary counts the side that really was a source file."""
    total = 0
    for path, lines in added.items():
        if is_source_path(path, cfg):
            total += sum(1 for ln in lines if ln.strip())
    for path, lines in removed.items():
        if is_source_path(path, cfg):
            total += sum(1 for ln in lines if ln.strip())
    return total


def select(diff_text: str, lenses: list[dict], cfg: dict) -> tuple[list[str], dict]:
    changed_paths, added, removed = parse_diff(diff_text)
    changed_lines = [ln for side in (added, removed) for lines in side.values()
                     for ln in lines]

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
            count = nontrivial_source_line_count(added, removed, cfg)
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
        changed_paths, added, removed = parse_diff(text)
        print(f"{path}")
        print(f"  changed paths: {', '.join(sorted(changed_paths)) or '(none)'}")
        print(f"  source lines:  "
              f"{nontrivial_source_line_count(added, removed, cfg)} "
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
