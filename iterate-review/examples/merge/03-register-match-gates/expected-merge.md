# Scenario 03 — register-match gates (provenance, behavior, trust-boundary)

Pins `../../../SKILL.md` step 11's three-gate `register_ref` validation and the
complete-logical-bullet digest recipe. All three gates and the digest recipe
are new behavior — this scenario exists because Codex caught **two real bugs
in the first drafts of this exact machinery** during the Risk Posture &
Proportionality Phase 0+1 review (2026-08-13, passes 1 and 5): a digest that
silently ignored wrapped entry text, and a register-match with no check that
the entry predates the diff it's excusing. The wrong-result table below is
those two bugs, plus the trust-boundary exclusion from the same review's pass 3.

## Setup

**This pass's posture** (governing plan named, or repo `docs/risk-posture.md`
— either source, same fields):

```
PF-shipbar: Blocks ship: unauthenticated writes to the approve/merge path.
            That path is a trust boundary — full rigor applies regardless
            of posture. Logged-as-accepted: staleness/poisoning windows on
            the autosave path.
```

**Register entry, present unchanged at the diff's base revision** (this is
the precondition the provenance gate checks — see finding 2's gate):

```
- **RR-2026-08-06-seq-poison** — client-supplied seq can poison one
  draft for ≤24h; recoverable via discard; accepted 2026-08-06.
```

**Lens response:** [`pass-1.senior-dev.response.json`](pass-1.senior-dev.response.json)
— two HIGH findings, both tagged `register_ref: RR-2026-08-06-seq-poison`:
1. Autosave path (`editor/autosave.ts:88`) — the same seq-poisoning behavior the entry names.
2. Approve/merge path (`editor/approve.ts:41`) — same shape, but on the trust-boundary path `PF-shipbar` names.

## Expected gate evaluation

**Finding 1 (autosave) — all three gates pass:**
1. **Provenance** — the entry's exact text (see digest below) already exists at the diff's base revision, unchanged. Pass.
2. **Behavior** — the finding's behavior (unbounded seq poisons one draft, recoverable via discard) falls within the entry's recorded behavior/bound/recovery exactly. Pass.
3. **Trust-boundary** — `editor/autosave.ts` is not named by `PF-shipbar`. Pass (nothing to exclude against).

→ Disposition: `register-match (RR-2026-08-06-seq-poison, entry-digest a3d07653dbb18c4430bc518af9457e3f39db22826271c8cb63d85c892f8d014b)`. No code edit, no fresh human confirmation.

**Finding 2 (approve/merge) — fails the trust-boundary gate:**
1. **Provenance** — same entry, same pass. Pass.
2. **Behavior** — same seq-poisoning shape. Pass.
3. **Trust-boundary** — `editor/approve.ts` (approve/merge path) **is** named by `PF-shipbar` as a trust boundary requiring full rigor regardless of posture. **Fail.**

→ Disposition: **not** a register-match — treated as untagged and dispositioned normally (`incorporated`, since it's a real HIGH on a trust-boundary path with no exemption available). The two findings share a `register_ref` but do **not** share a disposition — this is a deliberate two-way pin: the trust-boundary gate must fire per-finding, not per-register-entry.

## The digest, computed

Recipe (SKILL.md step 11): starting at the line matching `- **RR-<id>** — `,
include every subsequent line up to the next `- **RR-` bullet or section end;
strip trailing whitespace per line; join with `\n`; sha256 hex of the UTF-8 bytes.

```
- **RR-2026-08-06-seq-poison** — client-supplied seq can poison one
  draft for ≤24h; recoverable via discard; accepted 2026-08-06.
```
→ `a3d07653dbb18c4430bc518af9457e3f39db22826271c8cb63d85c892f8d014b`

If the entry is later amended — only the wrapped second line changes, bound
tightened from "recoverable via discard" to permanent:

```
- **RR-2026-08-06-seq-poison** — client-supplied seq can poison one
  draft PERMANENTLY; not recoverable; accepted 2026-08-06.
```
→ `60ab0fb440fb0885d271abe0513cc97e0ff2bec78c42975f2854fc24f8488b57` (different — correctly invalidates
a prior `register-match` carried in `PRIOR PASSES`, reopening finding 1).

## What a wrong result looks like

| Wrong implementation | What it produces | Why it's wrong |
|---|---|---|
| Digest = sha256 of only the first physical line (`- **RR-...** — client-supplied seq can poison one`) | `96e93276d133ea9d43ccf5138b998371ff11064d838403730e39617e96ed1c0b` — **identical** whether the entry is amended or not, since only the wrapped second line changed | The amendment above (discard → permanent, no recovery) goes completely undetected. A stale `register-match` for finding 1 keeps counting as resolved after the accepted risk's actual bound changed — this is the bug Codex found in pass 1 of the real review. |
| Trust-boundary gate skipped, or checked once for the whole register entry instead of per-finding | Finding 2 also becomes `register-match (RR-2026-08-06-seq-poison, ...)` | Silently converts an unauthenticated-write defect on the approve/merge path — the trust boundary the posture explicitly exempts from `accepted-risk` — into a no-human-confirmation-needed match. This is the bug Codex found in pass 3. |
| Provenance gate skipped (no base-revision check) | A contributor adds `RR-2026-08-06-seq-poison` to `docs/risk-posture.md` in the *same diff* as `editor/autosave.ts:88`, and finding 1 still matches | The "entry's own owner/date stands as its confirmation" claim only holds if the entry predates the change it's excusing. Skipping this check lets a diff author self-approve their own defect via a same-branch register edit — the bug Codex found in pass 5, framed as a security concern (branch-controlled register entries treated as pre-authorized). |
| Trust-boundary gate checked only against the *current* pass's `PF-shipbar`, not also the base-revision version | The same diff that introduces `editor/approve.ts:41` also edits `PF-shipbar` to drop the approve/merge path from the named trust boundaries; finding 2 now passes gate 3 and matches | A same-diff edit to the *posture* is the same self-serving-edit shape as editing the register entry itself, aimed at the exclusion instead of the acceptance — narrowing `PF-shipbar` within the very diff it's meant to constrain shouldn't retroactively legalize that diff's own defect. This is the bug Codex found in pass 7. Checking both the current and base-revision `PF-shipbar` closes it: the base revision still names the boundary, so the gate still fails. |

## Lens run summary

- senior-dev: REVISE (2 HIGH findings, both `register_ref`-tagged; only finding 1 survives all three gates as a match)
