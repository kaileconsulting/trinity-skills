# Expected merge — scenario 02: a FAILED lens must not downgrade BLOCK

Golden for the `FAILED`-lens branch of `SKILL.md` step 11 and the Converge block
in step 14. This scenario exists to pin the single most misreadable rule in the
shared machinery.

**Scenario.** `input.diff` adds an in-process TTL cache in front of a permission
lookup. Selection picks all three lenses (`senior-dev` always; `security` via the
`permission` content regex; `qa` via `non_trivial_without_tests` — 10 changed
source lines, no test change).

## Inputs

| Lens | Outcome | Findings filed |
|---|---|---|
| `senior-dev` | **BLOCK** | replica-incoherent authz decision (HIGH), unbounded cache (MEDIUM) |
| `security` | **`FAILED`** | none usable — see below |
| `qa` | REVISE | TTL/revocation untested (MEDIUM), order-dependent tests (MEDIUM) |

### What `FAILED` means here

`security` was invoked, retried once per step 11, and still produced nothing
usable:

- **Attempt 1** — process exited non-zero before writing a response.
- **Attempt 2** — wrote truncated output, preserved as
  `pass-1.security.response.json.malformed`. It stops mid-string inside the first
  finding's `description`, so it is not parseable JSON and fails
  `--output-schema` validation.

The `.malformed` suffix is deliberate: the file is invalid JSON on purpose, and
naming it `.json` would break any tooling that validates fixtures in this tree.

`FAILED` is **orchestration metadata, not a verdict.** The reviewer schema is
untouched — it has no `FAILED` enum value and must not gain one. `FAILED` lives
only in the skill's bookkeeping and the pass log's Lens run summary.

## Expected aggregate verdict: BLOCK

This is the whole point of the fixture. Two rules apply at once:

1. A `FAILED` selected lens raises the aggregate to **at least** REVISE.
2. **BLOCK is preserved if any *completed* lens returned BLOCK.**

Rule 1 is a **floor, not an assignment.** `senior-dev` completed with BLOCK, so
the aggregate is BLOCK.

> **The bug this fixture catches:** implementing rule 1 as `if any_failed:
> verdict = REVISE`. That reads plausibly, satisfies the phrase "raises to at
> least REVISE," and **silently downgrades a BLOCK to a REVISE** — turning a
> stop-everything verdict into an ordinary iterate-again verdict. Under `--loop`
> the damage compounds: BLOCK is a halt guardrail, so a downgraded BLOCK lets the
> loop keep auto-continuing past a change that should have stopped it cold.

Worst-of over the completed lenses `{BLOCK, REVISE}` is BLOCK; the `FAILED` floor
of REVISE is already satisfied and changes nothing.

## Expected merge: 4 findings, no dedupe possible

Nothing merges. `security` contributed no usable findings, and `senior-dev`'s and
`qa`'s concerns are genuinely distinct.

| # | Finding | Severity | Lens |
|---|---|---|---|
| 1 | In-process cache makes an authz decision incoherent across replicas | HIGH | `senior-dev` |
| 2 | Cache is unbounded | MEDIUM | `senior-dev` |
| 3 | TTL boundary and revocation behaviour are untested | MEDIUM | `qa` |
| 4 | Cached decision makes tests order-dependent | MEDIUM | `qa` |

**Do not fold the truncated response's partial finding.** Its `description` is
cut off mid-sentence, so its claim is incomplete and its severity unverified.
A failed lens contributes nothing; that is what makes it worth retrying rather
than salvaging. Salvaging partial output is how a truncated HIGH gets folded as
though the reviewer had finished making its case.

## Expected pass log

```markdown
## Pass 1 — 2026-07-28 10:02 [HISTORICAL]

**Scope:** working · **Diff size:** 16 lines · **Verdict:** BLOCK (worst-of; security FAILED after retry) · **Lenses:** senior-dev, security, qa

### Findings

1. **In-process cache makes an authorization decision incoherent across replicas** — HIGH · lens: senior-dev: after a revocation, whether a request is allowed depends on which replica serves it, for up to 300s; the cache preserves a stale allow instead of failing closed.
   → Opus: incorporated — reverted the in-process cache; opened a follow-up for a shared-store cache with explicit invalidation.
2. **Cache is unbounded** — MEDIUM · lens: senior-dev: no size limit, eviction only on read.
   → Opus: incorporated — moot after the revert; recorded on the follow-up.
3. **TTL boundary and revocation behaviour are untested** — MEDIUM · lens: qa: cache miss/hit, the TTL boundary, and allow-then-revoke are all unexercised.
   → Opus: incorporated — carried onto the follow-up as required coverage.
4. **Cached decision makes tests order-dependent** — MEDIUM · lens: qa: module-level state leaks a cached allow between tests in one process.
   → Opus: incorporated — the follow-up requires an injectable cache.

### Code corrections applied

- (none)

### New questions Codex raised

- What measured latency problem motivated caching this lookup? The answer determines whether a shared-store cache is needed at all.

### Lens run summary

- senior-dev: BLOCK · security: FAILED · qa: REVISE

### Diff snapshot reference

Diff captured at 2026-07-28 10:02; head SHA `def5678`.
```

## Expected checkpoint — Converge is unavailable

```
Pass 1: BLOCK across senior-dev, security, qa (security FAILED after retry), 4 findings, 0 corrections.
Converge is blocked: verdict is BLOCK, and the security lens produced no usable output.
Recommendation: Continue. Choose: (C)ontinue / (R)etry security / (A)bort
```

Two things must be true of this prompt:

- **`(V)Converge` is absent.** Two independent reasons block it — the BLOCK verdict
  and the `FAILED` lens. Either alone is sufficient. A loop that converged here
  would have skipped a selected lens entirely.
- **`(R)etry` is offered**, naming the failed lens. Without it the only way to get
  `security`'s view is to re-run the whole pass.

`(L)oop` is also absent: BLOCK is a halt guardrail, so offering to loop from a
BLOCK contradicts the guardrail.

## Secondary assertion — loop mode halts on two independent guardrails

Under `--loop` this pass halts twice over:

1. **BLOCK verdict** → stop.
2. **Fold needs human judgment** → the open question (what latency problem
   motivated this) cannot be answered from the diff plus repo context.

Both must be reported. Surfacing only the first would let a reader think a
non-BLOCK rerun would resume cleanly, when the open question stops it anyway.

## What a wrong result looks like

| Wrong output | Which failure |
|---|---|
| Aggregate REVISE | **The headline bug** — `FAILED` treated as an assignment rather than a floor; BLOCK silently downgraded |
| Aggregate BLOCK, but `(V)Converge` offered | `FAILED` did not block Converge; the loop can converge having skipped a selected lens |
| 5 findings, including the truncated one | Partial output from a failed lens salvaged; an unverified HIGH enters the fold |
| `security: FAILED` missing from the Lens run summary | The pass log no longer records that a selected lens was skipped — invisible coverage gap |
| Verdict recorded as `FAILED` | `FAILED` leaked into the verdict space; the reviewer schema has three verdicts and must keep three |
| Retry not attempted before recording `FAILED` | Step 11 requires exactly one retry first; a transient crash becomes a coverage gap |
