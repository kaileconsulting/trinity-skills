# Code Review — commit-6286fdd

Review of the Phase 3 commit series (`1c346fa` + `6286fdd`, iterate-plan
runner port) from the runner-scripts plan
(`docs/runner-scripts-artifact-hygiene-2026-08-06.md`). Loop mode.

## Pass 1 — 2026-08-10 14:20 [HISTORICAL]

**Scope:** commit series b2cbe09..6286fdd · **Diff size:** 3636 lines · **Verdict:** REVISE (worst-of) · **Lenses:** senior-dev, security, qa

### Findings

1. **Standalone run-lens leaks orchestration exceptions instead of honoring its CLI contract** — MEDIUM · lens: senior-dev: iterate-plan run-lens only catches CompositionError; codex missing from PATH or publication OSErrors escape as tracebacks, violating the documented "1 = orchestration error with a usable diagnostic" contract.
   → Opus: incorporated — run_one_lens call now catches `(CompositionError, OSError)` → exit 1 with a `run-lens:` diagnostic. Applied to **both skills'** run-lens (iterate-review shared the trait; aligning now rather than letting the next pass file the consistency gap). Fixture-pinned in both suites via a shim-PATH (python3+git only) so the machine's real codex can't satisfy the lookup.
2. **Frontmatter ID validation can be satisfied by body content** — MEDIUM · lens: senior-dev: `_frontmatter_id` scanned the whole lens file, so a body line `id: architect` could pass the loud rule-data-drift check.
   → Opus: incorporated — scanning now stops at the frontmatter's closing `---`; new fixture: a lens with no frontmatter id but a body `id:` line fails loudly.
3. **Standalone run-lens accepts an empty plan that run-pass rejects** — MEDIUM · lens: qa: input validation depended on which command boundary was used.
   → Opus: incorporated — empty-input refusal now at both skills' run-lens boundaries (`the plan/diff is empty — nothing to review`), fixture-pinned in both suites.
4. **Codex working-directory contract is not behaviorally tested** — MEDIUM · lens: qa: the fake codex ignored argv, so a dropped or misplaced `-C` kept the suite green.
   → Opus: incorporated — the fake codex now records argv+cwd per invocation; new fixtures assert `-C <resolved-plan-dir>` sits immediately after `exec` at both command boundaries.

### Code corrections applied

- (none issued)

### New questions Codex raised

- (none)

### Lens run summary

- senior-dev: REVISE · security: APPROVE · qa: REVISE

### Diff snapshot reference

Diff captured at 2026-08-10 14:15; head SHA `6286fdd`. Folds committed as `5abb4b1`; suites 122/122 + 55/55, check-all green.

## Pass 2 — 2026-08-10 14:45 [HISTORICAL]

**Scope:** commit series b2cbe09..5abb4b1 · **Diff size:** 3823 lines · **Verdict:** REVISE (worst-of) · **Lenses:** senior-dev, security, qa

### Findings

1. **Repeated required H2 headings are merged instead of stopping at the next H2** — HIGH · lens: senior-dev, qa (co-reported; severities HIGH/MEDIUM, worst kept): `extract_section` checked the title match before the section-end check, so a duplicate `## <title>` re-opened the slice and merged both sections, contradicting the documented "slice ends at the next H2" contract and over-exposing matched context.
   → Opus: incorporated — the in-section branch now runs first: ANY subsequent H2 (identical title included) terminates the slice. Fixture: duplicate heading yields only the first section. (Noted for the record: the original SKILL.md awk helper had the same duplicate-merging behavior; the documented contract governs.)
2. **Trusted-path validation has a symlink-swap race that can exfiltrate files outside the allowed boundary** — HIGH · lens: security: `ensure_trusted_path` realpaths at validation, but the later `read_text` re-traverses the pathname — a concurrent writer could swap a component mid-window and pull an out-of-boundary file into the network-backed codex prompt.
   → Opus: incorporated — new shared `read_trusted_text`: validate → open (O_NONBLOCK) → re-verify AFTER the open that the pathname still resolves in-boundary AND still names the opened inode → read from the descriptor. Non-regular files (FIFO/device/directory) refuse outright without hanging; benign in-boundary symlinks still work; UTF-8 enforced. Wired through all four CLIs (`--diff`/`--intent`/`--plan`/`--note`) and the pass-log read (`read_prior_passes` gained an anchored mode). Pinned by a deterministic swap-injection fixture (os.open redirected to an out-of-boundary inode → refusal) plus FIFO refusal fixtures at module and subprocess boundaries. Same fd-anchoring discipline Phase 2 established for deletion, now on the read side.

### Code corrections applied

- (none issued)

### New questions Codex raised

- (none)

### Lens run summary

- senior-dev: REVISE · security: REVISE · qa: REVISE

### Diff snapshot reference

Diff captured at 2026-08-10 14:30; head SHA `5abb4b1`. Folds committed as `9baf676`; suites 122/122 + 62/62, check-all green.

## Pass 3 — 2026-08-10 15:05 [HISTORICAL]

**Scope:** commit series b2cbe09..9baf676 · **Diff size:** 4110 lines · **Verdict:** APPROVE (worst-of) · **Lenses:** senior-dev, security, qa

### Findings

(none — all three lenses returned APPROVE with zero findings)

### Code corrections applied

- (none issued)

### New questions Codex raised

- (none)

### Lens run summary

- senior-dev: APPROVE · security: APPROVE · qa: APPROVE

### Diff snapshot reference

Diff captured at 2026-08-10 15:00; head SHA `9baf676`. Loop halted at the APPROVE guardrail; Converge decision presented to the human.
