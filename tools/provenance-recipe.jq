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
# Objects carrying `summary_schema` 1 or 2 are counted — a pre-v2.4 state
# file (no `summary_schema` field at all) is silently skipped rather than
# erroring, since "old state files remain readable" is the stated contract.
# Schema 2 (simplification gate Phase 0) is schema 1 plus per-row component
# fields (`observation`, `components`, `streaks`, `retired`, `cards`); a
# schema-1 row reads with those empty. Keep this reader schema-tolerant
# even if the skill prose is ever reverted: dropping it would silently
# remove every schema-2 run from the tallies (plan Rollback section).
#
# Simplification-card measures (plan §5), from `cards` rows:
#   cluster_hits          -- every card row, with its outcome and `next`: the
#                            card's label entry in `components` of the NEXT
#                            row with `observation: true` (null = quiet on
#                            that label; "unknown" = no later completed row,
#                            or a schema-1 row with no `observation` flag)
#   card_outcome_mix      -- counts by `chosen` (descriptive only)
#   card_false_positive   -- premature fold-once-more answers over resolved
#                            cards (pending/aborted excluded); the §5
#                            rollback rule reads this
#   card_run_pass_counts  -- pass_count of every run where a card fired
#
# The cluster threshold is passed as `--arg n <N>` (the literal in each
# SKILL.md; tools/cluster_tracker.py's CLUSTER_N). With it, each hit gets
# `recurrence: true` when it fired past N (a card returning after fold once
# more); without it, `recurrence` is null. The recipe never assumes N.
#
#   jq -s --arg n 3 -f tools/provenance-recipe.jq <skill>/state/*.json
#
# `scope_class` is `null` for every iterate-plan run (no diff to classify)
# and `"production"` / `"non-production"` for iterate-review runs (§3) —
# the non_production_rollback_hits query below is exactly §3's rollback
# condition: HIGH/MEDIUM findings landing after pass 2 in non-production
# reviews. If that number is ever nonzero across real runs, §3's reduced
# default reverts per its documented rollback condition.

($ARGS.named.n // null | if . == null then null else tonumber end) as $n
| [.[] | select(.summary_schema == 1 or .summary_schema == 2)] as $runs
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
| . as $base
| [ $runs[] as $run
    | $run.passes[] as $row
    | ($row.cards // [])[]
    | . as $card
    | ([ $run.passes[] | select(.pass > $row.pass and .observation != false) ]
       | first) as $next_row
    | $card + {
        run: ($run.pass_log_path // $run.plan_abs_path),
        pass: $row.pass,
        recurrence: (if $n == null then null else $card.streak_at_fire > $n end),
        next: (if $next_row == null or ($next_row | has("observation") | not)
               then "unknown"
               else ($next_row.components // {})[$card.component] end)
      }
  ] as $hits
| ([ $hits[] | select(.chosen != "pending" and .chosen != "aborted") ]) as $resolved
| $base + {
    cluster_threshold: $n,
    cluster_hits: $hits,
    card_outcome_mix: ($hits | group_by(.chosen)
                       | map({key: .[0].chosen, value: length}) | from_entries),
    card_false_positive: {
      resolved: ($resolved | length),
      premature: ([ $resolved[] | select(.reason == "premature") ] | length)
    },
    card_run_pass_counts: [ $runs[]
                            | select([.passes[] | (.cards // [])[]] | length > 0)
                            | .pass_count ]
  }
