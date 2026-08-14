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

**All four findings below are folded within this one pass, including two
design-shaped-fold escalations (findings 3 and 4).** This is deliberate, and
pins the halt-granularity distinction in SKILL.md step 12: a design-escalation
pauses *the fold of that one finding* to get a live decision — it does not
freeze the rest of the pass's already-returned findings. Once finding 3's
card is answered, the editor continues folding findings 4 and (implicitly)
would continue to any further findings in this same lens response; no new
Codex call happens between them. Contrast with the step-14 loop-mode
guardrails (max-pass, non-convergence, etc.), which halt *between* passes —
a fundamentally different, coarser granularity.

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
  a request id for audit; **adding a uniqueness constraint on that existing
  column and letting the insert itself be the claim** needs no new persisted
  field. Note what makes this a legitimate alternative rather than a
  hand-wave: the merge proceeds only for the request whose insert *won*, so
  the exclusion is atomic. A read-then-act "check the log, skip if present"
  would **not** qualify — two concurrent retries can both read absent and
  both merge, which is the original defect wearing a check. On trust-boundary
  code an alternative must supply the same invariant as the mechanism it
  replaces, only more cheaply; an alternative that merely narrows the race is
  a different, weaker fold and must be recorded as one.
- **Alternatives:** adopt a dedicated idempotency-key mechanism (more
  robust, more surface). *(accept the risk would normally be a third
  alternative here, but it's excluded entirely — `editor/approve.ts` is
  named by `PF-shipbar` as a trust boundary, so this option is never
  displayed on this card at all, not even to be declined.)*
- **(Discuss, via the harness's free-form response.)**
- **Chosen: cheaper alternative.** → `incorporated (via alternative)` —
  constrained the existing audit-log request id to be unique and made the
  insert the merge's admission ticket; re-reviewed next pass (Codex hasn't
  seen this implementation yet).

**Finding 4 — "No deterministic way to detect the autosave race after the
fact" (MEDIUM). Genuinely ambiguous at first glance — resolved via the
signals checklist.** "Just add a column" sounds cheap, but the signals name
exactly this: **a new persisted field** (a version/sequence counter on the
draft record) that must be checked on every subsequent write — a cross-request
invariant. Classified as mechanism-requiring despite its small footprint;
escalates the same as finding 3.
- **Recommendation:** adopt the mechanism — no cheaper alternative exists
  here (the whole point is making the race detectable *and rejectable*,
  which requires new state either way).
- **Alternatives:** accept the risk (permitted this time — `editor/autosave.ts`
  isn't a `PF-shipbar` boundary).
- **(Discuss, via the harness's free-form response.)**
- **Chosen: adopt.** → fold proceeds this pass, and the adopted mechanism is
  scoped explicitly (so nothing downstream has to infer its reach): a
  monotonic version counter on the draft record, **plus** the write path
  checking it on every save and rejecting a write whose counter doesn't
  match what it last read — detection and rejection land together, one
  mechanism, one fold. Noted for next pass: this is itself a new mechanism,
  so it gets full scrutiny like any other schema change.

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

AR-1 surfaces as a decision card — all four of accepted-risk confirmation's
resuming transitions are legal here (nothing about this finding prohibits
any of them), so all four are listed explicitly; `discuss` is the harness's
free-form path, not a fifth listed option (recommendation + 3 alternatives =
4, exactly the cap):
- **Recommendation:** confirm, this review only — the rationale is sound and
  narrow (one specific behavior, bounded, recoverable), but doesn't yet
  warrant a standing repo-wide register entry.
- **Alternatives:** confirm + add to register (durable, reusable across
  future reviews); reject (if the human disagrees the bound holds); defer
  (if the human wants to think about it — leaves AR-1 `proposed`, no new
  state, re-presented at the next checkpoint).
- **(Discuss, via the harness's free-form response.)**

**Persistence, two-phase (SKILL.md step 12):** before this card is presented
to the human, it's appended to the pass log as `AR-1 confirmation (AR-1):
recommendation — confirm, this review only; alternatives — confirm+register,
reject, defer; chosen: (pending)`. If the session were interrupted right
here — before any answer — a resumed session reads that line, sees
`(pending)`, and re-presents the identical card; nothing about the choice
is fabricated or lost. Once the human actually answers, the same log entry
is updated in place, replacing `(pending)` with the real outcome:

**Branch A — chosen: reject.** → the log entry becomes `chosen: reject
(AR-1 -> reopened)`. AR-1 moves to **`reopened`**: blocks
Converge exactly as `proposed` did, and immediately re-enters the open
ledgers (HIGH guardrail no longer satisfied for this finding; non-convergence
count re-includes it).

## Pass 2 (Branch A continues) — reopened finding gets a fresh disposition

Now that finding 4's version counter (plus reject-on-mismatch) landed in pass
1, the autosave race is both detectable and rejected outright before it can
corrupt anything — a different, later fold happened to close the finding
this reopened item is about. The editor re-evaluates AR-1's underlying
finding with fresh evidence from the just-adopted mechanism. **This is
`incorporated`, not `disputed`** — the original finding was never wrong
(a real race did exist), so `disputed`'s "Codex misread intent or a
constraint not visible in the diff" doesn't apply; the defect really did get
fixed, just as a side effect of a different finding's fold rather than a
dedicated one:
→ `incorporated (superseded by finding 4's mechanism)` — "finding 4's
version counter plus reject-on-mismatch, adopted in the prior pass for a
different finding, already closes this one: a write whose counter doesn't
match is rejected outright rather than merely detected, which supersedes
'bounded ≤one draft, recoverable via discard.' No additional code change
needed for AR-1 specifically."

This resolves the `reopened` item with a terminal disposition (`incorporated`),
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

**AR-2 keeps its id — deliberately, and this is the case that distinguishes
the two "changed bound" rules.** The lifecycle's new-id rule fires on a
materially changed *finding* (different location, behavior, or claimed
bound); nothing about the Export finding changed here — only `PF-blast`'s
wording did. So this is posture-dependency invalidation, which always
preserves the id: same `AR-2`, back to `proposed`, history intact. Minting an
`AR-5` here would be wrong, and would discard the record that a human once
confirmed this item against the older posture text.

**Contrast — a third accepted-risk, AR-3, descriptor `["PF-audience"]`**,
confirmed the same pass as AR-2. `PF-audience` digest:
`65fb1786fc352fe9db6f2c9a92c21d26713f399cc272b23ffd6483661ffc4e46`. The
pass-3 amendment above touches only `PF-blast` — `PF-audience`'s text and
digest are untouched. **AR-3 stays `confirmed`.** This is the deliberate
two-sided pin: an edit *inside* a confirmation's named fields invalidates
(AR-2); an edit *outside* them never does (AR-3), even within the same
posture file, same pass, same review.

**A fourth accepted-risk, AR-4, pins the multi-field digest procedure
(SKILL.md step 12).** AR-1/AR-2/AR-3 above are all single-field descriptors,
so their digests are the direct single-entry recipe (bare content, no
framing — identical in kind to register-match's). AR-4's rationale relies on
**two** fields, descriptor `["PF-blast", "PF-audience"]` (authored in that
order — the procedure sorts lexicographically regardless, so this is
deliberately not pre-sorted by the author), which needs the multi-field
case: length-prefix each field so no separator is ever scanned for, and
none can collide with content. Per the procedure: extract each field's
canonical content, sort ids lexicographically (`PF-audience` before
`PF-blast`), UTF-8-encode id and content and emit
`len(id):id` + `len(content):content` per field (decimal byte lengths),
concatenate in sorted order, sha256 the bytes:

```
9:PF-audience84:PF-audience: Internal editorial staff only, ~30 daily actives, behind company SSO.
8:PF-blast157:PF-blast: A corrupted draft from a rapid-save race is recoverable via version history; cost is bounded to one draft, no data loss beyond that draft.
```
(shown on two lines for readability only — the actual input is one
concatenated byte string, no newline between the two fields' encodings)
→ `7523159378aadf67509d40f344cddee45cdb8607bc394fa82daa062a708767e2`

Confirmed this pass. **After the pass-3 `PF-blast` amendment** (same
amendment as AR-2's, above), recomputing with the same procedure — sort
order and encoding unchanged, only `PF-blast`'s content and therefore its
length prefix differ — gives:
`9634adf8f1b40e86e258b8d2972d494b86f9a03d678b90edc5c7e144bcff5bc6`. Different
from the confirmed digest, so **AR-4 invalidates too**, for the same reason
as AR-2 (one of its named fields changed) — a multi-field descriptor
invalidates if *any* named field changes, not only if all of them do.

**Reconstructability (interruption-crossing), demonstrated rather than
asserted.** Walk through what a session actually has available, not just the
claim that it would work: at the moment of the pass-1 checkpoint, the pass
log durably records AR-2 as `confirmed`, descriptor `["PF-blast"]`, digest
`0719a9a0576c51c3de74d8d67d3d48b1a81478b8effacf70f0822ec7d58eef73`; AR-3 as
`confirmed`, descriptor `["PF-audience"]`, digest
`65fb1786fc352fe9db6f2c9a92c21d26713f399cc272b23ffd6483661ffc4e46`; AR-4 as
`confirmed`, descriptor `["PF-blast", "PF-audience"]`, digest
`7523159378aadf67509d40f344cddee45cdb8607bc394fa82daa062a708767e2`. **The
session then ends** — no session memory of *why* these were confirmed, what
the reasoning was, or which fields mattered beyond what's written above.

**A new session opens at pass 3**, after the human has independently amended
`PF-blast` (unrelated to this review — a real incident elsewhere prompted
it). This session's only inputs are: the pass log (the three lines above,
verbatim) and the current posture source (`PF-blast`'s new text, `PF-audience`
unchanged). It re-derives, per field id, from the current posture source:
`PF-blast` → new text → new single-field digest
`8117d86ae3515efdeff707f6561ad92c58a958899f4287d5d719dc805a73005b`;
`PF-audience` → unchanged text → same digest as before. For AR-2 (descriptor
`["PF-blast"]`): recomputed digest ≠ stored digest → invalidate. For AR-3
(descriptor `["PF-audience"]`): recomputed digest == stored digest → stands.
For AR-4 (descriptor `["PF-blast","PF-audience"]`): rebuild the length-prefixed
encoding per the procedure using each field's *current* content → recomputed
`9634adf8f1b40e86e258b8d2972d494b86f9a03d678b90edc5c7e144bcff5bc6` ≠ stored
`7523159378aadf67509d40f344cddee45cdb8607bc394fa82daa062a708767e2` →
invalidate. **These are the same three outcomes the same-session pass-3
recomputation reached above** — because both computations are the identical
procedure over the identical two durable inputs (pass log, posture source);
nothing else fed either one.

## What a wrong result looks like

| Wrong implementation | What it produces | Why it's wrong |
|---|---|---|
| AR-1 (`proposed`, HIGH) treated the same as a `disputed` HIGH for the loop-mode guardrail | Loop halts on AR-1 alone, even with no design-escalation pending | Defeats Q1's whole point (continue-and-batch) — `accepted-risk` proposals are supposed to let the loop keep moving while still surfacing at checkpoint and blocking Converge. |
| Design-shaped-fold escalation (finding 3) batched instead of halting immediately | Editor folds *some* implementation of de-dup this pass without the human choosing which one | Committing to an unapproved mechanism is exactly what the immediate-halt rule (unlike accepted-risk's continue-and-batch) exists to prevent. |
| "Accept the risk" offered on finding 3's card | Card presents accept-the-risk as an option for `editor/approve.ts` | `PF-shipbar` names the approve/merge path as a trust boundary — this option must never be displayed there, matching the same exclusion as register-match's trust-boundary gate. |
| AR-2's invalidation check recomputes the digest but doesn't compare against the *current* `PF-blast` — e.g. compares against a cached pass-1 value | AR-2 silently stays `confirmed` after the pass-3 amendment | The whole posture-dependency mechanism exists so a confirmation can't outlive the bound it was confirmed against; comparing against a stale cached value defeats it identically to Phase 1's register-match digest bug. |
| Any edit to `docs/risk-posture.md` invalidates every confirmed `AR-<n>`, not just ones whose descriptor names the changed field | AR-3 also returns to `proposed` after the `PF-blast`-only edit | Over-invalidates: the whole reason the descriptor names specific field ids (rather than "the posture changed") is so an edit to one field doesn't retroactively unconfirm accepted risks that never depended on it — this would make posture editing itself costly in a way the design explicitly avoids. |
| Multi-field digest built by concatenating field contents in *authoring* order with a plain separator (e.g. `\n---\n`) instead of length-prefixing | Two problems at once: authoring `["PF-blast","PF-audience"]` vs `["PF-audience","PF-blast"]` hashes differently without the sort step; and if any field's content ever contains the separator sequence itself, the join is ambiguous — the same bytes could come from two different (id, content) splits | Two sessions reconstructing the same confirmation from the pass log alone must reach the same digest regardless of authoring order (the sort fixes this) and regardless of what's in the content (length-prefixing fixes this, a plain separator does not) — this is the gap Phase 2's first draft actually shipped, caught by both senior-dev and qa independently at pass 2. |

Real values above (single-field AR-2/AR-3 digests unchanged from Scenario 03's PF- examples; AR-4's are new) — none of this table is hand-waved.

## Lens run summary

- senior-dev: REVISE (3 HIGH, 1 MEDIUM; **four** accepted-risk proposals —
  AR-1 rejected/reopened/resolved via a superseding fold; AR-2 confirmed
  then invalidated (single-field descriptor); AR-3 confirmed and **still
  valid** (untouched by the posture edit that invalidated AR-2); AR-4
  confirmed then invalidated (multi-field descriptor); two
  mechanism-requiring escalations; one non-mechanism fold)
