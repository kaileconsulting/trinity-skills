"""Reference implementation of iterate-plan's §4 open-question freeze
counting semantics (Trinity v2.4 Phase 0, `iterate-plan/SKILL.md` step 7's
"Open-question freeze tracking").

Not invoked by any runner -- freezing is an editor fold-time judgment
call (the equivalence decision is the editor's, not this module's), not
code the loop consults for control flow. This module pins the exact
*counting* algorithm executable-ly, since prose alone left a genuine
ambiguity (Phase 0 pass 1, senior-dev finding): does the first answered
pass in a streak count toward N, or does N require N pairwise
*comparisons* (i.e. N+1 answered passes)? This module -- and the fixed
worked example in SKILL.md -- settle it explicitly: **the first answered
pass after any reset trivially becomes counted-pass #1** (it has nothing
to differ from yet, so it can't fail the equivalence check), and each
subsequent pass whose answer is equivalent to the immediately preceding
counted pass increments the streak by one. Freezing fires when the
streak reaches `FREEZE_N`.

A pass is represented as one of:
    ("failed",)            -- a FAILED-lens pass: never counts, never resets
    ("answer", <token>)    -- a fully-completed pass with one settled,
                               merged answer; <token> is an opaque equality
                               key standing in for "the editor's semantic-
                               equivalence judgment of this pass's merged
                               answer" -- equal tokens mean the editor
                               judged the answers equivalent. This module
                               only does the counting; the equivalence
                               judgment itself stays the editor's, upstream
                               of this function.
    ("disagreement",)      -- an escalated cross-lane disagreement (step 7:
                               lenses disagree, never averaged): there is no
                               single settled answer this pass to serve as a
                               baseline, so this always resets the streak to
                               *no baseline at all* -- distinct from a
                               differing `("answer", token)`, which resets to
                               a fresh streak of 1 because it DOES have a
                               real answer to start counting from. A
                               disagreement is never treated as a neutral
                               skip like `("failed",)`: skipping would let
                               answers straddling an unresolved disagreement
                               form one continuous streak and freeze a
                               question that was never actually settled.

Reopening (a plan edit touching the question, or a lens answering with
genuinely new evidence) and the human's unfreeze override are both
modeled the same way: reset the tracker's state to `None` and resume
calling `advance()` -- there is no separate "reopen" verb in this module
because, at the counting layer, reopening *is* a state reset. What
differs between an editor-judged reopen and a human-directed unfreeze is
only how the plan's inline annotation records *why* -- that lives in
SKILL.md prose, not here. `keep-active` is simpler still: a question
marked keep-active is simply never passed through `advance()` at all,
by construction -- there is nothing for this module to model.
"""

from __future__ import annotations

FREEZE_N = 3


def advance(state, pass_record):
    """`state`: `(streak, last_token)` or `None` for "no streak yet" (a
    fresh question, one just reset by a reopen/unfreeze, or one just
    reset by an escalated disagreement).
    `pass_record`: `("failed",)`, `("disagreement",)`, or `("answer", token)`.

    Returns `(new_state, frozen)` -- `frozen` is True exactly on the pass
    whose answer completes the Nth consecutive equivalent streak."""
    if pass_record[0] == "failed":
        return state, False  # neither counts nor resets (mirrors the stall
                              # guardrail's own FAILED-pass treatment)

    if pass_record[0] == "disagreement":
        return None, False  # always resets to no-baseline -- there is no
                             # settled answer this pass to count from, and
                             # treating it as a neutral skip (like FAILED)
                             # would let a streak span an unresolved
                             # disagreement

    _, token = pass_record
    if state is None or token != state[1]:
        new_state = (1, token)  # baseline, or a differing answer restarting the streak
    else:
        new_state = (state[0] + 1, token)

    return new_state, new_state[0] >= FREEZE_N


def run(passes):
    """Run a full sequence of `pass_record`s from a fresh (unfrozen,
    non-keep-active) state. Returns the 0-based index of the pass at
    which freezing first fires, or `None` if it never does. Once frozen,
    subsequent passes aren't evaluated -- mirrors "don't re-answer a
    frozen question absent new evidence"; a lens *with* new evidence
    reopens it, which is a fresh `run()` starting over from `None`."""
    state = None
    for i, record in enumerate(passes):
        state, frozen = advance(state, record)
        if frozen:
            return i
    return None
