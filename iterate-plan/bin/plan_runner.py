#!/usr/bin/env python3
"""iterate-plan's adapted runner half: composition, section slicing, lens runs.

This module is the ADAPTED (skill-specific) half of the runner design — the
parts that legitimately differ between iterate-plan and iterate-review: lens
selection (trivial here — every lens is `always: true`), required-section
extraction, and plan-file composition. The skill-agnostic machinery (locks,
atomic publication, codex invocation, validation, the summary contract) lives
in runner_shared.py and must stay there — it is duplicated byte-identically
from the sibling skill and hash-checked by tools/check-parity.py.

Composition is DETERMINISTIC by contract: the same reviewer prompt, lens
record, plan text, and staged note produce a byte-identical input file. The
canonical assembly (pinned by the goldens in examples/composition/):

    <reviewer-prompt.md, verbatim>
    <lens body — everything after the frontmatter's closing ---, verbatim>
    ---
    === NOTE: HUMAN EDITS SINCE LAST PASS ===      (only when a note is staged)
    <note text>
    === MATCHED CONTEXT (sections for the <lens-id> lens) ===
    [<lens-id> lens framing] <matched_context, folded to one line>
    <blank line>
    <required-section slices, absence NOTE lines for missing sections>
    === PLAN ===
    <plan text>

Every block is normalized to end with exactly one newline before the next
part begins; the parts themselves are otherwise verbatim. Prior passes need
no separate block: iterate-plan's HISTORICAL sections live INSIDE the plan,
so the reviewer's continuity context always arrives with the plan itself.

Stdlib-only, Python >= 3.9.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

# Self-sufficient import: works when run through the bin/ CLIs (which put
# this directory on sys.path) AND when loaded by file path via importlib
# (the fixture checkers do that).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner_shared as shared  # noqa: E402

SKILL_ROOT = Path(__file__).resolve().parent.parent
STATE_ROOT = SKILL_ROOT / "state"
REVIEWER_PROMPT = SKILL_ROOT / "reviewer-prompt.md"
SCHEMA_PATH = SKILL_ROOT / "reviewer-output.schema.json"
LENS_DIR = SKILL_ROOT / "lenses"

ABSENT_SECTION_NOTE = 'NOTE: required section "{title}" is absent — flag this gap'
SELECTION_REASON = "always selected per lenses/README.md"


class CompositionError(Exception):
    """A composition input could not be read/parsed. Message is user-facing."""


# --------------------------------------------------------------------------
# Lens record reading (body + matched_context + selection data)
# --------------------------------------------------------------------------

def read_lens_record(lens_id: str):
    """Return (body_text, matched_context, selection) for a lens record.

    body = everything after the frontmatter's closing `---`, verbatim.
    matched_context = the frontmatter's folded scalar, joined to one line
    (YAML `>` semantics as the skill has always applied them: continuation
    lines joined with single spaces).
    selection = {"always": bool, "requires_sections": [titles]} — parsed
    from the `selection:` block; `requires_sections` values are canonical
    bare H2 titles (no `## ` marker), exactly as lenses/README.md defines.

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
    selection = {"always": None, "requires_sections": None}
    in_selection = False
    for raw in lines[1:end]:
        line = raw.rstrip("\n")
        indented = line.startswith((" ", "\t"))
        if not indented:
            in_mc = False
            in_selection = False
        stripped = line.strip()
        if not indented and stripped.split("#", 1)[0].strip() == "selection:":
            in_selection = True
            continue
        if in_selection and indented:
            key, _, value = stripped.partition(":")
            value = value.split("#", 1)[0].strip()
            if key.strip() == "always":
                if value not in ("true", "false"):
                    raise CompositionError(
                        f"{path}: selection.always must be true or false, "
                        f"got {value!r}")
                selection["always"] = value == "true"
            elif key.strip() == "requires_sections":
                try:
                    titles = json.loads(value)
                except ValueError:
                    raise CompositionError(
                        f"{path}: requires_sections must be a JSON-style "
                        f"list of section titles, got {value!r}") from None
                if not isinstance(titles, list) \
                        or not all(isinstance(t, str) for t in titles):
                    raise CompositionError(
                        f"{path}: requires_sections must be a list of "
                        f"strings, got {value!r}")
                selection["requires_sections"] = titles
            continue
        if line.split("#", 1)[0].strip() == "matched_context: >" or \
                line.startswith("matched_context:"):
            in_mc = True
            inline = line.partition(":")[2].strip()
            if inline and inline != ">":
                mc_parts.append(inline)
            continue
        if in_mc and stripped:
            mc_parts.append(stripped)

    if selection["always"] is None or selection["requires_sections"] is None:
        raise CompositionError(
            f"{path}: frontmatter must declare selection.always and "
            f"selection.requires_sections")
    return body, " ".join(mc_parts), selection


def load_lenses():
    """All lens records in lenses/ (README.md excluded), sorted by id.
    The record's `id:` must equal its filename stem — a mismatch is rule-data
    drift and fails loudly."""
    lenses = []
    try:
        names = sorted(os.listdir(LENS_DIR))
    except OSError as exc:
        raise CompositionError(f"lenses/ unreadable: {exc}") from None
    for name in names:
        if not name.endswith(".md") or name == "README.md":
            continue
        stem = name[:-3]
        _body, _mc, selection = read_lens_record(stem)
        declared = _frontmatter_id(LENS_DIR / name)
        if declared != stem:
            raise CompositionError(
                f"{LENS_DIR / name}: frontmatter id {declared!r} does not "
                f"match filename {stem!r}")
        lenses.append({"id": stem, **selection})
    if not lenses:
        raise CompositionError(f"no lens records found in {LENS_DIR}")
    return lenses


def _frontmatter_id(path: Path):
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0]
        key, _, value = line.partition(":")
        if key.strip() == "id":
            return value.strip()
    return None


def select_lenses(override=None):
    """Deterministic selection per lenses/README.md: every iterate-plan lens
    is `always: true`, so selection is the full lens set. A lens declaring
    `always: false` fails loudly — iterate-plan defines no conditional
    selection rules, so such a record is rule-data drift, never silently
    included or skipped. `--lenses` forces an explicit subset."""
    lenses = load_lenses()
    not_always = [lens["id"] for lens in lenses if not lens["always"]]
    if not_always:
        raise CompositionError(
            f"lens record(s) declare always: false ({', '.join(not_always)}) "
            f"but iterate-plan defines no conditional selection rules — see "
            f"lenses/README.md")
    known = {lens["id"] for lens in lenses}
    if override:
        forced = [x.strip() for x in override.split(",") if x.strip()]
        if not forced:
            raise CompositionError("--lenses was given but named no lenses")
        unknown = [x for x in forced if x not in known]
        if unknown:
            raise CompositionError(
                f"--lenses names unknown lens id(s): {', '.join(unknown)} "
                f"(known: {', '.join(sorted(known))})")
        return sorted(set(forced)), {x: ["forced via --lenses"] for x in forced}
    ids = sorted(known)
    return ids, {x: [SELECTION_REASON] for x in ids}


# --------------------------------------------------------------------------
# Required-section extraction
# --------------------------------------------------------------------------

def extract_section(plan_text: str, title: str):
    """The slice for one required H2 section, or None when absent.

    Matching is exact and case-sensitive against the canonical bare title:
    a line that is precisely `## <title>` opens the slice, and the slice
    runs up to (not including) the next `## ` heading. Sub-headings (###)
    belong to their parent section and are kept."""
    lines = plan_text.splitlines(keepends=True)
    out = []
    in_section = False
    for raw in lines:
        line = raw.rstrip("\n")
        if line == f"## {title}":
            in_section = True
            out.append(raw)
            continue
        if in_section and line.startswith("## "):
            break
        if in_section:
            out.append(raw)
    if not out:
        return None
    return "".join(out)


def extract_required_sections(plan_text: str, titles) -> str:
    """Concatenated slices for a lens's requires_sections, in declared order.
    An absent section contributes its absence NOTE line instead — the lens is
    never skipped and never handed silence about a gap (lenses/README.md)."""
    parts = []
    for title in titles:
        section = extract_section(plan_text, title)
        if section is None:
            parts.append(ABSENT_SECTION_NOTE.format(title=title))
        else:
            parts.append(section)
    return "\n".join(_block(p) for p in parts)


# --------------------------------------------------------------------------
# Deterministic composition
# --------------------------------------------------------------------------

def _block(text: str) -> str:
    """Normalize a part to end with exactly one newline."""
    return text.rstrip("\n") + "\n"


def compose_input(reviewer_prompt: str, lens_id: str, lens_body: str,
                  matched_context: str, sections: str, plan: str,
                  note: str = "") -> str:
    """Assemble one lens's Codex input. Deterministic: same inputs →
    byte-identical output. Golden-pinned in examples/composition/."""
    note_block = ""
    if note.strip():
        note_block = ("=== NOTE: HUMAN EDITS SINCE LAST PASS ===\n"
                      + _block(note))
    framing = ""
    if matched_context:
        framing = _block(f"[{lens_id} lens framing] {matched_context}") + "\n"
    return (
        _block(reviewer_prompt)
        + _block(lens_body)
        + "---\n"
        + note_block
        + f"=== MATCHED CONTEXT (sections for the {lens_id} lens) ===\n"
        + framing
        + _block(sections)
        + "=== PLAN ===\n"
        + _block(plan)
    )


def compose_for_lens(lens_id: str, plan_text: str, note: str = "") -> str:
    try:
        prompt = REVIEWER_PROMPT.read_text(encoding="utf-8")
    except OSError as exc:
        raise CompositionError(f"reviewer prompt unreadable: {exc}") from None
    body, mc, selection = read_lens_record(lens_id)
    sections = extract_required_sections(plan_text,
                                         selection["requires_sections"])
    return compose_input(prompt, lens_id, body, mc, sections, plan_text, note)


# --------------------------------------------------------------------------
# Scope hash — the plan file IS the scope
# --------------------------------------------------------------------------

def scope_hash(plan_path: Path) -> str:
    """sha1 of the plan's absolute (real) path — the same per-plan key
    SKILL.md has always used for the model's state/<hash>.json record, so
    the runner's state DIRECTORY and the model's state FILE share one key."""
    return hashlib.sha1(str(plan_path).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# One lens, end to end (composition → invocation → validation)
# --------------------------------------------------------------------------

def run_one_lens(lens_id: str, plan_text: str, note: str, plan_dir: Path,
                 input_path: Path, response_path: Path, lock=None) -> dict:
    """Compose, publish the input, invoke codex, validate the response.

    `plan_dir` becomes codex's working root (`-C`, per SKILL.md) so the
    read-only reviewer can consult the repository around the plan.

    `lock` is the owning ScopeLock under run-pass — every publication goes
    through its token-fenced critical section (verify_and), so a revocation
    cannot interleave the ownership check and the filesystem mutation. None
    for standalone/debug runs, which write only to the isolated debug/
    namespace.

    Returns the per-lens summary entry:
      {status: ok|failed|rejected, response_path, exit_code, stderr_tail,
       reject_reasons?}   — failure/rejection is data, not an exception.
    """
    composed = compose_for_lens(lens_id, plan_text, note)
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
    result = shared.invoke_codex(composed, SCHEMA_PATH, staging, cwd=plan_dir)
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
