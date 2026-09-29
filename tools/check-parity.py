#!/usr/bin/env python3
"""Assert the shared machinery is present in BOTH skills' per-pass loops.

`iterate-plan` steps 5-10 and `iterate-review` steps 9-16 are the same machine
described twice. The plan requires them kept in **semantic parity, not
byte-identity** -- the prose legitimately differs where each skill's folding,
pass-log and flag handling differ, but the *rules* must hold in both.

Since the Phase 3 runner port, this checker ALSO enforces the one place where
byte-identity IS the contract: the designated shared runner files
(`bin/runner_shared.py`, `bin/prune-state`) are duplicated between the two
skills and compared by content hash. Prose drifts semantically; shared code
drifts byte-by-byte -- a single divergent byte is a failure, because the whole
point of the duplication is that both skills run the SAME reviewed machinery.

This checker takes the "semantic" part seriously by normalising markdown before
matching: emphasis markers, backticks, dash variants and whitespace are
flattened, so a rule counts as present however it happens to be formatted. What
it cannot do is judge whether a rule is *correctly* stated -- only whether it is
stated at all. It is a drift alarm, not a proof of correctness.

Three outcomes per rule:

    OK          stated in both skills
    PARITY GAP  stated in one skill only  <- the failure this tool exists for
    MISSING     stated in neither         <- a rule was dropped, or the pattern is wrong

Usage:
    tools/check-parity.py           # summary
    tools/check-parity.py -v        # also show which line matched in each skill
"""

from __future__ import annotations

import hashlib
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = ("iterate-plan", "iterate-review")

# Designated SHARED runner files: duplicated byte-identically between the two
# skills' bin/ (runner-scripts plan, Phase 3). Everything else under bin/ is
# adapted per skill and covered by behavioral fixtures, never byte parity.
SHARED_BIN_FILES = ("runner_shared.py", "prune-state")

# (rule id, human description, patterns that must ALL appear)
#
# Patterns are matched against NORMALISED text: no emphasis markers, no
# backticks, dashes unified, whitespace collapsed, lowercased.
#
# The third element is either a list applied to both skills, or a dict of
# {skill: [patterns]} when a rule is legitimately worded per-skill -- e.g. one
# names `plan_corrections` and the other `code_corrections`. Prefer the dict form
# whenever a shared pattern would let one skill satisfy the rule using text that
# merely *references* the other's behaviour.
RULES: list[tuple[str, str, list[str] | dict[str, list[str]]]] = [
    # --- fan-out -----------------------------------------------------------
    ("fan-out-per-lens", "one Codex call per selected lens",
     [r"one codex call per selected lens"]),
    ("fan-out-concurrent", "lenses run concurrently, not serially",
     [r"concurrent|in parallel"]),
    ("per-lens-response-file", "each lens writes its own response artifact",
     [r"<lensid>\.response\.json"]),

    # --- per-response validation ------------------------------------------
    ("patch-marker-rejection", "patch-shaped output is rejected",
     [r"patch-marker", r"begin patch"]),

    # --- lens failure -----------------------------------------------------
    ("lens-retry-once", "a failing lens is retried exactly once",
     [r"retried once"]),
    ("failed-not-a-verdict", "FAILED is orchestration metadata, not a verdict",
     [r"orchestration metadata", r"not a verdict"]),
    ("failed-floor-revise", "a FAILED lens forces at-least-REVISE",
     [r"at least revise"]),
    ("failed-preserves-block", "BLOCK survives a FAILED lens (floor, not assignment)",
     [r"block is preserved"]),
    ("failed-blocks-converge", "a FAILED lens blocks Converge",
     [r"blocks converge"]),

    # --- merge ------------------------------------------------------------
    ("merge-semantic", "merge is semantic judgment, not a mechanical key",
     [r"semantic judgment", r"not a mechanical key"]),
    ("merge-dedupe-key", "collapse same location AND same defect",
     [r"same location", r"same defect"]),
    ("merge-keeps-distinct", "distinct concerns at one location stay separate",
     [r"distinct concerns"]),
    ("merge-attribution", "a co-report retains ALL contributing lens ids",
     [r"all contributing lens ids"]),
    # Per-skill: each must state the rule for ITS OWN correction field, with the
    # substance (mechanical application + the collapse key). A shared
    # `dedupe (plan|code)_corrections` pattern would let a cross-reference to the
    # sibling skill satisfy the rule without the loop instructing anything.
    ("merge-dedupe-corrections", "corrections are deduped (they apply mechanically)",
     {"iterate-plan": [r"dedupe plan_corrections",
                       r"corrections are applied mechanically",
                       r"collapse by location \+ intended fix"],
      "iterate-review": [r"dedupe code_corrections",
                         r"corrections are applied mechanically",
                         r"collapse by location \+ intended fix"]}),

    # --- new_questions classification + routing ---------------------------
    ("question-class-routing", "new_questions are routed by settled_by",
     [r"route new_questions by settled_by",
      r"resolvable_in_fold", r"needs_lookup", r"needs_human"]),
    ("question-class-conflict", "a class conflict takes the most escalating label",
     [r"most escalating"]),
    ("question-lookup-failure", "a failed lookup reclassifies to needs_human",
     [r"reclassify to needs_human"]),
    ("question-label-audited", "the settled_by label is sanity-checked, not trusted",
     [r"sanity-check the label"]),

    # --- verdict aggregation ---------------------------------------------
    ("verdict-worst-of", "aggregate verdict is worst-of",
     [r"worst-of", r"block > revise > approve"]),

    # --- single-pass invariants ------------------------------------------
    ("one-historical-block", "exactly one HISTORICAL block per pass",
     [r"one historical block"]),
    ("one-checkpoint", "exactly one checkpoint per pass",
     [r"one checkpoint per pass"]),
    ("lens-attribution-in-log", "each folded finding records its originating lens",
     [r"tagged with its originating lens id"]),
    ("lens-run-summary", "the pass log records each lens's outcome",
     [r"lens run summary"]),

    # --- loop mode --------------------------------------------------------
    ("loop-flags", "--loop / --until-approve opt-in",
     [r"--loop", r"--until-approve"]),
    ("loop-checkpoint-option", "(L)oop offered at the checkpoint",
     [r"\(l\)oop"]),
    ("loop-continue-only", "loop mode automates Continue only",
     [r"automate continue only|automates continue only"]),
    ("loop-never-converges", "loop mode never auto-converges",
     [r"never auto-converges"]),

    # --- loop-mode guardrails (five here; the sixth, the simplification card, is pinned by card-halts-fold) ---
    ("guard-approve", "guardrail: APPROVE reached halts the loop",
     [r"approve reached"]),
    ("guard-max-passes", "guardrail: max-pass cap, default 6, overridable",
     [r"max-pass cap", r"default 6", r"--max-passes"]),
    ("guard-fresh-budget", "the cap is a fresh per-activation budget",
     [r"fresh per-activation budget"]),
    ("guard-block", "guardrail: BLOCK halts the loop",
     [r"block verdict"]),
    ("guard-nonconvergence", "guardrail: HIGH+MEDIUM count must strictly decrease",
     [r"non-convergence", r"high\+medium", r"strictly decrease"]),
    ("guard-human-judgment", "guardrail: a fold needing human judgment halts",
     [r"needs human judgment",
      # Tightened with question classification: the guardrail must name which
      # class halts, not just say "a question the editor can't answer".
      r"new_question classified needs_human",
      r"do not halt the loop|does not halt the loop"]),

    # --- standing invariants ---------------------------------------------
    # The model/runner boundary (plan R1): the contract sentence must appear
    # in both SKILL.mds. The middle clause legitimately differs ("never
    # writes pass logs" vs "never writes the plan"), so it is not matched.
    ("runner-contract", "the runner composes and invokes; never folds, never decides",
     [r"the runner composes and invokes", r"never folds", r"never decides"]),
    ("never-decides-convergence", "the skill never decides convergence",
     [r"never decides convergence"]),
    ("codex-never-edits", "Codex never edits files",
     [r"codex never edits"]),
    ("editor-sole-writer", "the editor is the sole writer of folds",
     [r"sole writer"]),

    # --- fold-time hygiene checklist (v2.4 Phase 0 §2) ---------------------
    # Item 1 (claims-vs-behavior sweep) is shared verbatim; item 2 (the
    # invariant walk) is deliberately iterate-plan-only and is verified
    # directly by Phase 0's acceptance, not by parity.
    ("fold-hygiene-claims-vs-behavior", "claims-vs-behavior sweep at fold time (shared)",
     [r"test name, docstring, log line, comment",
      r"no passing test could have caught it"]),

    # --- fold-provenance instrumentation (v2.4 Phase 0 §5) -----------------
    ("provenance-field", "introduced_by_pass records per-finding fold-provenance",
     [r"introduced_by_pass"]),
    ("provenance-judgment-rule", "fold-caused iff a previous pass's fold created the defect",
     [r"created by an edit a previous pass's fold made"]),
    ("provenance-uncertain-null", "uncertainty resolves to null with a note, not a guess",
     [r"null with a one-line note"]),
    ("provenance-summary-schema", "state file carries a versioned per-pass row schema",
     [r"summary_schema: 2", r"a schema-1 file still reads"]),
    ("provenance-scope-class", "state file carries a run-level scope_class field",
     [r"scope_class"]),
    ("provenance-disposition-keys", "dispositions use one fixed key set across both skills",
     [r"fixed key set", r"accepted-risk", r"register-match"]),
    ("provenance-abort-parity", "Abort produces the passes array exactly as Converge does",
     [r"abort produces the array exactly as converge does"]),
    # Simplification gate Phase 1 lifted the v2.4 "none may consult" reservation
    # (its old wording is now FORBIDDEN below); the line it draws instead:
    ("provenance-evidence-only", "component streak is the only trigger; provenance is evidence only",
     [r"component-based triggering is permitted and is the only trigger",
      r"provenance fields .{0,80}are consumed as card evidence and for measurement only"]),

    # --- component tags + streak (simplification gate Phase 0, §1/§2) -------
    # The threshold's *value* is asserted by check-cluster-streak.py (both
    # literals equal cluster_tracker.CLUSTER_N); parity only pins presence.
    ("component-tag-placement", "[component: <label>] sits beside introduced_by_pass",
     [r"\[introduced_by_pass: <n \| null>\] \[component: <label>\]"]),
    ("component-same-mechanism", "same mechanism, same label, whatever the wording or lens",
     [r"same mechanism, same label"]),
    ("component-replacement-new-label", "a replacement mechanism gets a new label",
     [r"a replacement mechanism gets a new label"]),
    ("component-mechanism-not-location", "a label names a mechanism, never a location",
     [r"a label names a mechanism, never a location"]),
    # Per-skill: each skill's card answers differ (iterate-review offers
    # accept-the-risk, iterate-plan offers split-the-plan instead).
    ("component-lifecycles", "remove retires; replace retires + fresh label; card-answer-only resets",
     {"iterate-review": [
         r"removed .{1,3} the label retires",
         r"replaced .{1,3} the old label retires and the replacement gets a new label with a fresh streak",
         r"narrowed .{0,90} in answer to the card .{1,3} the label is retained and its streak resets to 0",
         r"accepted-risk\) .{1,3} retained, streak reset to 0",
         r"no other outcome resets a streak",
         r"a reset without a human decision would let the editor defer the card"],
      "iterate-plan": [
         r"removed .{1,3} the label retires",
         r"replaced .{1,3} the old label retires and the replacement gets a new label with a fresh streak",
         r"narrowed .{0,90} in answer to the card .{1,3} the label is retained and its streak resets to 0",
         r"split into its own plan in answer to the card .{1,3} the label retires here",
         r"no other outcome resets a streak",
         r"a reset without a card answer would let the editor defer the card"]}),
    ("component-retire-vs-reset", "retirement is explicit and persisted; absence only resets",
     [r"retirement is explicit and persisted; absence is only a reset",
      r"retired: <label> \(<why>\)"]),
    ("component-one-observation", "one pass is one observation per label",
     [r"one pass is one observation"]),
    ("component-low-excluded", "LOW findings never count toward a streak",
     [r"low findings never count"]),
    ("component-failed-skips", "a FAILED-lens pass neither counts nor resets",
     [r"failed lens after retry is skipped for streak purposes"]),
    ("component-threshold-literal", "the threshold is a literal in each SKILL.md",
     [r"the cluster threshold, \d+,"]),
    # --- simplification card (simplification gate Phase 1, §3/§4) ---------
    ("card-sixth-moment", "the simplification card is the sixth named human-judgment moment",
     [r"six named human-judgment moments", r"simplification card - the sixth named human-judgment moment"]),
    ("card-trigger-candidate-streak", "fires on the candidate streak, before the first fold on the label",
     [r"candidate streak", r"the card fires before the first fold on that label this pass"]),
    ("card-refires-after-fold-once-more", "the card returns on every further pass past the threshold",
     [r"fires again on every further pass on which a label left at or past the threshold by fold once more"]),
    ("card-no-checkpoint-observations", "checkpoint lifecycle events are never observations",
     [r"never from a checkpoint lifecycle event", r"the one observation source is merged high/medium findings at fold time"]),
    ("card-transition-order", "classify before fold; pending card; slots stay empty",
     [r"transition order - counting and presentation happen exactly once",
      r"classify every merged finding's component label and compute each label's candidate streak, before any fold",
      r"slots stay empty, so an empty slot still means unfinished work"]),
    ("card-dispositions-per-operation", "findings dispositioned by the chosen operation's accounting, never batched",
     [r"by that operation's per-finding accounting as persisted in the pending card",
      r"never the recommendation's by default, and never as a batch",
      r"never marked incorporated by association"]),
    ("card-resume", "a card is keyed by (pass, component); resume re-presents, never recounts",
     [r"a card is identified by \(pass, component\)", r"never recounts"]),
    ("card-required-fields", "every offered simplify operation carries guarantee lost / covering layer / per-finding accounting",
     [r"a card missing any of it is malformed and is not presented",
      r"for every simplification operation the card offers, recommended or alternative, three sub-fields",
      r"the guarantee lost", r"which remaining layer covers it", r"per-finding accounting",
      r"of this streak's .{0,12}findings are fold-caused"]),
    ("card-mandatory-options", "remove and fold-once-more are on every card; fold-once-more never recommended",
     [r"mandatory on every card: remove the mechanism \(the recommendation, or else the first alternative\)",
      r"fold once more \(always listed, never the recommendation\)",
      r"context-sensitive omission may drop optional options only, never the two mandatory ones"]),
    ("card-fold-once-more-reason", "fold once more records premature|deliberate; false-positive reads premature",
     [r"premature \(the card wasn't warranted\)", r"deliberate \(warranted"]),
    ("card-simplify-lifecycle", "simplify outcomes follow the component-tag lifecycle, never a rule of their own",
     [r"chosen: simplify \(remove\)", r"never a rule of its own"]),
    ("card-halts-fold", "the card halts that label's fold immediately and the loop until answered",
     [r"the loop does not continue to another pass until the card is answered"]),
    ("card-never-auto", "never an auto-stop, never an auto-simplify",
     [r"never an auto-stop, never an auto-simplify",
      r"the simplification card presents; it never stops or simplifies anything by itself"]),
    ("card-incorporated-by-simplification", "incorporated (by simplification) is incorporated for every ledger",
     [r"incorporated \(by simplification\) - a finding a simplification card's chosen operation resolves"]),
    ("card-escape-hatch", "split-the-plan (a scope transfer) is iterate-plan's slot; accept-the-risk is iterate-review's",
     {"iterate-plan": [r"split the plan \(this skill's escape hatch",
                       r"split the plan .{1,3} a scope transfer, in this order, each write durable before the next",
                       r"the card's resolution is written first",
                       r"never re-presents it: it continues the recorded transfer",
                       r"## carried findings", r"incorporated \(moved to <stub path>\)"],
      "iterate-review": [r"accept the risk when the posture permits",
                         r"accept the risk .{1,3} the existing accepted-risk lifecycle"]}),
    # Per-skill: each skill's own entry path back into an unfinished pass.
    ("block-tag-completion-marker", "a pass block is [IN PROGRESS] until its last write, then [HISTORICAL]",
     {"iterate-plan": [r"tagged \[in progress\] from the moment it opens", r"flips to \[historical\] as the last write of the pass",
                       r"the tag, not any single slot, is the pass-completion marker"],
      "iterate-review": [r"\[in progress\] while open", r"the tag, not the card, is the authoritative resume signal"]}),
    ("resume-unfinished-pass", "an interrupted pass is resumed under its own number, never a fresh fan-out",
     {"iterate-plan": [r"before any fan-out, check the plan for an unfinished pass",
                       r"resume it under its own pass number"],
      "iterate-review": [r"on resume, complete the open block; never append a second"]}),
    ("cluster-section", "cap and stall hand-backs carry the grouped-by-component cluster section",
     [r"cluster section - on the max-pass cap hand-back and the non-convergence stall card",
      r"one below the cluster threshold, \d+, - one more high/medium pass on it triggers the simplification card",
      r"it changes no guardrail's condition or outcome"]),
    ("component-summary-fields", "schema-2 rows carry observation/components/streaks/retired/cards",
     [r"observation", r"components", r"streaks", r"retired", r"cards", r"counts, not booleans"]),

    # --- accepted-risk disposition + lifecycle (v2.4 Phase 1 port) --------
    # `iterate-review` shipped this in v2.3.0; `iterate-plan` gained it in
    # Phase 1. Wording legitimately differs (a plan has no diff/base
    # revision to anti-game against, so the trust-boundary dual-check
    # compares "start of this pass" instead of "base revision" -- see the
    # per-skill dict rule below) but the *rules* below must hold in both.
    ("accepted-risk-disposition-definition", "accepted-risk = real finding, disproportionate to posture",
     [r"real finding, disproportionate to"]),
    ("accepted-risk-lifecycle-named", "the identity + lifecycle section is present",
     [r"identity and lifecycle"]),
    ("accepted-risk-material-change", "a materially changed finding mints a new AR id, never reuses one",
     [r"materially changed", r"new proposal under a new id"]),
    ("accepted-risk-posture-dependency-descriptor", "confirmations persist a posture-field dependency descriptor + digest",
     [r"posture-dependency descriptor"]),
    ("accepted-risk-invalidation-preserves-id", "a posture-digest mismatch returns to proposed, keeping the same AR id",
     [r"invalidation always preserves the"]),
    ("accepted-risk-accounting-table", "one table, three consumers, defines every lifecycle state's standing",
     [r"accounting is defined per ledger, per state"]),
    ("accepted-risk-converge-predicate", "Converge is blocked while any AR- id is proposed or reopened",
     [r"converge predicate", r"zero items in.*proposed.*or.*reopened"]),
    ("accepted-risk-pushback-anti-criteria", "never push back on a trust boundary or to dodge a cheap honest fix",
     [r"anti-criteria", r"named as a trust boundary"]),
    ("accepted-risk-trust-boundary-unavailable", "accepted-risk/register-match are unavailable for PF-shipbar trust-boundary content",
     [r"are unavailable for", r"trust boundary in", r"pf-shipbar"]),
    ("register-match-trust-boundary-gate", "a register-match gate named specifically for trust-boundary exclusion",
     [r"trust-boundary gate"]),

    # --- decision-card shared contract (v2.4 Phase 1 port) -----------------
    ("decision-card-cardinality-bound", "recommendation + alternatives never exceed the harness's 4-option cap",
     [r"cardinality is bound by the harness"]),
    ("decision-card-two-phase-persistence", "cards are written (pending) before presentation, resolved once answered",
     [r"pending write, before presentation", r"resolution write, once answered"]),
    ("decision-card-floor-never-skipped", "recommendation + discuss is the floor and is always presented",
     [r"recommendation \+ discuss is the floor and is always presented, never skipped"]),
    ("malformed-source-halts-before-fanout", "a malformed posture/register source halts before any lens runs",
     [r"halts before fan-out with a decision card rather than silently"]),
]


# Phrases that must be ABSENT (same normalisation). A rule id maps to
# {skill: [patterns]}; any match fails. This is how a deliberate asymmetry is
# pinned from the sibling's side ("the sibling lacks it"), and how a lifted
# rule's old wording is kept from lingering in any copy.
FORBIDDEN: list[tuple[str, str, dict[str, list[str]]]] = [
    ("provenance-reservation-lifted", "the v2.4 'none may consult introduced_by_pass' wording is gone",
     {"iterate-plan": [r"none may until that issue is resolved", r"this ships data collection only",
                       r"introduced_by_pass is data collection only"],
      "iterate-review": [r"none may until that issue is resolved", r"this ships data collection only",
                         r"introduced_by_pass is data collection only"]}),
    ("split-plan-iterate-plan-only", "split-the-plan exists in iterate-plan only",
     {"iterate-plan": [], "iterate-review": [r"split the plan", r"split-plan"]}),
    ("accept-risk-not-on-plan-card", "iterate-plan's simplification card does not offer accept-the-risk",
     {"iterate-plan": [r"accept the risk when the posture permits"], "iterate-review": []}),
]


def normalise(text: str) -> str:
    text = text.replace("*", "").replace("`", "")
    text = text.replace("—", "-").replace("–", "-").replace("≥", ">=")
    text = re.sub(r"\s+", " ", text)
    return text.lower()


def load(skill: str) -> tuple[str, list[str]]:
    path = os.path.join(REPO, skill, "SKILL.md")
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    return normalise(raw), raw.splitlines()


def first_line_matching(pattern: str, lines: list[str]) -> int | None:
    rx = re.compile(pattern)
    for i, line in enumerate(lines, 1):
        if rx.search(normalise(line)):
            return i
    return None


def main(argv: list[str]) -> int:
    verbose = "-v" in argv or "--verbose" in argv

    for skill in SKILLS:
        path = os.path.join(REPO, skill, "SKILL.md")
        if not os.path.exists(path):
            print(f"error: {path} not found", file=sys.stderr)
            return 2

    docs = {s: load(s) for s in SKILLS}

    gaps: list[str] = []
    missing: list[str] = []
    width = max(len(r[0]) for r in RULES)

    print("shared-machinery parity: iterate-plan <-> iterate-review")
    print(f"{len(RULES)} rules, matched against markdown-normalised text\n")

    def pats_for(patterns, skill: str) -> list[str]:
        return patterns[skill] if isinstance(patterns, dict) else patterns

    for rule_id, desc, patterns in RULES:
        if isinstance(patterns, dict):
            missing_skills = [s for s in SKILLS if s not in patterns]
            if missing_skills:
                print(f"error: rule {rule_id} has per-skill patterns but none "
                      f"for {', '.join(missing_skills)}", file=sys.stderr)
                return 2

        present = {}
        for skill in SKILLS:
            norm, _lines = docs[skill]
            present[skill] = all(
                re.search(p, norm) for p in pats_for(patterns, skill))

        have = [s for s in SKILLS if present[s]]
        if len(have) == len(SKILLS):
            status = "OK        "
        elif have:
            status = "PARITY GAP"
            gaps.append(rule_id)
        else:
            status = "MISSING   "
            missing.append(rule_id)

        print(f"  {status}  {rule_id:<{width}}  {desc}")

        if status == "PARITY GAP":
            absent = [s for s in SKILLS if not present[s]]
            for skill in absent:
                norm, _ = docs[skill]
                unmatched = [p for p in pats_for(patterns, skill)
                             if not re.search(p, norm)]
                print(f"              -> absent from {skill}: "
                      f"no match for {', '.join(repr(u) for u in unmatched)}")
        elif status == "MISSING":
            for skill in SKILLS:
                norm, _ = docs[skill]
                unmatched = [p for p in pats_for(patterns, skill)
                             if not re.search(p, norm)]
                print(f"              -> absent from {skill}: no match for "
                      f"{', '.join(repr(u) for u in unmatched)}")
            print(f"              -> absent from both. Either the rule was "
                  f"dropped, or these patterns are wrong.")
        elif verbose:
            for skill in SKILLS:
                _, lines = docs[skill]
                where = first_line_matching(pats_for(patterns, skill)[0], lines)
                print(f"              {skill}/SKILL.md:{where}")

    # -- forbidden phrases: must be absent -----------------------------------
    print()
    print("forbidden phrases (must be absent)")
    present_forbidden: list[str] = []
    for rule_id, desc, per_skill in FORBIDDEN:
        hits = []
        for skill in SKILLS:
            norm, _ = docs[skill]
            hits += [f"{skill}: {p!r}" for p in per_skill.get(skill, [])
                     if re.search(p, norm)]
        if hits:
            present_forbidden.append(rule_id)
            print(f"  PRESENT     {rule_id:<{width}}  {desc}")
            for h in hits:
                print(f"              -> {h}")
        else:
            print(f"  OK          {rule_id:<{width}}  {desc}")

    # -- shared runner files: byte-identity by content hash -----------------
    print()
    print("shared runner files: byte-identity (sha256)")
    drifted: list[str] = []
    for name in SHARED_BIN_FILES:
        digests = {}
        for skill in SKILLS:
            path = os.path.join(REPO, skill, "bin", name)
            try:
                with open(path, "rb") as fh:
                    digests[skill] = hashlib.sha256(fh.read()).hexdigest()
            except OSError as exc:
                digests[skill] = f"UNREADABLE ({exc})"
        if len(set(digests.values())) == 1 \
                and not str(next(iter(digests.values()))).startswith("UNREADABLE"):
            print(f"  OK          bin/{name}  {digests[SKILLS[0]][:12]}")
        else:
            drifted.append(name)
            print(f"  DRIFT       bin/{name}")
            for skill, digest in digests.items():
                print(f"              {skill}: {digest[:64]}")

    print()
    ok = len(RULES) - len(gaps) - len(missing)
    print(f"{ok}/{len(RULES)} rules in parity; "
          f"{len(SHARED_BIN_FILES) - len(drifted)}/{len(SHARED_BIN_FILES)} "
          f"shared files byte-identical")
    if gaps:
        print(f"PARITY GAPS ({len(gaps)}): {', '.join(gaps)}")
    if missing:
        print(f"MISSING FROM BOTH ({len(missing)}): {', '.join(missing)}")
    if present_forbidden:
        print(f"FORBIDDEN PRESENT ({len(present_forbidden)}): "
              f"{', '.join(present_forbidden)}")
    if drifted:
        print(f"SHARED-FILE DRIFT ({len(drifted)}): {', '.join(drifted)} — "
              f"re-copy the reviewed file byte-identically; never fix one "
              f"side alone")
    if gaps or missing or drifted or present_forbidden:
        print("\nSemantic parity means the same *rules* hold in both skills. "
              "Prose may differ; a rule may not — and a designated shared "
              "runner file may not differ by a single byte.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
