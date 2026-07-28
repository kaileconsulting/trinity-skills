#!/usr/bin/env python3
"""Assert the shared machinery is present in BOTH skills' per-pass loops.

`iterate-plan` steps 5-10 and `iterate-review` steps 9-16 are the same machine
described twice. The plan requires them kept in **semantic parity, not
byte-identity** -- the prose legitimately differs where each skill's folding,
pass-log and flag handling differ, but the *rules* must hold in both.

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

import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = ("iterate-plan", "iterate-review")

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

    # --- loop-mode guardrails (all five) ---------------------------------
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
     [r"needs human judgment"]),

    # --- standing invariants ---------------------------------------------
    ("never-decides-convergence", "the skill never decides convergence",
     [r"never decides convergence"]),
    ("codex-never-edits", "Codex never edits files",
     [r"codex never edits"]),
    ("opus-sole-writer", "Opus is the sole writer of folds",
     [r"sole writer"]),
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

    print()
    ok = len(RULES) - len(gaps) - len(missing)
    print(f"{ok}/{len(RULES)} rules in parity")
    if gaps:
        print(f"PARITY GAPS ({len(gaps)}): {', '.join(gaps)}")
    if missing:
        print(f"MISSING FROM BOTH ({len(missing)}): {', '.join(missing)}")
    if gaps or missing:
        print("\nSemantic parity means the same *rules* hold in both skills. "
              "Prose may differ; a rule may not.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
