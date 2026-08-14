# Changelog

## 2.3.0 — 2026-08-14 — risk posture & proportionality

Plan: `docs/archive/risk-posture-proportionality-2026-08-12.md` (converged after 9
iterate-plan passes). **Kyle initiated this one**, after a week of heavy use
raised a specific complaint: review cost was running 2–3× build cost and
phases were taking 5–10 passes, because the loop had no way to know that a
finding — while real — was disproportionate to what the thing being built
actually needed. Every prior release made the reviewer *find more*; this one
gives the editor a principled, recorded way to **not fix something**, and
gives the reviewer the project's own risk posture so it stops re-litigating
decisions already made.

Four phases: posture capture at plan time (0), posture flowing to the lenses
plus a single-home accepted-risks register (1), the `accepted-risk` lifecycle
and the decision-card contract (2), and a read-only retrospective validating
the premise against a week of real doc-bot review logs (3).

### Changed — **breaking** (reviewer output schema)

- Findings carry a new `register_ref` field: `["string", "null"]`, matching
  `^RR-\d{4}-\d{2}-\d{2}-[a-z0-9-]+$`, set only when a finding's behavior
  falls inside a specific register entry's recorded bound. **It is in
  `required` and nullable, not optional** — a constraint neither of us knew
  going in and worth writing down: under `additionalProperties: false`,
  `codex exec --output-schema` requires *every* property to appear in
  `required`, so an "optional" field must be nullable-and-required or the
  call fails outright. Found by invoking the real API, not by schema
  validation — `tools/check-all.sh` was 58/58 green while this was broken,
  because it never invokes Codex.
- Migration: reviewers must emit `register_ref` on every finding; `null` is
  the correct and common value. The editor validates every non-null ref and
  treats unknown, malformed, or non-matching refs as untagged.

### Added (Phase 2 — `accepted-risk` lifecycle + editor pushback)

- **New disposition `accepted-risk`** — "real finding, disproportionate to
  this product's posture; not fixing" — with a full lifecycle: `proposed`
  (editor, at fold time) → `confirmed`/`rejected` (human only, at a
  checkpoint), `rejected` → `reopened` (blocks Converge exactly as `proposed`
  does, and re-enters the open ledgers immediately). Ids are `AR-<n>`,
  allocated by the pass log, matched by id and never by prose.
- **Posture-dependency descriptor** — every confirmation persists the posture
  *field ids* its rationale relies on plus a sha256 digest of exactly those
  fields' content. A later pass re-selects by id and recomputes: a mismatch
  invalidates the confirmation and returns the item to `proposed` under the
  same id. Edits *outside* the named fields never invalidate. Multi-field
  descriptors use length-prefixed (netstring) framing so no byte of field
  content can ever be misread as a delimiter.
- **Design-shaped-fold escalation** — before folding any finding, the editor
  checks whether incorporating it requires a *new mechanism* (schema change or
  migration, new persisted or protocol field, invariant outliving the request,
  background process, external dependency). If so it pauses at that finding
  and asks. The halt is mid-fold and finding-scoped — deliberately a finer
  granularity than step 14's between-pass guardrails.
- **One decision-card contract across all five human-judgment moments**
  (design-shaped fold, accepted-risk confirmation, `needs_human` question,
  non-convergence stall, malformed posture source): recommendation + up to 3
  alternatives + an always-available `discuss`. Cardinality is bound by the
  harness's real 4-option cap, with `discuss` realized as free-form response
  so it never competes for a slot. **A card is never skipped and never
  auto-proceeded past**, including the degenerate zero-alternative case.
- **Accounting stated once, as a table** — three consumers (per-pass HIGH
  guardrail, non-convergence counter, Converge predicate) × every lifecycle
  state, so accepting a risk can't read as a stall while remaining impossible
  to converge past unconfirmed.
- **Pushback criteria and anti-criteria.** The editor is expected to spend
  `disputed` and `accepted-risk` when warranted. Never on code named as a
  trust boundary by `PF-shipbar`, and never to avoid a small honest fix.
- Fixture `examples/merge/04-accepted-risk-lifecycle/` with real computed
  sha256 digests, two-sided invalidation, single- and multi-field descriptors,
  a demonstrated session boundary, and mechanism/non-mechanism boundary cases
  including a deliberately ambiguous one.

### Hardened (Phase 2's 14-pass review — APPROVE×3 at pass 14, 0 disputed)

HIGH+MEDIUM trajectory 5,3,3,3,3,3,3,3,2,2,3,1,1,0. The flat-at-3 stretch ran
seven passes and tripped the stall guardrail twice; continuing was right both
times, since the two most valuable findings arrived after it. Most of what
follows is a **resume and persistence contract that did not exist in the
Phase 2 design** — it was discovered entirely by the review.

- **Pass-log blocks became a state machine.** A block opens unconditionally
  right after the merge, before any folding, and carries a three-valued tag:
  `[IN PROGRESS]` (resumable), `[HISTORICAL]` (complete *through* the
  checkpoint, not merely through folding), `[ABORTED]` (a pass deliberately
  ended while open — terminal, never resumed). `--once` seals explicitly since
  it has no checkpoint. Aborting the *review* after a complete pass leaves
  that pass `[HISTORICAL]`; the review-level outcome is `final_action`.
- **The merged findings list is written before folding begins**, with empty
  outcome slots that folding fills in. Resume is a lookup, never a
  re-derivation — re-running the semantic merge after an interruption can
  legitimately land differently and double-fold or skip. Corrections and
  questions have their own `(pending)` form, so one rule covers all three
  sections.
- **Reconcile before re-applying.** An empty outcome slot means "not
  recorded," which is not "not applied": read the file first, complete the
  slot if the change is already there, and escalate rather than guess when
  presence can't be determined — both guesses are destructive in one
  direction.
- **A trust boundary between reviewer text and control state.** Making
  `→ Editor:` lines the durable progress ledger put model-authored titles and
  descriptions into control-bearing structure; a crafted source comment could
  induce a lens to emit a forged `→ Editor: incorporated` line and make a
  resuming session drop an unfolded HIGH. Closed two ways: reviewer strings
  are sanitized to single logical lines with markers escaped, *and*
  dispositions are recognized only at editor-written structural positions,
  never by scanning for marker text.
- **A resolved card authorizes the option chosen, never the options
  declined.** Found twice, in different guises: once as a zero-alternative
  escape valve that could silently adopt an unapproved mechanism (pass 4), and
  once as a failed alternative falling through to the mechanism the human had
  declined (pass 9). The fixture now demonstrates the second case ending
  correctly — the cheaper alternative is folded provisionally, loses on
  re-review, and escalates again with its own card.
- Decision-card cardinality reconciled with the harness's real cap; the
  multi-field digest given collision-safe framing; terminal dispositions
  required to name what actually happened (`incorporated (superseded by …)`,
  never `disputed` for convenience).

### Added (Phase 1 — posture flows to the lenses)

- Posture reaches reviewers as an intent block, and findings can point back at
  it via `register_ref` (schema change above).
- **Single-home accepted-risks register**, `docs/risk-posture.md`, with
  allocation-free `RR-<date>-<slug>` ids. Publication happens **only** through
  an explicit human confirm — the editor never writes an entry on its own.
- **Register-match validation, three gates in order**: id resolves, behavior
  fits the recorded bound, and the entry is not a trust boundary — then a
  sha256 digest of the entry's *complete logical bullet*, every wrapped
  continuation line included. A matched finding needs no code edit and no
  fresh confirmation; the entry's own owner and date stand as its
  confirmation.
- **Provenance gate against same-diff self-authorization.** Register entries
  and `PF-shipbar` are checked at both the current pass and the base revision,
  so a change cannot edit the posture that would excuse it — or quietly narrow
  a trust boundary — inside the same diff.

### Added (Phase 0 — risk posture capture)

- `create-plan` captures posture at plan time via `PF-` fields (both plan
  types): what ships, what the blast radius is, what the ship bar is, and
  which code is a trust boundary. This is the input everything above consumes.

### Hardened (Phase 0+1's 8-pass review — APPROVE×3 at pass 8, 0 disputed)

Reviewed as one batch rather than per-phase (Kyle's call), which paid off
directly: it surfaced a cross-phase integration bug neither phase showed
alone — Phase 0's register-seeding path produced a `docs/risk-posture.md`
that Phase 1's own malformed-source detection would immediately reject.

- The `additionalProperties`/`required` schema constraint described above.
- A register-match digest that hashed only an entry's first physical line,
  silently missing amendments to wrapped text — the template's own canonical
  example wraps, so this would have bitten on the first realistic entry.
- Two distinct same-diff self-authorization attacks (security lens): editing
  the register entry itself, and separately narrowing `PF-shipbar` to remove a
  trust boundary. Both closed by the base-revision provenance check.
- SHA-1 → **SHA-256** for the register digest: it is an adversarial integrity
  boundary, unlike the state-file scope hash elsewhere, which has no
  adversarial model and stays sha1.

### Known gaps

Acceptance criteria at ship: **2 of 6 met, 3 built-and-fixture-pinned but never
exercised live, 1 deliberately not met** — annotated individually in the
archived plan. Stated plainly here because this release's whole subject is not
overstating what a review has established:

- **No live review has run against a real posture file.** Both reviews that
  validated this work were of *this* repo, which has no `docs/risk-posture.md`.
  The no-posture path is evidenced 22 times over (every pass block records
  `Posture: absent`); the with-posture path is pinned by fixture only.
- **`accepted-risk` has never fired on a live finding.** Across 22 passes, no
  finding was disproportionate enough to decline. The lifecycle is pinned
  state-by-state by `04-accepted-risk-lifecycle`, but the mechanism this
  release exists for has not yet been used in anger.
- **One of five decision-card moments has been exercised live** (design-shaped
  fold, at Phase 2 review pass 8 — the escalation, the pending persistence, and
  the resume signal all behaved as specified). The other four are specified and
  fixture-pinned only.
- **The pass-count claim is unmeasured.** Phase 3 became a read-only
  retrospective, so whether posture-awareness actually reduces review passes
  remains an open question, answerable only by a future real phase reviewed
  against an applied posture file.

Treat the fixtures as evidence the design is coherent, not as evidence it works
in the field.

### Validated (Phase 3 — retrospective, read-only)

Scope changed mid-plan from live validation to mining existing evidence: the
doc-bot write-path week (62 commits; Phase 0 alone took 10 review passes; 57
folds vs 7 disputes) was read without touching that repo.

- **Convergent invention.** At write-path Phase 3 pass 10 — a day before this
  release's Phase 2 shipped the mechanism — Kyle hand-wrote a proportionality
  doctrine in prose: dispute when a scenario needs scale the deployment won't
  reach and the failure is inconvenience rather than dishonesty; fold anything
  where the app would lie or that's in the merge path. That is essentially
  `accepted-risk`'s pushback criteria and `PF-shipbar`'s exemption, arrived at
  independently.
- **The register's case, concretely.** The "no app-level auth" dispute (an
  accepted posture: Tailscale perimeter, bounded blast radius) recurred
  **three times** across write-path Phases 0, 1, and 3, re-argued from scratch
  each time because no cross-phase memory existed.
- Classified as a **premise check**, not success/inconclusive/regression — no
  live posture-aware review has run yet. It validates strongly on premise; the
  pass-count question stays open until a real future phase is reviewed against
  an applied posture file.

## 2.2.0 — 2026-08-11 — runner scripts + artifact hygiene

Plan: `docs/archive/runner-scripts-artifact-hygiene-2026-08-06.md` (converged
after 9 iterate-plan passes; all acceptance criteria met, each annotated with
its evidence). Replaces per-pass improvised shell with stdlib-only Python
runners under each skill's `bin/` so one documented allowlist rule per skill
covers an entire review; moves the iterate-review pass-log default to
`docs/reviews/`; adds state pruning. Phase 3 completed the pattern's port to
`iterate-plan`. Real-world validation: the iterate-review dogfood (doc-bot
write-path Phase 1, 5 passes) and the iterate-plan dogfood (Axis 1 plan
review, 6 passes / 12 codex calls) each ran end to end with **zero Bash
permission prompts**; platform matrix verified on macOS (both install
layouts, rule matching demonstrated) and a `python:3.9-slim` Linux container
(full check suite green on the actual 3.9 floor interpreter).

### Changed (model-agnostic editor role)

- The editor role is no longer named after a model: "Opus" → **"the editor"**
  (Claude, whichever model drives the session) across both SKILL.mds, both
  reviewer prompts, lens READMEs, README, and the create-plan template; the
  loop is now described as **Claude⇄Codex**. HISTORICAL fold tags are
  `→ Editor:` going forward. Historical records (existing pass logs, archived
  plans, frozen `v1/`) deliberately keep their original wording.

### Added (Phase 3 — iterate-plan port + parity fixtures)

- `iterate-plan/bin/` with the same runner shape: `run-pass` (always-all lens
  selection + concurrent fan-out + `pass-N.summary.json` contract), `run-lens`
  (standalone/debug, isolated `debug/` namespace), `prune-state`, all under
  the same lock/atomic-publication lifecycle. The plan file is the scope:
  `--plan` must resolve inside the invoking repo root and be `.md`; an
  optional `--note` (the human-edits-since-last-pass block) is read only from
  the enforced per-repo handoff dir `<git-dir>/iterate-plan/`. Codex runs
  with `-C <plan-dir>` per the skill's original invocation shape.
- Adapted composition in `bin/plan_runner.py`, byte-deterministic and
  golden-pinned (`examples/composition/`): reviewer prompt + lens body +
  `=== MATCHED CONTEXT ===` (framing line + the H2 sections named in the
  lens's `requires_sections`; an absent section contributes its NOTE line —
  never skipped, never silent) + optional staged note + `=== PLAN ===`.
  Prior passes need no separate block — the plan's HISTORICAL sections
  arrive with the plan.
- **Shared-vs-adapted boundary made mechanical**: `runner_shared.py` and
  `prune-state` are designated shared files, duplicated byte-identically and
  content-hash-checked by `tools/check-parity.py` (a single divergent byte
  fails). To make the same bytes valid in both homes, the shared module
  derives its skill identity from its own location (`SKILL_NAME` from
  `bin/..`) — handoff dir, error text, and prune targets all follow the
  hosting skill; `invoke_codex` gained an optional `cwd` (`-C`) that
  iterate-review simply doesn't pass.
- `tools/check-plan-runners.py`: 50 behavioral fixtures for the adapted half
  (extraction semantics, selection + loud rule-data-drift failures,
  boundaries, exit contracts, patch-marker rejection at both command
  boundaries, debug isolation, concurrency fail-fast, prune wiring smoke) —
  wired into `tools/check-all.sh`. Deep shared-machinery behavior is
  deliberately not re-pinned: byte-identity plus iterate-review's 120
  fixtures already pin it once.
- `iterate-plan/SKILL.md` steps 5–7 rewired to the runners (selection +
  composition moved into `run-pass`, summary-driven response handling,
  one-retry via standalone `run-lens`); Converge now prunes the scope's
  state dir (`--keep-state` opts out, new invocation flag); the runner
  contract sentence added and enforced as a new `check-parity.py` prose rule
  (37 rules total). README documents the second allowlist line (tilde form).

### Hardened (Phase 3's 3-pass review — loop mode, APPROVE×3 at pass 3, 0 disputed)

Six findings, all incorporated (fold commits `5abb4b1`, `9baf676`); trail in
`docs/reviews/code-review-commit-6286fdd.md`:

- **Reads are identity-anchored, not just validated**: new shared
  `read_trusted_text` closes the validate-then-read symlink-swap window —
  content always comes from an opened descriptor whose inode is re-verified
  in-boundary AFTER the open; FIFOs/devices refuse without hanging; all four
  CLIs and the pass-log read route through it. The read-side twin of Phase
  2's fd-anchored deletion, pinned by a deterministic swap-injection fixture.
- **Duplicate H2 headings can't merge into one oversized slice** — any next
  H2 terminates extraction, a repeated identical title included. (The bug
  was a faithful port of the original awk helper's behavior; it became
  visible — and fixable — only once composition moved into code.)
- **Standalone CLI contracts aligned across both skills**: run-lens refuses
  empty inputs like run-pass, and orchestration failures (codex missing,
  publication errors) exit 1 with a diagnostic instead of a traceback.
- **The `-C <plan-dir>` invocation contract is asserted, not assumed** — the
  fake codex records argv; fixtures pin the flag's presence, value, and
  position at both command boundaries.

### Added (Phase 2 — prune-state + auto-prune on convergence)

- `bin/prune-state` implemented: `--scope` targeted cleanup (invoked by the
  model at the Converge checkpoint — the pruner never infers convergence),
  `--older-than` age-based cleanup for abandoned runs, `--force-unlock` as
  the explicit recovery path for ambiguous locks, and a read-only overview
  with no arguments. Every mode is a dry run unless `--yes`. Deletion holds
  the scope's own `run.lock` (role=prune) for the entire operation; a
  `run-pass` starting mid-cleanup fails fast on it. Never touched: pass
  logs, `state/<hash>.json` records, anything outside `state/`, live-locked
  scopes, and (by any automatic path) reclaim-marker-bearing scopes.
  Force-unlock removals are flock+inode-fenced and conditional on
  byte-identity with the inspected content — removal under that fence *is*
  the token revocation, so a displaced live run aborts without committing a
  summary and a successor's fresh lock is never touched.
- `iterate-review/SKILL.md` step 16 wired: Converge prunes the scope
  (`--keep-state` opts out, new invocation flag); Abort leaves state for the
  age-based sweep.
- Phase 2 fixture set in `tools/check-runners.py`: converged-scope removal,
  dry-run exactness, pass-log + model-state-file safety, scope-name/symlink
  refusals, live-lock refusal and age-sweep skip (marker-bearing scopes
  included), run-start vs. prune fail-fast, dead-pid reclaim through a
  targeted prune, concurrent force-unlock self-serialization, and
  force-unlock of a genuinely live run (displaced run detects revocation,
  successor's summary is the only one).

### Hardened (Phase 2's 6-pass review — run entirely on the new runners, loop mode's first real outing)

Behavior-visible outcomes, all fixture-pinned (suite grew from 90 to 120);
full trail in `docs/reviews/code-review-commit-13c9e0c.md`:

- **Deletion never re-traverses a validated pathname**: contents, locks, and
  force-unlock all operate through `O_NOFOLLOW` directory descriptors
  (`ScopeLock` gained a `dir_fd` mode); a symlink swapped in anywhere is
  unlinked as a link or refused, never followed.
- **Dry runs disclose exactly what `--yes` removes** — files, empty dirs,
  and directory symlinks — and targeted prune refuses if undisclosed
  entries appear before the lock is taken; the age sweep re-checks
  freshness *under* the lock (blind to its own mtime bumps).
- **Recovery tooling survives hostile state**: non-regular files (FIFO,
  directory) at lock names classify as malformed without hanging or
  crashing; malformed pids are never coerced on destructive paths (shared
  `_lock_pid`); concurrent sweeps treat disappearance as benign (APFS
  quirks included: EINVAL from unlinked-dir openat, `st_nlink=2` after
  rmdir).
- **Diagnostics are unforgeable**: every untrusted byte reaching the
  terminal — lock contents, parsed fields, scope/entry names, refusal
  text — is control-character-escaped into single-line records.
- **Honest outcomes**: genuine removal failures exit 1 naming the entry
  (never misreported as a benign handoff); mid-deletion displacement
  reports PARTIAL, never "skipped".
- One reviewer HIGH was **disputed and human-arbitrated** (final-rmdir
  TOCTOU: the window exists, but POSIX `ENOTEMPTY` means only an *empty*
  replacement could ever be removed — no state can be lost; verified live,
  argument recorded in code). Loop mode drove all 6 passes and halted on
  the max-pass + disputed-HIGH guardrails, as designed.

### Added (Phase 1 — iterate-review runners + SKILL.md rewire)

- `bin/run-pass` and `bin/run-lens` implemented: deterministic lens-input
  composition (byte-identical, golden-pinned in `examples/composition/`),
  concurrent per-lens Codex fan-out with the exact read-only sandbox flags,
  patch-marker rejection + structural validation **in code**, and the
  `pass-N.summary.json` result contract (exit 0 ⇔ summary published; a pass
  exists iff its summary exists).
- Lens selection **promoted to runtime**: the engine moved to
  `bin/selection_engine.py`; `run-pass` calls it and
  `examples/selection/check-selection.py` is now a thin goldens CLI over the
  same module — exactly one implementation, all 14 routing fixtures repointed.
- Run lifecycle: exclusive per-scope `run.lock` with ownership tokens,
  race-safe stale reclaim (`run.lock.reclaim` + byte-identity), atomic
  tmp+`os.replace` publication, conditional release, and an isolated `debug/`
  namespace for standalone `run-lens`.
- `tools/check-runners.py` — the runner fixture suite: composition goldens,
  both exit-contract boundaries, pass-log resolution (docs/reviews default
  from a subdirectory, override, non-git warning, existing logs untouched),
  the adversarial lifecycle cases, and the trusted-boundary refusals; wired
  into `check-all.sh`, teeth-tested in `test-checkers.py`. (Counts live in
  the suite output, deliberately not restated here — they grew with every
  self-hosted review pass.)
- `iterate-review/SKILL.md` steps 9–11 rewired to one `run-pass` invocation
  per pass; pass-log default moved to `docs/reviews/`; HISTORICAL appends via
  the Edit/Write tools; runner contract added to Hard rules. `--once`,
  `--loop`, `--max-passes`, `--log-path`, the state-file format, and the
  pass-log HISTORICAL format are unchanged. Parity: 36/36.

### Hardened (Phase 1's 11-pass self-hosted review — the runners reviewed their own branch)

Behavior-visible outcomes a user will encounter, all fixture-pinned; full
trail in `docs/reviews/code-review-branch-docs-runner-scripts-brief.md`:

- **Inputs must live in the per-repo handoff dir** `<git-dir>/iterate-review/`
  (non-git fallback `<cwd>/.iterate-review/`): the standing allowlist rule
  can't be used to read arbitrary host files — or even unrelated in-repo
  files (an untracked `.env`, `.git/config`) — into a codex prompt.
- **The pass-log header is the read capability**: an existing `--log-path`
  file is read as prior-pass context only when its first line is exactly
  `# Code Review — <scope-tag>` for this invocation.
- **Published pass state is immutable**: an explicit `--pass-num` colliding
  with any existing `pass-N.*` artifact is refused; codex responses stage at
  run-unique paths and publish atomically under a verified ownership token;
  lock mutations are flock+inode-fenced so force-unlock can't race a
  successor.
- **exit 0 ⇔ summary published** holds through pruned scopes, post-commit
  I/O errors, and broken stdout pipes, at both command boundaries.
- One reviewer HIGH was **disputed and human-arbitrated** (PEP 604
  annotations on the 3.9 floor — disproven on the floor interpreter, with a
  Gemini cross-vendor second opinion concurring); the review also included
  loop mode's first live guardrail halts.

### Added (Phase 0 — foundations)

- `iterate-review/bin/{run-lens,run-pass,prune-state}` — inert stubs pinning the
  argument surface, exit contracts, skill-root resolution, and the Python ≥ 3.9
  fail-fast check. Implementations land in Phases 1–2; SKILL.md steps are not yet
  rewired, so current review behavior is unchanged.
- README: the one-rule permission model (allowlist snippet for both install
  layouts), `python3 ≥ 3.9` prerequisite, and the upcoming `docs/reviews/`
  pass-log default with its existing-logs-untouched migration note.
- `iterate-review/SKILL.md` Pointers: the extended state-dir layout the runners
  will use (composed inputs, `pass-N.summary.json` as the pass's commit point,
  `run.lock` ownership, `debug/` namespace).

## 2.1.1 — 2026-07-28 — bound the content-regex match span

Fixes [#5](https://github.com/kaileconsulting/trinity-skills/issues/5), found while
dogfooding `iterate-review` on this repo.

### Fixed

- **A content regex could bridge an entire minified file.** Lens `content_regexes` are
  matched against changed content lines — but minified or single-line JSON makes a whole
  file *one* line, so a pattern like
  `(SELECT|UPDATE|…)\s+.*\b(FROM|TABLE)\b` spanned **959 characters** of unrelated
  prose and selected the `security` lens for a fixture containing no SQL.
  A regex is now evaluated against at most **400 characters** of a changed line, chunked
  with a **200-character overlap** so any genuine match up to 200 chars is still found
  in full. Bound and overlap are parsed from `lenses/README.md` like the other rule
  data, and an overlap ≥ span is a hard error rather than a non-terminating loop.

### Why this was worth fixing before a measurement period

Over-inclusion is the deliberate selection bias, so a spurious lens costs one Codex
call rather than correctness. But real repos contain minified JSON, and the next few
weeks are for measuring **whether the added lenses earn their keep**. A `security` lens
that fires on bundled artifacts and returns empty APPROVEs would make itself look
low-value — contaminating exactly the signal being collected.

### Added

- `selection/14-minified-json-span.diff` — a true regression fixture: it selects
  `security` spuriously *without* the bound and `senior-dev` alone with it. 13 → 14
  routing fixtures.
- 9 checker self-tests (44 → 53) covering chunking, the bound stopping a bridge, a
  genuine match surviving chunking at four offsets including chunk boundaries, and
  overlap ≥ span raising.

### Not changed

The same run also selected `qa` because `\bresponse\b` matched the word "response" in
prose mentioning a filename. That is **pattern breadth in the qa lens, not a mechanism
bug** — narrowing it would change routing behaviour and is a judgment call about the
lens rather than a fix. Left alone deliberately; issue #5 was corrected to say so.

## 2.1.0 — 2026-07-28 — classified open questions

A reviewer raising a question now says **who can settle it**, and that label decides
whether an unattended loop stops. Found by dogfooding: during the first multi-lens
`iterate-plan` run, neither lens could resolve a question that needed an external
lookup — the lenses run sandboxed with no network — while two other questions were
genuinely the author's call. The loop guardrail treated all three identically.

### Changed — **breaking** (reviewer output schema)

- **`new_questions` is now an array of objects**, not strings:
  `{question, settled_by, why}`. `settled_by` ∈
  `resolvable_in_fold | needs_lookup | needs_human`. Both skills.
  - Taken as a break rather than a `oneOf string|object` on purpose: an optional
    label is one that quietly stops being filled in.
  - `why` is **required** — a one-line justification, so the label can be audited
    instead of trusted. A bare enum is easy to rubber-stamp.
  - The contract states that **`needs_human` is the correct choice when unsure.**
    An unnecessary escalation costs one question; mislabeling the author's decision
    as machine-resolvable invites a fabricated answer.
- **The loop-mode human-judgment guardrail now halts only on `needs_human`.**
  `resolvable_in_fold` and `needs_lookup` are resolved by Opus and the loop
  continues; a *failed* lookup reclassifies to `needs_human` and then halts.
  Previously the guardrail read "a question Opus can't answer from the plan + repo
  context," which stopped unattended loops for questions a single file read would
  have answered.
- Both fold paths route by class, dedupe questions across lenses, take the **most
  escalating** label on a class conflict, and **sanity-check the label rather than
  trusting it** — a `resolvable_in_fold` that plainly needs the author's preference
  is treated as `needs_human`.
- Pass-log templates record each question's class, resolution, and any override.

### Migration

Seven tracked fixtures reshaped; question text preserved **verbatim**, container
only. Two notes:

- `iterate-plan/examples/pass-4-response.json` is the repo's only *real* Codex
  capture and is now lightly reshaped rather than byte-exact. The frozen copy at
  `v1/iterate-plan-v1/examples/pass-4-response.json` keeps the original shape.
- `v1/` is untouched — it carries its own schema copy and `tools/` does not scan it.

Runtime state files under `*/state/` are gitignored and were not migrated; they are
historical artifacts, and nothing reads them back against the schema.

### Added

- 4 parity rules (32 → 36) covering class routing, most-escalating conflict
  resolution, lookup-failure reclassification, and label auditing. The existing
  `guard-human-judgment` rule was tightened to require naming *which* class halts.
- 8 checker self-tests (36 → 44) asserting both schemas reject unclassified
  `new_questions`, reject an unknown `settled_by`, and require `why`.
- Merge goldens now demonstrate all three classes, including the case that
  **changed behavior**: in `iterate-review/examples/merge/01`, the "is the router
  behind auth middleware" question is `resolvable_in_fold` and no longer halts the
  loop, while the product-intent question still does. Scenario 02's single question
  is `needs_human`, so its halt is unchanged — both cases are pinned so the label
  isn't mistaken for a way to suppress halts.

### Known gaps

- **A lens can mislabel.** The mitigations are the unsure-default, the required
  `why`, and Opus's override — none of which is a guarantee. A `needs_human`
  question mislabeled `resolvable_in_fold` and not caught on review would get a
  fabricated answer. This is plan risk R2 surfacing in a new place.
- The value concentrates in loop mode. Attended, Opus already made this distinction
  by hand; the label makes it explicit and machine-actionable.
- **Routing behaviour is not mechanically tested — only schema shape is.** The 8 new
  self-tests assert the schemas reject unclassified questions, unknown classes, and a
  missing `why`. Nothing asserts that `needs_human` halts the loop and the other two
  continue, because there is no executable fold path to call: routing is prose Opus
  follows at runtime. The goldens state the expected continue-vs-halt outcome per
  class, which is the same coverage model merge correctness uses. Raised as a MEDIUM
  in review and recorded rather than resolved.

## 2.0.0 — 2026-07-28 — Axis 2: persona lenses

Each review pass now runs **several reviewer personas concurrently** and merges their
findings into one list. Same reviewer model, more question categories — this is a
*breadth* change, not a reliability one (model diversity is a separate, later axis).

Plan: [`docs/archive/trinity-axis-2-persona-lenses-2026-07-27.md`](docs/archive/trinity-axis-2-persona-lenses-2026-07-27.md).
Review trail: `docs/archive/code-review-phase{0,1,4}-*.md`.

### Added

- **Persona lenses.** `iterate-plan` runs `architect` + `product-manager` every pass.
  `iterate-review` runs `senior-dev` always, plus `security` and `qa` when the diff's
  shape selects them. Lenses are data-shaped records in `<skill>/lenses/<id>.md`.
- **Deterministic lens selection** — a rules table over changed paths and changed diff
  lines, explicitly *not* an LLM router. `senior-dev` is a floor that always runs, and
  borderline matches include the lens: a wasted Codex call is cheaper than a missed
  category.
- **Fan-out + merge.** N concurrent `codex exec` calls per pass; Opus merges by
  semantic judgment (same location **and** same asserted defect), aggregates verdicts
  **worst-of**, and records every finding's originating lens.
- **`FAILED` lens handling.** A lens that fails is retried once, then recorded as
  `FAILED` — orchestration metadata, not a verdict. It forces at-least-REVISE,
  preserves a `BLOCK` from any completed lens, and **blocks Converge** with a retry
  option, so the loop never converges having silently skipped a selected lens.
- **Loop mode** — `--loop` / `--until-approve` and an `(L)oop from here` checkpoint
  option. Automates `Continue` only, **never `Converge`**, and halts on five
  guardrails: APPROVE reached, max-pass cap (default 6, `--max-passes`, fresh per
  activation), BLOCK, non-convergence (merged HIGH+MEDIUM count not strictly
  decreasing over two transitions), or a fold needing human judgment.
- **Matched context per lens.** `iterate-plan` slices the plan H2 sections each lens
  declares in `requires_sections`; a lens whose section is missing runs anyway and is
  required to flag the gap rather than invent content.
- **Dev checks in `tools/`** — `check-parity.py` (32 shared-machinery rules present in
  both skills), `check-examples.py` (schema validity + fixture-name-claim checks),
  `test-checkers.py` (36 tests that the checkers fail when they should),
  `check-all.sh`. Requires `jsonschema`; see `requirements-dev.txt`.
- **A runnable reference implementation of lens selection** —
  `iterate-review/examples/selection/check-selection.py` plus 13 golden diff fixtures.
  The selection rules claim any two implementations agree on a diff; until this
  existed there was one implementation, and it was a language model reading prose.
  It parses its rule data from the lens frontmatter and `lenses/README.md` rather than
  restating it, so only the evaluation algorithm is duplicated. Test-only — never
  invoked during a real run.
- **Merge goldens** for both skills, covering co-report dedupe, two distinct concerns
  at one location, worst-of with an approving lens, `FAILED` preserving `BLOCK`,
  degraded context, and conflicting `open_question_answers`.
- **`v1/`** — the pre-lens skills, frozen and installable side-by-side via
  `./install.sh --with-v1`. Also tagged `v1.0`.

### Changed

- `reviewer-prompt.md` in both skills is now a **shared contract** that defers only
  ROLE and FOCUS to a lens fragment. Every lens runs under identical restrictions and
  returns the same schema.
- Merge rules gained two cases found while writing the goldens: two lenses answering
  the same `question_id` must be recorded **with the disagreement surfaced**, not
  silently reconciled (`iterate-plan`); and corrections must be deduped, since they
  apply *mechanically* and a duplicate can double-apply an edit (both skills).
- `install.sh` takes `--with-v1` and `--help`, and installs by repo-relative path so a
  skill's directory name need not match its location.
- Reviewer output schemas are **unchanged** — the split altered prompt *assembly*, not
  the contract.

### Fixed

- `iterate-review/examples/pass-malformed.response.json` had been **fake coverage
  since the initial release**. A `$comment` key made it schema-invalid
  (`additionalProperties: false`), so it would have been rejected by schema validation
  a step *before* reaching the patch-marker scan it existed to exercise. `$comment`
  removed from both pre-existing fixtures, and the file renamed to
  `pass-1-patch-marker-violation.response.json` — the old name implied malformed JSON,
  which it never was.
- `check-selection.py` returned wrong answers *silently* in three cases, all found by
  its own code review: renames across the `source_exts` boundary (removed lines
  attributed to the new path), git C-quoted paths, and tab-separated timestamps in
  plain unified diff headers. Each yielded zero changed source lines and quietly
  failed to select `qa`.

### Known gaps

- The plan's "single-lens path is a behavioral non-regression" criterion is
  **explicitly unmet**. It asserts *same findings* versus pre-Axis-2, which no fixture
  establishes and a nondeterministic reviewer arguably cannot.
- `check-parity.py` verifies a rule is *stated* in both skills, not that it is stated
  *correctly*. A rule wrong in both passes.
- Merge correctness is not mechanically tested anywhere. Semantic dedupe is Opus's
  judgment by design, so it ships goldens to compare against, not assertions.
- Matched context on diffs is prompt framing plus already-available inputs, not real
  extraction (no computed trust boundaries).

## 1.0.0 — 2026-05-19 — initial release

`create-plan`, `iterate-plan`, `iterate-review`. One reviewer persona per pass: a
single `codex exec` in a `-s read-only -a never` sandbox with `--output-schema`
enforcement, Opus as sole editor, patch-marker rejection, HISTORICAL audit trail, and
a human checkpoint after every pass.

Tagged `v1.0`. Frozen copies live in [`v1/`](v1/README.md) from 2.0.0 onward.
