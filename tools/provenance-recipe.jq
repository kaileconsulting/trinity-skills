# Provenance analytics recipe — shared across iterate-plan and iterate-review.
#
# Reproduces the retro's core tallies (pass counts, fold-caused share,
# disposition mix) plus iterate-review's §3 rollback-cohort query, from the
# `passes` row schema both skills' state files carry at Converge/Abort
# (Trinity v2.4 Phase 0 §5). One recipe, referenced by both skills'
# SKILL.md, so the two never drift on field names.
#
# Usage (slurp mode — pass every state file you want tallied as an argument;
# globs from one skill's state/ dir, or both skills' together, both work
# because the row schema is shared):
#
#   jq -s -f tools/provenance-recipe.jq <skill>/state/*.json
#   jq -s -f tools/provenance-recipe.jq iterate-plan/state/*.json iterate-review/state/*.json
#
# Only objects carrying `summary_schema == 1` are counted — a pre-v2.4 state
# file (no `summary_schema` field at all) is silently skipped rather than
# erroring, since "old state files remain readable" is the stated contract.
#
# `scope_class` is `null` for every iterate-plan run (no diff to classify)
# and `"production"` / `"non-production"` for iterate-review runs (§3) —
# the non_production_rollback_hits query below is exactly §3's rollback
# condition: HIGH/MEDIUM findings landing after pass 2 in non-production
# reviews. If that number is ever nonzero across real runs, §3's reduced
# default reverts per its documented rollback condition.

[.[] | select(.summary_schema == 1)] as $runs
| ($runs | map(.passes[])) as $rows
| ($rows | map(.findings_total) | add // 0) as $findings_total
| ($rows | map(.fold_caused_count) | add // 0) as $fold_caused_total
| {
    runs: ($runs | length),
    pass_count: ($rows | length),
    findings_total: $findings_total,
    fold_caused_total: $fold_caused_total,
    fold_caused_share: (if $findings_total > 0
                         then $fold_caused_total / $findings_total
                         else null end),
    disposition_mix: (
      reduce $rows[] as $row (
        {"incorporated": 0, "skipped": 0, "disputed": 0,
         "accepted-risk": 0, "register-match": 0};
        reduce ($row.dispositions | to_entries[]) as $e (.; .[$e.key] += $e.value)
      )
    ),
    non_production_rollback_hits: (
      [ $runs[]
        | select(.scope_class == "non-production")
        | .passes[]
        | select(.pass > 2)
        | .high_medium_count
      ] | add // 0
    )
  }
