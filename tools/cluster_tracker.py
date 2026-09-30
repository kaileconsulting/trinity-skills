"""Reference implementation of the simplification gate's component-streak
counting semantics (simplification-gate plan §1/§2, both loop skills' fold
steps: `[component: <label>]` tagging and the cluster streak).

Not invoked by any runner -- labeling a finding's component and deciding
whether two findings target the same mechanism are editor fold-time
judgments, not code the loop consults for control flow. This module pins
the *counting* algorithm executably, in the style of `freeze_tracker.py`,
so the prose rules can't be reinterpreted pass by pass.

`CLUSTER_N` is the **development-side pin, not a runtime source**: each
skill directory is independently installable by copy and a copied install
has no `tools/`, so each SKILL.md states the threshold as its own literal.
`tools/check-cluster-streak.py` asserts every such literal equals
`CLUSTER_N` (and therefore each other). Tuning is a three-place edit --
this constant plus both SKILL.md files -- that the checker keeps
consistent.

A pass is represented as one of:
    ("failed",)                   -- a pass with a FAILED lens after retry:
                                     skipped for streak purposes (neither
                                     counts nor resets), exactly as the
                                     freeze tracker treats it; a lens that
                                     didn't run says nothing about any
                                     component
    ("findings", {label: sev})    -- a completed pass; `sev` is the worst
                                     severity among that pass's *merged*
                                     findings tagged with `label` ("HIGH",
                                     "MEDIUM" or "LOW"). One pass is one
                                     observation per label, however many
                                     findings carry it. Corrections are
                                     never tagged and never appear here.

Semantics, per label:
    - A completed pass on which the label is HIGH or MEDIUM extends its
      streak by 1 (the *candidate* streak = committed streak + 1).
    - A completed pass on which the label is LOW only, or absent, resets
      its streak to 0. Absence is only a reset, never a retirement.
    - The gate fires for every label whose candidate streak reaches
      `CLUSTER_N` -- including a label already past N after a
      "fold-once-more", so the card returns on every further pass.

Outcomes applied on a pass, after the candidate streaks are computed, come
in two kinds.

Mechanism events -- facts about what happened to the code or plan, recorded
on any pass, with or without a card, including a FAILED one (lifecycle
changes made during a skipped pass still persist):
    ("retire", label)                 -- the label retires (a fold deleted
                                         the mechanism, a chunk boundary
                                         dropped it)
    ("replace", label, new_label)     -- the label retires; new_label is
                                         tracked from a fresh streak of 0

Card answers -- the human's choice on a simplification card; each must
answer a card that fired for that label on that same pass (a card is
identified by `(pass, component)`):
    ("remove", label)                 -- retire the label
    ("replace", label, new_label)     -- as above (the card's replace option
                                         and a replacing fold land the same
                                         state)
    ("narrow", label)                 -- label retained, streak reset to 0
    ("accept-risk", label)            -- label retained, streak reset to 0
                                         (the AR-<n> lifecycle owns only
                                         that finding; later merged
                                         findings on the label count)
    ("fold-once-more", label)         -- no change: the streak keeps counting
    ("split-plan", label)             -- retire the label (iterate-plan
                                         only; the new plan tracks it from 0)

The streak resets on narrow and accept-risk exist only as card answers,
because they are a human decision applied. An ordinary fold that narrows
a mechanism, or an editor's `accepted-risk` proposal on one finding, is not
a card answer: it resets nothing, and the streak keeps counting -- otherwise
the editor could defer the card with no human decision point. A retired
label may never be reused: a replacement mechanism gets a new label, which
is what lets the gate fire again correctly on it.

Checkpoint lifecycle events (an AR-<n> rejection or posture invalidation)
are never observations and have no representation here: the one
observation source is merged HIGH/MEDIUM findings at fold time.
"""

from __future__ import annotations

CLUSTER_N = 3

COUNTING = {"HIGH", "MEDIUM"}
SEVERITIES = COUNTING | {"LOW"}

CARD_ONLY = {"remove", "narrow", "accept-risk", "fold-once-more", "split-plan"}
MECHANISM_EVENTS = {"retire", "replace"}
RETIRING = {"remove", "replace", "split-plan", "retire"}


def observation(findings):
    """Collapse a completed pass's merged findings, given as
    `[(label, severity), ...]`, into the `("findings", {label: worst})`
    record -- one observation per label however many findings carry it."""
    rank = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    worst = {}
    for label, sev in findings:
        if sev not in rank:
            raise ValueError(f"unknown severity {sev!r} for {label!r}")
        if label not in worst or rank[sev] > rank[worst[label]]:
            worst[label] = sev
    return ("findings", worst)


def initial_state():
    """`(streaks, retired)`: committed streak per tracked label, and the
    set of retired labels."""
    return ({}, frozenset())


def advance(state, pass_record, outcomes=()):
    """Advance one sealed pass.

    `state`: `(streaks, retired)` as returned by `initial_state()` or a
    previous `advance()`.
    `pass_record`: `("failed",)` or `("findings", {label: severity})`.
    `outcomes`: the outcome tuples recorded on this pass (see module doc).

    Returns `(new_state, fired)` -- `fired` is the sorted list of labels
    whose candidate streak reached `CLUSTER_N` on this pass, i.e. the
    labels a simplification card is presented for before any fold on
    them."""
    streaks, retired = dict(state[0]), set(state[1])

    if pass_record[0] == "failed":
        fired = []
    elif pass_record[0] == "findings":
        observed = pass_record[1]
        for label, sev in observed.items():
            if sev not in SEVERITIES:
                raise ValueError(f"unknown severity {sev!r} for {label!r}")
            if label in retired:
                raise ValueError(f"retired label {label!r} reused; a "
                                 "replacement mechanism needs a new label")
        for label in set(streaks) | set(observed):
            if observed.get(label) in COUNTING:
                streaks[label] = streaks.get(label, 0) + 1
            else:
                streaks[label] = 0
        fired = sorted(l for l, n in streaks.items() if n >= CLUSTER_N)
    else:
        raise ValueError(f"unknown pass record {pass_record!r}")

    for outcome in outcomes:
        kind, label = outcome[0], outcome[1]
        if kind not in CARD_ONLY and kind not in MECHANISM_EVENTS:
            raise ValueError(f"unknown outcome {outcome!r}")
        if kind in CARD_ONLY and label not in fired:
            raise ValueError(f"{kind!r} on {label!r} answers no card "
                             "presented this pass")
        if kind in RETIRING:
            streaks.pop(label, None)
            retired.add(label)
        if kind == "replace":
            new_label = outcome[2]
            if new_label in retired or new_label in streaks:
                raise ValueError(f"replacement label {new_label!r} is not new")
            streaks[new_label] = 0
        elif kind in ("narrow", "accept-risk"):
            streaks[label] = 0

    return (streaks, frozenset(retired)), fired


def run(passes):
    """Run a full sequence of `(pass_record, outcomes)` pairs from a fresh
    state. Returns `(fired_by_pass, final_state)` -- `fired_by_pass` is a
    list, one entry per pass, of the labels a card fired for."""
    state = initial_state()
    fired_by_pass = []
    for record, outcomes in passes:
        state, fired = advance(state, record, outcomes)
        fired_by_pass.append(fired)
    return fired_by_pass, state
