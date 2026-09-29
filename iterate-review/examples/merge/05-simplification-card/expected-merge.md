# Scenario 05 — simplification card: trigger, per-operation accounting, no incorporation by association

Pins `../../../SKILL.md` step 12's component streak and **simplification
card**: the candidate-streak trigger (the card fires *before* the fold, on
the third consecutive HIGH/MEDIUM pass), the two-phase pending → resolved
write, the per-operation accounting, context-sensitive omission of *accept
the risk* on trust-boundary code, and the rule that a finding the chosen
operation does not fully resolve is **never** marked `incorporated (by
simplification)` by association. Read, not run, per this directory's
convention (`../README.md`).

Built from a real review — ResearchLogix_v2's CSRF hardening code review
(2026-09-24), passes 1–3, the sign-in bootstrap race — condensed to the
one lens and one mechanism this scenario protects. It doubles as the
simplification-gate plan's Phase 1 dry read-through: run against this
SKILL.md, passes 1–3 produce a card at pass 3 recommending the removal the
human actually chose.

## Setup

**Posture** (the governing plan's `## Risk posture`):

```
PF-shipbar: Blocks ship: a CSRF bypass, or a session-installing request raced by
            our own client code on the three sign-in screens — that code is a
            trust boundary, full rigor regardless of posture. Logged-as-accepted:
            framework-level session behaviour outside our request code (a
            concurrent request in another tab reviving a rotated session),
            bounded by session rotation on the next request, tracked as its own card.
```

**Committed record — passes 1 and 2, as sealed in the pass log** (only the
findings on this scenario's label shown):

```
## Pass 1 — … [HISTORICAL]
3. **A slow mount-time token fetch can overwrite the rotated post-login token** — MEDIUM · lens: senior-dev: …
   → Editor: incorporated — shared in-flight promise + a write fence on sessionGeneration … [introduced_by_pass: null] [component: csrf-bootstrap-mount-fetch]

## Pass 2 — … [HISTORICAL]
1. **An in-flight CSRF bootstrap GET can still land after session installation and restore the pre-install session cookie** — HIGH · lens: senior-dev, security, qa: …
   → Editor: incorporated — ensureCsrfToken() awaits any pending inFlightCsrfFetch … [introduced_by_pass: 1] [component: csrf-bootstrap-mount-fetch]
```

Committed streak for `csrf-bootstrap-mount-fetch` after pass 2: **2**
(pass 1 MEDIUM, pass 2 HIGH — one observation each).

**Lens response, pass 3:** [`pass-3.security.response.json`](pass-3.security.response.json)
— one HIGH. (In the real run qa's first attempt FAILED on a usage limit and
its retry succeeded, co-reporting the same HIGH; a successful retry makes
the pass a completed one, so it counts. See the wrong-result table.)

## Pass 3 — transition order

1. **Merge** → one finding. The block opens with it, `→ Editor:` empty.
2. **Classify before any fold.** The finding targets the same mechanism —
   the mount-time CSRF bootstrap fetch and the guards added around it — so
   it is `csrf-bootstrap-mount-fetch`, not a new label, even though its
   title names `ensureCsrfToken()` and the cross-tab case (*same mechanism,
   same label*). Candidate streak = committed 2 + 1 = **3** = the cluster
   threshold.
3. **Pending write**, before presentation — the finding's `→ Editor:` slot
   stays empty:

```markdown
### Decision cards

- **simplification** (`csrf-bootstrap-mount-fetch`, pass 3, streak 3): streak findings — pass 1 #3 MEDIUM (senior-dev, introduced_by_pass: null); pass 2 #1 HIGH (senior-dev, security, qa, introduced_by_pass: 1); pass 3 #1 HIGH (security, introduced_by_pass: 2); 2 of this streak's 3 findings are fold-caused.
  recommendation — **simplify (remove)**: delete the mount-time `fetchCsrfToken()` from all three sign-in screens; `ensureCsrfToken()` becomes the only pre-login fetch and runs strictly before the session-installing POST; delete the shared in-flight promise and the generation write fence (no longer needed). Guarantee lost: the token is no longer pre-warmed on arrival, so a bootstrap failure shows at submit instead of on page load, and first submit costs one extra round trip. Covering layer: `ensureCsrfToken()` at submit, plus the existing 419 "Security check failed" contract. Per-finding: pass 1 #3 — resolves (no mount fetch exists to overwrite the rotated token); pass 2 #1 — resolves (in this tab, no bootstrap GET is ever in flight across the POST); pass 3 #1 — resolves the in-tab variant only; does **not** resolve the cross-tab / any-concurrent-request revival, which is framework session behaviour independent of the mount fetch.
  alternatives — **simplify (narrow)**: keep the mount fetch but abort it with an `AbortController` the moment submit starts. Guarantee lost: none. Covering layer: the abort. Per-finding: pass 1 #3 — resolves (an aborted fetch can't write the store); pass 2 #1 — does not (the server may already have sent `Set-Cookie`, which the browser applies regardless of the JS abort); pass 3 #1 — does not (neither variant). · **fold once more**: extend the in-flight check across tabs. · *(accept the risk omitted: the mechanism is sign-in client code, a `PF-shipbar` trust boundary)*
  discuss — always available (the harness's free-form response; never counted against the four options).
  chosen: (pending)
```

4. **Present.** No other label has findings this pass, so nothing else
   folds meanwhile; in loop mode the loop is halted at this card.
5. **Resolution write** — the human picks the recommendation:

```markdown
  chosen: simplify (remove) (Kyle, 2026-09-24) — mount fetch, in-flight promise and fence deleted; remove's per-finding accounting applies.
retired: csrf-bootstrap-mount-fetch (removed by simplification card, pass 3)
```

   Then this pass's finding is dispositioned **by remove's accounting** —
   and remove resolves only its in-tab variant:

```markdown
1. **A late or cross-tab bootstrap GET can restore a superseded session** — HIGH · lens: security: …
   → Editor: accepted-risk (AR-1) — the in-tab variant is resolved by the pass-3 simplification fold (mount fetch removed); the cross-tab revival it also asserts is not, so this finding is not `incorporated (by simplification)`. Remainder proposed as accepted risk: framework-level session behaviour outside our request code, logged-as-accepted by PF-shipbar, bounded by session rotation, filed as its own card. Descriptor ["PF-shipbar"], digest a7a79cb9b1dea7812d42db5c2d7febd4b4e0448ba60c65f5d5043278e2f9eb73 (sha256 of the PF-shipbar field text as shown in Setup). [introduced_by_pass: 2] [component: csrf-bootstrap-mount-fetch]
```

   The remainder's AR is available even though the card omitted *accept
   the risk*: the card's option concerned the mechanism (sign-in client
   code, a trust boundary); the remainder concerns framework behaviour the
   posture explicitly logs as accepted. `AR-1` then follows its own
   lifecycle — confirmation at the checkpoint, Converge-blocking until then.

6. **Seal.** Pass 4 reads the label as retired; nothing on it can count
   again, and a replacement mechanism would need a new label.

**State-summary row for pass 3** (derived at exit):

```json
{"pass": 3, "verdict": "REVISE", "high_medium_count": 1, "findings_total": 1, "fold_caused_count": 1,
 "dispositions": {"incorporated": 0, "skipped": 0, "disputed": 0, "accepted-risk": 1, "register-match": 0},
 "observation": true,
 "components": {"csrf-bootstrap-mount-fetch": {"worst_severity": "HIGH", "findings": 1, "fold_caused": 1}},
 "streaks": {}, "retired": ["csrf-bootstrap-mount-fetch"],
 "cards": [{"type": "simplification", "component": "csrf-bootstrap-mount-fetch", "streak_at_fire": 3,
            "findings_in_streak": 3, "fold_caused_in_streak": 2, "chosen": "remove", "reason": null}]}
```

## Checkpoint

`AR-1` is `proposed` → batched accepted-risk confirmation card; Converge
blocked until it is confirmed. Recommendation: **Continue** — pass 4
reviews the simplified head with every selected lens.

## What a wrong result looks like

| Wrong output | The misreading that produces it |
|---|---|
| No card at pass 3; the finding is folded as a third patch | Streak counted *after* the fold, or from the state file instead of the pass log — the candidate streak (committed + this pass) is computed before any fold |
| Card first appears at pass 4 | Pass 3 treated as a FAILED-lens pass because qa's *first* attempt failed; a successful retry makes the pass complete, so it counts |
| The pass-3 finding's `→ Editor:` slot is filled with `simplification pending` while the card is open | The tag belongs in the card entry; an empty slot is what marks unfinished work on resume |
| Pass 3 #1 dispositioned `incorporated (by simplification)` | Incorporation by association — remove's accounting says it resolves the in-tab variant only |
| The narrow option's per-finding lines copied from remove's | Accounting is per operation: narrowing resolves a different (smaller) subset |
| *accept the risk* listed on the card | Context-sensitive omission missed: the mechanism is `PF-shipbar` trust-boundary code |
| *fold once more* is the recommendation, or remove is missing | Both are mandatory; fold once more is never recommended |
| `csrf-bootstrap-mount-fetch` still in `streaks` after pass 3 | Remove retires the label; it is never reused |
