# Scenario 04 — accepted-risk lifecycle, escalation boundary, accounting table

Pins `../../../SKILL.md` step 12's `accepted-risk` disposition (full `AR-<n>`
lifecycle, posture-dependency descriptor + digest), the design-shaped-fold
escalation rule (mechanism/non-mechanism boundary), the per-card outcome
mappings, and the accounting table's per-ledger, per-state behavior — all new
in the Risk Posture & Proportionality initiative's Phase 2. Read, not run, per
this directory's convention (`../README.md`): the dispositions below are the
editor's semantic judgment, not something mechanically derivable from the
lens response alone.

## Setup

**Posture** (governing plan named, or repo `docs/risk-posture.md`):

```
PF-audience: Internal editorial staff only, ~30 daily actives, behind company SSO.
PF-blast: A corrupted draft from a rapid-save race is recoverable via version
          history; cost is bounded to one draft, no data loss beyond that draft.
PF-shipbar: Blocks ship: unauthenticated or duplicated writes on the
            approve/merge path -- that path is a trust boundary, full rigor
            regardless of posture. Logged-as-accepted: autosave-path staleness
            and corruption windows bounded to one draft, recoverable.
```

**Lens response:** [`pass-1.senior-dev.response.json`](pass-1.senior-dev.response.json)
— 3 HIGH findings, 1 MEDIUM.

## Pass 1 — fold decisions

**Finding 1 — "Rapid double-save can corrupt an in-progress draft" (HIGH).**
Pushback criteria met: the defect (autosave-path corruption, one draft,
recoverable) falls exactly within `PF-blast`'s bound, and `PF-shipbar` doesn't
name the autosave path as a trust boundary — the anti-criteria doesn't
exclude it. Editor proposes `accepted-risk`.
→ `accepted-risk (AR-1)`. Rationale: "Bounded to one draft, recoverable via
version history per PF-blast; fixing requires either a lock (see finding 3's
mechanism boundary below) or accepting the bound." Posture-dependency
descriptor: `["PF-blast"]`. Digest (sha256 of the complete `PF-blast` field
text, normalized): `0719a9a0576c51c3de74d8d67d3d48b1a81478b8effacf70f0822ec7d58eef73`.

**Finding 2 — "Save handler dereferences an optional field without a null
check" (HIGH). Non-mechanism — folds normally, no escalation.** A guard
clause is explicitly listed as a non-mechanism signal (SKILL.md step 12);
nothing here creates a schema change, persisted field, cross-request
invariant, background process, or external dependency.
→ `incorporated` — added a null check before the `clientMeta.deviceId` read.

**Finding 3 — "Approve endpoint can double-merge on a network-retried
request" (HIGH). Mechanism-requiring — design-shaped-fold escalation.**
De-duplicating retried approvals needs either a new persisted idempotency
key (a new persisted field — a mechanism signal) or a new invariant that
must hold beyond the current request (has this approval already been
applied? — state outliving the call, also a mechanism signal). The fold
halts immediately (not batched — continuing would commit to an unapproved
mechanism) with a decision card:
- **Recommendation:** cheaper alternative — the approve handler already logs
  a request id for audit; check-and-skip against that existing log needs no
  new persisted field.
- **Alternatives:** adopt a dedicated idempotency-key mechanism (more
  robust, more surface); accept the risk (excluded — `editor/approve.ts` is
  named by `PF-shipbar` as a trust boundary, so this option is never
  displayed on this card).
- **Discuss.**
- **Chosen: cheaper alternative.** → `incorporated (via alternative)` —
  reused the existing audit-log request id for check-and-skip de-dup;
  re-reviewed next pass (Codex hasn't seen this implementation yet).

**Finding 4 — "No deterministic way to detect the autosave race after the
fact" (MEDIUM). Genuinely ambiguous at first glance — resolved via the
signals checklist.** "Just add a column" sounds cheap, but the signals name
exactly this: **a new persisted field** (a version/sequence counter on the
draft record) that must be checked on every subsequent write — a cross-request
invariant. Classified as mechanism-requiring despite its small footprint;
escalates the same as finding 3.
- **Recommendation:** adopt the mechanism — no cheaper alternative exists
  here (the whole point is making the race detectable, which requires new
  state).
- **Alternatives:** accept the risk (permitted this time — `editor/autosave.ts`
  isn't a `PF-shipbar` boundary); discuss.
- **Chosen: adopt.** → fold proceeds this pass: adds a monotonic version
  counter to the draft record. Noted for next pass: this is itself a new
  mechanism, so it gets full scrutiny like any other schema change.

### Accounting table applied, this pass

| Item | State | HIGH guardrail | Non-convergence count | Converge |
|---|---|---|---|---|
| AR-1 | `proposed` | satisfied — loop continues | excluded | **blocks** |
| Finding 2 | `incorporated` | n/a (resolved) | excluded | clear |
| Finding 3 | `incorporated (via alternative)` | n/a (resolved) | excluded | clear |
| Finding 4 | `incorporated` (adopted mechanism) | n/a (resolved) | excluded | clear |

Loop-mode guardrail check: AR-1 is a HIGH dispositioned `accepted-risk
(proposed)` — this does **not**, by itself, halt the loop (Q1: continue and
batch). The loop *did* halt this pass regardless, because findings 3 and 4
each triggered their own immediate design-shaped-fold escalation halt — a
different guardrail, firing on its own terms. Converge is recommended
against: AR-1 remains `proposed`.

## Pass 1 checkpoint — batched accepted-risk confirmation

AR-1 surfaces as a decision card:
- **Recommendation:** confirm, this review only — the rationale is sound and
  narrow (one specific behavior, bounded, recoverable), but doesn't yet
  warrant a standing repo-wide register entry.
- **Alternatives:** confirm + add to register (durable, reusable across
  future reviews); reject (if the human disagrees the bound holds).
- **Discuss.**

**Branch A — chosen: reject.** → AR-1 moves to **`reopened`**: blocks
Converge exactly as `proposed` did, and immediately re-enters the open
ledgers (HIGH guardrail no longer satisfied for this finding; non-convergence
count re-includes it).

## Pass 2 (Branch A continues) — reopened finding gets a fresh disposition

Now that finding 4's version counter landed in pass 1, the autosave race
itself is deterministically detectable and — per the human's pass-1-checkpoint
reasoning — no longer worth accepting as a residual risk; it should either be
closed outright or re-argued. The editor re-evaluates AR-1's underlying
finding with fresh evidence from the just-adopted mechanism:
→ `disputed` — "superseded by the version-counter mechanism (finding 4,
pass 1): the race is now detectable and the caller can reject a
version-mismatched write outright, which is a stronger property than
'bounded and recoverable.' Not the same defect as originally filed."

This resolves the `reopened` item with a terminal disposition (`disputed`),
per the lifecycle rule that a `reopened` finding needs `incorporated`,
`disputed`, or a **new** `AR-<n>` proposal — never a reuse of `AR-1`.

## Branch B — confirmed, then invalidated by a posture amendment (two-sided)

A second, independent accepted-risk from the same review: **AR-2**, "Export
cache can serve a stale snapshot for one cache TTL window" (HIGH), rationale
citing `PF-blast` (same field as AR-1 — a different finding can cite the same
field). Descriptor: `["PF-blast"]`, digest
`0719a9a0576c51c3de74d8d67d3d48b1a81478b8effacf70f0822ec7d58eef73` (identical
to AR-1's, since both were confirmed against the same `PF-blast` text at the
same time — the digest is a property of the *field content*, not the
proposal).

At the pass-1 checkpoint, chosen: **confirm, this review only** → AR-2 is
`confirmed`.

**Later, at pass 3, `PF-blast` is amended** (an unrelated posture edit,
nothing to do with either AR-1 or AR-2's sagas — the human tightens the
language after a real incident elsewhere):

```
PF-blast: A corrupted draft from a rapid-save race is NOT reliably
          recoverable -- version history only captures saves that
          completed, and the race can corrupt mid-write.
```

New digest: `8117d86ae3515efdeff707f6561ad92c58a958899f4287d5d719dc805a73005b`
— different from the confirmed digest. **AR-2's confirmation is invalidated**:
the descriptor's field (`PF-blast`) no longer resolves to the same content, so
AR-2 returns to `proposed` for fresh confirmation under the *new* posture
text — the human's original confirmation was against a bound that no longer
holds.

**Contrast — a third accepted-risk, AR-3, descriptor `["PF-audience"]`**,
confirmed the same pass as AR-2. `PF-audience` digest:
`65fb1786fc352fe9db6f2c9a92c21d26713f399cc272b23ffd6483661ffc4e46`. The
pass-3 amendment above touches only `PF-blast` — `PF-audience`'s text and
digest are untouched. **AR-3 stays `confirmed`.** This is the deliberate
two-sided pin: an edit *inside* a confirmation's named fields invalidates
(AR-2); an edit *outside* them never does (AR-3), even within the same
posture file, same pass, same review.

**Reconstructability (interruption-crossing).** Nothing above depends on
session memory: AR-2 and AR-3's descriptors and digests live in the pass log;
`PF-blast`'s and `PF-audience`'s current text live in the posture source. A
fresh session re-deriving both digests from just those two durable sources —
whether that's the *same* session one pass later, or a *new* session resuming
after an interruption — runs the identical recompute-and-compare and reaches
the identical verdict (AR-2 invalidated, AR-3 stands). There is no
resume-specific code path to verify separately; the reproducibility claim
*is* the claim that this recomputation has no hidden session-local input.

## What a wrong result looks like

| Wrong implementation | What it produces | Why it's wrong |
|---|---|---|
| AR-1 (`proposed`, HIGH) treated the same as a `disputed` HIGH for the loop-mode guardrail | Loop halts on AR-1 alone, even with no design-escalation pending | Defeats Q1's whole point (continue-and-batch) — `accepted-risk` proposals are supposed to let the loop keep moving while still surfacing at checkpoint and blocking Converge. |
| Design-shaped-fold escalation (finding 3) batched instead of halting immediately | Editor folds *some* implementation of de-dup this pass without the human choosing which one | Committing to an unapproved mechanism is exactly what the immediate-halt rule (unlike accepted-risk's continue-and-batch) exists to prevent. |
| "Accept the risk" offered on finding 3's card | Card presents accept-the-risk as an option for `editor/approve.ts` | `PF-shipbar` names the approve/merge path as a trust boundary — this option must never be displayed there, matching the same exclusion as register-match's trust-boundary gate. |
| AR-2's invalidation check recomputes the digest but doesn't compare against the *current* `PF-blast` — e.g. compares against a cached pass-1 value | AR-2 silently stays `confirmed` after the pass-3 amendment | The whole posture-dependency mechanism exists so a confirmation can't outlive the bound it was confirmed against; comparing against a stale cached value defeats it identically to Phase 1's register-match digest bug. |
| Any edit to `docs/risk-posture.md` invalidates every confirmed `AR-<n>`, not just ones whose descriptor names the changed field | AR-3 also returns to `proposed` after the `PF-blast`-only edit | Over-invalidates: the whole reason the descriptor names specific field ids (rather than "the posture changed") is so an edit to one field doesn't retroactively unconfirm accepted risks that never depended on it — this would make posture editing itself costly in a way the design explicitly avoids. |

## Lens run summary

- senior-dev: REVISE (3 HIGH, 1 MEDIUM; two accepted-risk proposals — one
  rejected/reopened/resolved, one confirmed/later-invalidated; two
  mechanism-requiring escalations; one non-mechanism fold)
