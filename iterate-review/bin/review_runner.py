#!/usr/bin/env python3
"""iterate-review's adapted runner half: composition, log naming, lens runs.

This module is the ADAPTED (skill-specific) half of the runner design — the
parts that legitimately differ between iterate-review and iterate-plan: lens
input composition, matched-context framing, and pass-log naming. The
skill-agnostic machinery (locks, atomic publication, codex invocation,
validation, the summary contract) lives in runner_shared.py and must stay
there — see docs/runner-scripts-artifact-hygiene-2026-08-06.md, Phase 3.

Composition is DETERMINISTIC by contract: the same reviewer prompt, lens
record, intent, diff, and prior-pass text produce a byte-identical input file.
The canonical assembly (pinned by the goldens in examples/composition/):

    <reviewer-prompt.md, verbatim>
    <lens body — everything after the frontmatter's closing ---, verbatim>
    ---
    === INTENT ===
    [<lens-id> lens framing] <matched_context, folded to one line>
    <blank line>
    <intent text>
    === DIFF ===
    <reviewed diff text — the diff minus runner-applied exclusions>
    === PRIOR PASSES ===
    <prior pass-log text, or "(none — this is pass 1)">

Every block is normalized to end with exactly one newline before the next
part begins; the parts themselves are otherwise verbatim.

Stdlib-only, Python >= 3.9.
"""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

# Self-sufficient import: works when run through the bin/ CLIs (which put
# this directory on sys.path) AND when loaded by file path via importlib
# (the fixture checkers do that).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner_shared as shared  # noqa: E402
import selection_engine as sel  # noqa: E402

SKILL_ROOT = Path(__file__).resolve().parent.parent
STATE_ROOT = SKILL_ROOT / "state"
REVIEWER_PROMPT = SKILL_ROOT / "reviewer-prompt.md"
SCHEMA_PATH = SKILL_ROOT / "reviewer-output.schema.json"
LENS_DIR = SKILL_ROOT / "lenses"

PASS_LOG_DIRNAME = os.path.join("docs", "reviews")
NO_PRIOR_PASSES = "(none — this is pass 1)"


class CompositionError(Exception):
    """A composition input could not be read/parsed. Message is user-facing."""


SCOPE_TAG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def validate_scope_tag(scope_tag: str) -> str:
    """Scope tags flow into filenames, state-dir hashes, and the pass-log
    header capability — constrain them to a boring charset so a crafted tag
    can't smuggle path components or masquerade as arbitrary document
    headings."""
    if not SCOPE_TAG_RE.match(scope_tag):
        raise CompositionError(
            f"invalid scope tag {scope_tag!r}: use letters, digits, dot, "
            f"underscore, hyphen (must start alphanumeric)")
    return scope_tag


# --------------------------------------------------------------------------
# Lens record reading (body + matched_context)
# --------------------------------------------------------------------------

def read_lens_record(lens_id: str):
    """Return (body_text, matched_context) for a lens record.

    body = everything after the frontmatter's closing `---`, verbatim.
    matched_context = the frontmatter's folded scalar, joined to one line
    (YAML `>` semantics as the skill has always applied them: continuation
    lines joined with single spaces).

    Defense in depth: the CLIs validate lens ids against load_lenses(), and
    this rejects separator/traversal components outright so an id can never
    address a file outside lenses/."""
    if os.sep in lens_id or (os.altsep and os.altsep in lens_id) \
            or ".." in lens_id:
        raise CompositionError(f"invalid lens id: {lens_id!r}")
    path = LENS_DIR / f"{lens_id}.md"
    try:
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    except OSError as exc:
        raise CompositionError(f"lens record unreadable: {exc}") from None
    if not lines or lines[0].strip() != "---":
        raise CompositionError(f"{path}: expected frontmatter to open with '---'")
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        raise CompositionError(f"{path}: unterminated frontmatter")

    body = "".join(lines[end + 1:])

    mc_parts = []
    in_mc = False
    for raw in lines[1:end]:
        line = raw.rstrip("\n")
        if not line.startswith((" ", "\t")) and in_mc:
            in_mc = False
        if line.split("#", 1)[0].strip() == "matched_context: >" or \
                line.startswith("matched_context:"):
            in_mc = True
            inline = line.partition(":")[2].strip()
            if inline and inline != ">":
                mc_parts.append(inline)
            continue
        if in_mc and line.strip():
            mc_parts.append(line.strip())
    return body, " ".join(mc_parts)


# --------------------------------------------------------------------------
# Deterministic composition
# --------------------------------------------------------------------------

def _block(text: str) -> str:
    """Normalize a part to end with exactly one newline."""
    return text.rstrip("\n") + "\n"


def compose_input(reviewer_prompt: str, lens_id: str, lens_body: str,
                  matched_context: str, intent: str, diff: str,
                  prior: str) -> str:
    """Assemble one lens's Codex input. Deterministic: same inputs →
    byte-identical output. Golden-pinned in examples/composition/."""
    framing = ""
    if matched_context:
        framing = _block(f"[{lens_id} lens framing] {matched_context}") + "\n"
    return (
        _block(reviewer_prompt)
        + _block(lens_body)
        + "---\n"
        + "=== INTENT ===\n"
        + framing
        + _block(intent)
        + "=== DIFF ===\n"
        + _block(diff)
        + "=== PRIOR PASSES ===\n"
        + _block(prior if prior.strip() else NO_PRIOR_PASSES)
    )


def compose_for_lens(lens_id: str, intent: str, diff: str, prior: str) -> str:
    try:
        prompt = REVIEWER_PROMPT.read_text(encoding="utf-8")
    except OSError as exc:
        raise CompositionError(f"reviewer prompt unreadable: {exc}") from None
    body, mc = read_lens_record(lens_id)
    return compose_input(prompt, lens_id, body, mc, intent, diff, prior)


# --------------------------------------------------------------------------
# Scope hash + pass-log resolution
# --------------------------------------------------------------------------

def scope_hash(scope_tag: str, log_path: Path) -> str:
    """sha1 of `<scope-tag>|<pass-log-path>` — same key SKILL.md has always
    used for the state file and directory."""
    return hashlib.sha1(f"{scope_tag}|{log_path}".encode("utf-8")).hexdigest()


def resolve_log_path(scope_tag: str, override=None, cwd=None):
    """Return (log_path, warnings). Default lands in <repo-root>/docs/reviews/
    (created on demand by the caller that holds the lock — this function only
    resolves). --log-path overrides verbatim; existing logs elsewhere are
    never touched, never migrated."""
    if override is not None:
        return Path(override).resolve(), []
    root, warnings = shared.resolve_repo_root(cwd)
    return (root / PASS_LOG_DIRNAME / f"code-review-{scope_tag}.md"), warnings


def read_prior_passes(log_path: Path, scope_tag: str, boundaries=None) -> str:
    """The runner READS the pass log for the PRIOR PASSES block; it never
    writes it — the model is the sole log writer. With `boundaries` (the
    CLIs pass [repo_root]), the read is identity-anchored via
    shared.read_trusted_text so a pathname swapped between validation and
    read can never pull out-of-boundary content into the prompt.

    The log's own format is the read capability: a pass log created by this
    skill always opens with `# Code Review — <scope-tag>`, so an existing
    file is read ONLY if its first line is exactly that header (no
    whitespace tolerance) for THIS invocation's scope tag. Scope of the
    guarantee, stated precisely: no file lacking a pass-log header can ever
    enter the codex prompt via --log-path. Because the tag is
    caller-supplied, a caller could adopt ANOTHER review's tag and read
    that review's log — but only by also adopting its identity (same tag →
    same scope hash → same state dir), and same-repo pass logs are review
    history of this same repository, already inside the confidentiality
    boundary. A missing file is simply pass 1."""
    if boundaries is not None:
        try:
            _real, text = shared.read_trusted_text(
                log_path, boundaries, "pass log", missing_ok=True)
        except shared.TrustedPathError as exc:
            raise CompositionError(str(exc)) from None
        if text is None:
            return ""
    else:
        try:
            text = log_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""
        except OSError as exc:
            raise CompositionError(f"pass log unreadable: {exc}") from None
    expected = f"# Code Review — {scope_tag}"
    first = text.splitlines()[0] if text else ""
    if first != expected:
        raise CompositionError(
            f"{log_path} exists but is not this review's pass log (first "
            f"line {first!r}, expected {expected!r}) — refusing to read it "
            f"as prior-pass context")
    return text


_PASS_HEADER_RE = re.compile(r"^## Pass (\d+) — (.+)$", re.MULTILINE)


def summarize_prior_passes(prior_text: str) -> dict:
    """Cheap defense-in-depth signal, echoed in the pass summary: how many
    prior HISTORICAL pass sections the resolved log already holds, and the
    oldest one's header line.

    SKILL.md's own steps 7-8 already have the orchestrator detect prior
    passes and surface a scope summary to the human before the first Codex
    call — this exists as a second line of defense for exactly the failure
    mode where that manual step gets skipped: a resolved log path that
    collides with an unrelated review's history (e.g. two different
    features both landing on the generic `--scope=working` default) is now
    visible directly in run-pass's own JSON output, not only in prose the
    orchestrator has to remember to read first.

    Returns {"count": 0, "first_pass_header": None} for an empty/missing
    log (this is genuinely pass 1, nothing to flag)."""
    if not prior_text:
        return {"count": 0, "first_pass_header": None}
    matches = _PASS_HEADER_RE.findall(prior_text)
    if not matches:
        return {"count": 0, "first_pass_header": None}
    first_num, first_rest = matches[0]
    return {"count": len(matches), "first_pass_header": f"Pass {first_num} — {first_rest}"}


# --------------------------------------------------------------------------
# Diff sectioning + runner-applied exclusion (docs/review-diff-exclusions-*)
# --------------------------------------------------------------------------
#
# Exclusion DELETES reviewed content, so this parser is strict where
# selection_engine.parse_diff is best-effort: a wrong guess there changes
# which lenses run; a wrong guess here would silently drop code from review.
# Any doubt about any section's identity is a DiffParseError, and the caller
# then excludes NOTHING (self-exclusion is skipped with a warning).
#
# Contract (plan §0): `git diff` output only — sections begin at a
# `diff --git` line and run to the next one; default a/ b/ prefixes
# required; C-style quoted paths decoded; a section is kept or removed as
# raw text, never re-rendered; hunk-less sections (rename-only, mode-only,
# binary) are sections like any other.

class DiffParseError(Exception):
    """A section's identity could not be established. Message is user-facing."""


# Extended header lines git emits between `diff --git` and the first hunk.
_HEADER_PREFIXES = (
    "old mode ", "new mode ", "deleted file mode ", "new file mode ",
    "similarity index ", "dissimilarity index ", "index ",
)
_HUNK_RE = re.compile(r"^@@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? @@")
_QUOTED = r'"(?:[^"\\]|\\.)*"'


def _split_lines(text: str) -> list:
    """Split on "\n" ONLY, keeping the terminators. str.splitlines() would
    also split on \r, \f, \x1c,   …, which can sit inside a diff
    content line and would shift section boundaries."""
    parts = text.split("\n")
    lines = [part + "\n" for part in parts[:-1]]
    if parts[-1]:
        lines.append(parts[-1])
    return lines


def _decode_path(token: str) -> str:
    if len(token) >= 2 and token.startswith('"') and token.endswith('"'):
        return sel._unquote_c(token[1:-1])
    return token


def _strip_side(path: str, side: str, where: str) -> str:
    if not path.startswith(side + "/"):
        raise DiffParseError(
            f"{where}: path {path!r} lacks the default {side}/ prefix")
    return path[len(side) + 1:]


def _parse_git_line(line: str):
    """(old, new) from `diff --git <a> <b>`, or None when the unquoted form
    is ambiguous (git does not quote spaces, so `a/x y b/z w` has several
    readings). The unambiguous unquoted form is `a/P b/P`; a rename's exact
    paths come from its `rename from`/`rename to` lines instead."""
    rest = line[len("diff --git "):].rstrip("\n")
    m = re.match(rf"^({_QUOTED}|\S+) ({_QUOTED}|\S+)$", rest)
    if m:
        old, new = (_decode_path(t) for t in m.groups())
        return (_strip_side(old, "a", "diff --git"),
                _strip_side(new, "b", "diff --git"))
    if rest.startswith("a/") and (len(rest) - 5) % 2 == 0:
        half = (len(rest) - 5) // 2
        p = rest[2:2 + half]
        if rest == f"a/{p} b/{p}":
            return p, p
    if rest.startswith('"') or rest.endswith('"'):
        raise DiffParseError(f"unparseable diff --git line: {line.rstrip()!r}")
    return None


def _header_path(payload: str, side: str):
    """`---`/`+++` payload → repo path, or None for /dev/null."""
    payload = payload.rstrip("\n")
    if "\t" in payload and not payload.startswith('"'):
        payload = payload.split("\t", 1)[0]
    payload = _decode_path(payload)
    if payload == "/dev/null":
        return None
    return _strip_side(payload, side, f"{'---' if side == 'a' else '+++'} line")


_UNSET = object()
_NO_NEWLINE = "\\ No newline at end of file"
# git's base85 alphabet; a payload line is <length char><5 chars per 4 bytes>.
_B85_LINE = re.compile(r"^[A-Za-z][0-9A-Za-z!#$%&()*+\-;<=>?@^_`{|}~]+$")
_BINARY_BLOCK = re.compile(r"^(?:literal|delta) \d+$")


def _check_binary_patch(lines: list, i: int, head: str) -> None:
    """`GIT binary patch` payload: one or two blocks, each `literal N` or
    `delta N`, base85 lines whose length character matches their width,
    then a blank line — and nothing else up to the next section."""
    n = len(lines)
    blocks = 0
    while i < n:
        if not _BINARY_BLOCK.match(lines[i].rstrip("\n")):
            raise DiffParseError(
                f"malformed binary patch block header {lines[i].rstrip()[:80]!r}")
        i += 1
        payload = 0
        while i < n and lines[i] != "\n":
            ln = lines[i].rstrip("\n")
            if not _B85_LINE.match(ln):
                raise DiffParseError(f"malformed binary patch line in {head.rstrip()!r}")
            c = ln[0]
            nbytes = ord(c) - 64 if c <= "Z" else ord(c) - 96 + 26
            if len(ln) - 1 != (nbytes + 3) // 4 * 5:
                raise DiffParseError(f"binary patch line width mismatch in {head.rstrip()!r}")
            payload += 1
            i += 1
        if payload == 0 or i >= n:
            raise DiffParseError(f"unterminated binary patch block in {head.rstrip()!r}")
        i += 1
        blocks += 1
    if blocks not in (1, 2):
        raise DiffParseError(f"binary patch has {blocks} blocks in {head.rstrip()!r}")


def _binary_marker_confirms(line: str, old, new) -> bool:
    """`Binary files <a> and <b> differ` names exactly the resolved
    endpoints. Paths may themselves contain " and ", so every split is
    tried and exactly one must match."""
    body = line.rstrip("\n")
    if not (body.startswith("Binary files ") and body.endswith(" differ")):
        return False
    mid = body[len("Binary files "):-len(" differ")]
    want = ("/dev/null" if old is None else f"a/{old}",
            "/dev/null" if new is None else f"b/{new}")
    hits, k = 0, mid.find(" and ")
    while k >= 0:
        if (_decode_path(mid[:k]), _decode_path(mid[k + 5:])) == want:
            hits += 1
        k = mid.find(" and ", k + 1)
    return hits == 1


def _agree(current, value, what: str):
    if current is not _UNSET and current != value:
        raise DiffParseError(
            f"section identity conflict on {what}: {current!r} vs {value!r}")
    return value


def _parse_section(lines: list) -> dict:
    """Identity of one section: {old_path, new_path, text, lines}, where a
    None endpoint is /dev/null (the missing side of an add or delete)."""
    head = lines[0]
    git_pair = _parse_git_line(head)
    old = new = _UNSET
    moved_old = moved_new = _UNSET
    created = deleted = False
    minus = plus = _UNSET
    i = 1
    n = len(lines)
    # Extended header.
    while i < n:
        ln = lines[i].rstrip("\n")
        if ln.startswith(("rename from ", "copy from ")):
            moved_old = _agree(moved_old, _decode_path(ln.split(" from ", 1)[1]),
                               "rename/copy source")
        elif ln.startswith(("rename to ", "copy to ")):
            moved_new = _agree(moved_new, _decode_path(ln.split(" to ", 1)[1]),
                               "rename/copy target")
        elif ln.startswith("new file mode "):
            created = True
        elif ln.startswith("deleted file mode "):
            deleted = True
        elif ln.startswith(_HEADER_PREFIXES):
            pass
        else:
            break
        i += 1
    # Body: ---/+++ then hunks, or a binary marker, or nothing.
    body_kind = "none"
    binary_marker = None
    if i < n and lines[i].startswith("--- "):
        if i + 1 >= n or not lines[i + 1].startswith("+++ "):
            raise DiffParseError(f"'---' without '+++' in section {head.rstrip()!r}")
        minus = _header_path(lines[i][4:], "a")
        plus = _header_path(lines[i + 1][4:], "b")
        i += 2
        body_kind = "hunks"
    elif i < n and lines[i].startswith("Binary files "):
        if i + 1 != n:
            raise DiffParseError(
                f"unexpected content after 'Binary files' in {head.rstrip()!r}")
        binary_marker = lines[i]
        i = n
        body_kind = "binary"
    elif i < n and lines[i].rstrip("\n") == "GIT binary patch":
        _check_binary_patch(lines, i + 1, head)
        i = n
        body_kind = "binary"
    if body_kind == "hunks":
        if i >= n:
            raise DiffParseError(f"no hunks after file headers in {head.rstrip()!r}")
        while i < n:
            m = _HUNK_RE.match(lines[i])
            if not m:
                raise DiffParseError(
                    f"expected a hunk header, got {lines[i].rstrip()[:80]!r}")
            old_left = int(m.group(1)) if m.group(1) is not None else 1
            new_left = int(m.group(2)) if m.group(2) is not None else 1
            i += 1
            after_content = False  # a no-newline marker may follow one content line
            while old_left > 0 or new_left > 0:
                if i >= n:
                    raise DiffParseError(f"truncated hunk in {head.rstrip()!r}")
                c = lines[i][:1]
                if c == "\\":
                    if not after_content or lines[i].rstrip("\n") != _NO_NEWLINE:
                        raise DiffParseError(
                            f"malformed or misplaced '\\' line in {head.rstrip()!r}")
                    after_content = False
                    i += 1
                    continue
                after_content = True
                if c == " ":
                    old_left -= 1
                    new_left -= 1
                elif c == "-":
                    old_left -= 1
                elif c == "+":
                    new_left -= 1
                else:
                    raise DiffParseError(
                        f"malformed hunk line {lines[i].rstrip()[:80]!r}")
                if old_left < 0 or new_left < 0:
                    raise DiffParseError(f"hunk overruns its header in {head.rstrip()!r}")
                i += 1
            if i < n and after_content and lines[i].rstrip("\n") == _NO_NEWLINE:
                i += 1  # the hunk's last line had no trailing newline
    elif body_kind == "none" and i < n:
        raise DiffParseError(
            f"unrecognized line {lines[i].rstrip()[:80]!r} in {head.rstrip()!r}")

    # Resolve endpoints: every present source must agree.
    if git_pair is not None:
        old = _agree(old, git_pair[0], "old path")
        new = _agree(new, git_pair[1], "new path")
    if moved_old is not _UNSET or moved_new is not _UNSET:
        if moved_old is _UNSET or moved_new is _UNSET:
            raise DiffParseError(f"half a rename/copy header in {head.rstrip()!r}")
        old = _agree(old, moved_old, "old path")
        new = _agree(new, moved_new, "new path")
    if minus is not _UNSET and minus is not None:
        old = _agree(old, minus, "old path")
    if plus is not _UNSET and plus is not None:
        new = _agree(new, plus, "new path")
    if old is _UNSET or new is _UNSET:
        raise DiffParseError(f"ambiguous section paths in {head.rstrip()!r}")
    if created and deleted:
        raise DiffParseError(f"section both creates and deletes: {head.rstrip()!r}")
    if (created or deleted) and (moved_old is not _UNSET or old != new):
        # An add or delete has ONE real path; nulling a side of a rename or
        # copy would silently erase its other endpoint.
        raise DiffParseError(
            f"file created/deleted and moved in one section: {head.rstrip()!r}")
    if minus is not _UNSET and ((minus is None) != created
                                or (plus is None) != deleted):
        raise DiffParseError(
            f"/dev/null header disagrees with file mode in {head.rstrip()!r}")
    if created:
        old = None
    if deleted:
        new = None
    if binary_marker is not None and not _binary_marker_confirms(
            binary_marker, old, new):
        raise DiffParseError(
            f"'Binary files' paths disagree with the section in {head.rstrip()!r}")
    return {"old_path": old, "new_path": new,
            "text": "".join(lines), "lines": len(lines)}


def parse_diff_sections(diff: str) -> list:
    """Split a `git diff` into identified sections (plan §0). Raises
    DiffParseError unless EVERY section's identity is established — there
    is no partial result, because a partial one could only be used to
    exclude on a guess."""
    lines = _split_lines(diff)
    starts = [i for i, ln in enumerate(lines) if ln.startswith("diff --git ")]
    if not starts:
        raise DiffParseError("no 'diff --git' sections (not git diff output)")
    if starts[0] != 0:
        # Not even whitespace: it would be dropped on rejoin (raw text, §0).
        raise DiffParseError("content before the first 'diff --git' line")
    bounds = starts + [len(lines)]
    return [_parse_section(lines[a:b]) for a, b in zip(bounds, bounds[1:])]


def count_lines(text: str) -> int:
    return len(_split_lines(text))


def apply_self_exclusion(diff: str, log_rel):
    """Drop the pass log's own sections (plan §1). Returns
    (reviewed_diff, excluded, warnings).

    A section is dropped ONLY when every endpoint that exists is the log
    itself — added, modified, mode-changed or deleted in place. A rename or
    copy whose other endpoint is any other path stays in review, whole,
    with a warning. `log_rel` is the log's repo-relative POSIX path, or
    None when it can't be expressed as one (nothing is excluded then).
    Unparseable input excludes nothing and says so: never best-effort."""
    if log_rel is None:
        return diff, [], []
    try:
        sections = parse_diff_sections(diff)
    except DiffParseError as exc:
        return diff, [], [
            f"pass-log self-exclusion skipped — the diff could not be "
            f"sectioned exactly ({exc}); the diff is reviewed unchanged"]
    kept, excluded, warnings = [], [], []
    for sec in sections:
        ends = {p for p in (sec["old_path"], sec["new_path"]) if p is not None}
        if ends == {log_rel}:
            excluded.append({"old_path": sec["old_path"],
                             "new_path": sec["new_path"],
                             "class": "pass-log", "lines": sec["lines"]})
            continue
        if log_rel in ends:
            other = sorted(ends - {log_rel})
            warnings.append(
                f"pass log {log_rel} is renamed or copied to/from "
                f"{', '.join(other)} — that section crosses the log's boundary "
                f"and stays in review, whole")
        kept.append(sec["text"])
    if not excluded:
        return diff, [], warnings
    return "".join(kept), excluded, warnings


def log_path_in_diff(log_path: Path, repo_root: Path):
    """The pass log's path as `git diff` writes it (repo-relative, POSIX),
    or None if it isn't inside the repo root."""
    try:
        rel = Path(os.path.realpath(str(log_path))).relative_to(
            os.path.realpath(str(repo_root)))
    except ValueError:
        return None
    return rel.as_posix()


def self_exclusion_target(log_path: Path, repo_root: Path, overridden: bool):
    """(log_rel, warnings) for apply_self_exclusion. Only the DEFAULT slot,
    docs/reviews/code-review-<scope-tag>.md, is trusted to be this review's
    own log: an override merely has to be an in-repo .md file, so honoring
    it here would let --log-path name any markdown path — including one
    the diff deletes, which no header check can see — and drop its section
    as "pass-log". An override therefore excludes nothing."""
    if overridden:
        return None, [
            "pass-log self-exclusion is off for a --log-path override (only "
            "the default docs/reviews/code-review-<scope-tag>.md is trusted "
            "as this review's own log); the diff is reviewed unchanged"]
    return log_path_in_diff(log_path, repo_root), []


def excluded_stderr(prog: str, excluded: list) -> str:
    """The disclosure for a diff that exclusions emptied entirely (plan §4):
    no pass is created, so stderr is where it lives."""
    lines = [f"{prog}: nothing left to review after exclusions — removed:"]
    for e in excluded:
        path = e["new_path"] or e["old_path"]
        lines.append(f"{prog}:   {e['class']} {path} ({e['lines']} lines)")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# One lens, end to end (composition → invocation → validation)
# --------------------------------------------------------------------------

def run_one_lens(lens_id: str, intent: str, diff: str,
                 prior: str, input_path: Path, response_path: Path,
                 lock=None) -> dict:
    """Compose, publish the input, invoke codex, validate the response.

    `lock` is the owning ScopeLock under run-pass — every publication goes
    through its token-fenced critical section (verify_and), so a revocation
    cannot interleave the ownership check and the filesystem mutation. None
    for standalone/debug runs, which write only to the isolated debug/
    namespace.

    Returns the per-lens summary entry:
      {status: ok|failed|rejected, response_path, exit_code, stderr_tail,
       reject_reasons?}   — failure/rejection is data, not an exception.
    """
    composed = compose_for_lens(lens_id, intent, diff, prior)
    if lock is not None:
        lock.verify()  # abort-before-work; the real gate is verify_and below
        lock.verify_and(lambda: shared.atomic_publish(input_path, composed))
    else:
        shared.atomic_publish(input_path, composed)

    # Codex writes to a run-unique STAGING path, never the final one: a
    # killed codex leaves only an ignorable staging file, and a displaced
    # run's still-writing child cannot touch a successor's artifacts. The
    # staged response is published atomically only after codex completed
    # AND inside the token-fenced critical section.
    staging = shared.staging_path_for(response_path)
    result = shared.invoke_codex(composed, SCHEMA_PATH, staging)
    entry = {
        "status": "ok",
        "response_path": str(response_path),
        "exit_code": result["exit_code"],
        "stderr_tail": result["stderr_tail"],
    }
    if result["exit_code"] != 0 or not staging.exists():
        entry["status"] = "failed"
        try:
            staging.unlink()
        except OSError:
            pass
        return entry
    if lock is not None:
        lock.verify_and(lambda: os.replace(staging, response_path))
    else:
        os.replace(staging, response_path)
    problems = shared.validate_response_file(SCHEMA_PATH, response_path)
    if problems:
        entry["status"] = "rejected"
        entry["reject_reasons"] = problems
    return entry


def debug_paths(state_dir: Path, lens_id: str):
    """Artifact paths for a standalone run-lens invocation: the isolated
    debug/ namespace, never pass-N.* — a standalone run during a live
    run-pass cannot overwrite or interleave published state. Names carry
    pid + random besides the timestamp: standalone runs take no lock, so
    two concurrent invocations for the same scope+lens must not share
    publication paths."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    unique = f"{os.getpid()}-{secrets.token_hex(4)}"
    debug_dir = state_dir / "debug"
    return (debug_dir / f"{stamp}-{unique}-{lens_id}.input.txt",
            debug_dir / f"{stamp}-{unique}-{lens_id}.response.json")
