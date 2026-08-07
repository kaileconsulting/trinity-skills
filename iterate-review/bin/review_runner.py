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
    <diff text>
    === PRIOR PASSES ===
    <prior pass-log text, or "(none — this is pass 1)">

Every block is normalized to end with exactly one newline before the next
part begins; the parts themselves are otherwise verbatim.

Stdlib-only, Python >= 3.9.
"""

from __future__ import annotations

import hashlib
import os
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
# Conventional handoff area for model-written diff/intent files: inside the
# trusted boundary, outside any scope's lock-guarded directory.
INBOX = STATE_ROOT / "inbox"
REVIEWER_PROMPT = SKILL_ROOT / "reviewer-prompt.md"
SCHEMA_PATH = SKILL_ROOT / "reviewer-output.schema.json"
LENS_DIR = SKILL_ROOT / "lenses"

PASS_LOG_DIRNAME = os.path.join("docs", "reviews")
NO_PRIOR_PASSES = "(none — this is pass 1)"


class CompositionError(Exception):
    """A composition input could not be read/parsed. Message is user-facing."""


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


def read_prior_passes(log_path: Path) -> str:
    """The runner READS the pass log for the PRIOR PASSES block; it never
    writes it — the model is the sole log writer."""
    try:
        return log_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    except OSError as exc:
        raise CompositionError(f"pass log unreadable: {exc}") from None


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
    debug/ namespace, timestamped, never pass-N.* — a standalone run during a
    live run-pass cannot overwrite or interleave published state."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    debug_dir = state_dir / "debug"
    return (debug_dir / f"{stamp}-{lens_id}.input.txt",
            debug_dir / f"{stamp}-{lens_id}.response.json")
