# Expected merge — scenario 01: dedupe + worst-of

Golden for the **semantic** half of the per-pass loop (`SKILL.md` steps 11–14).
Unlike selection routing, merge is Opus's judgment and cannot be asserted by a
script — so this is a worked example to compare a real run against, not an
executable test.

**Scenario.** The diff is `../../selection/02-unauth-endpoint.diff` (a new
unauthenticated admin endpoint with interpolated SQL). Selection picks all three
lenses: `senior-dev, security, qa`.

## Inputs

| Lens | Verdict | Findings filed |
|---|---|---|
| `senior-dev` | REVISE | SQL interpolation (HIGH), connection not released (MEDIUM) |
| `security` | REVISE | SQL injection (HIGH), no authorization (HIGH) |
| `qa` | **APPROVE** | no tests for new endpoint (MEDIUM) |

Five findings filed across three lenses.

## Expected aggregate verdict: REVISE

Worst-of over `{REVISE, REVISE, APPROVE}` with `BLOCK > REVISE > APPROVE`.

The load-bearing part: **`qa` returned APPROVE and that does not pull the
aggregate up.** No lens is `FAILED`, so `FAILED` handling is not exercised here
(see scenario 02).

> **`qa`'s APPROVE-with-a-MEDIUM is a deliberately atypical fixture, not a model
> to imitate.** The schema permits it — only HIGH *always* blocks APPROVE — and
> the combination is what makes worst-of visibly do work: if the aggregate were
> best-of, or if an approving lens were allowed to short-circuit the others, this
> pass would wrongly converge. But a reviewer filing an actionable missing-tests
> finding would more commonly return REVISE, and nothing here should be read as
> encouraging lenses to approve while filing real issues. The verdict is chosen to
> exercise the aggregation rule, not to demonstrate typical reviewer behaviour.
> *(Raised as a `code_correction` in the Phase 4 review; kept as APPROVE because
> changing it to REVISE would remove the only case in the fixture set where
> worst-of has to discriminate.)*

## Expected merge: 5 filed → 4 merged

### One pair merges

`senior-dev` "Query parameter interpolated directly into SQL string" and
`security` "SQL injection via the q query parameter" are **the same defect at the
same location** (`src/routes/admin.js:17`, untrusted `q` reaching `db.query` as
concatenated text). They collapse into one finding retaining **both** lens ids.

Keep the more actionable description — `security`'s names the source, the sink,
and a concrete exploit value — rather than mechanically keeping the first.

### Two findings at the SAME location do NOT merge

`security` "no authorization" and `qa` "no tests" both concern the endpoint
registered at `src/routes/admin.js:15`. Same location, **different asserted
defects** (missing access control vs. missing coverage). They stay separate.

This is the under-dedupe direction of plan risk **R4**: a merge keyed on location
alone would wrongly collapse these and silently drop a HIGH security finding.
Location is necessary but not sufficient — the *asserted defect* must also match.

### Expected merged list

| # | Finding | Severity | Lens(es) |
|---|---|---|---|
| 1 | SQL injection via `q` — untrusted input concatenated into the statement | HIGH | `senior-dev`, `security` |
| 2 | `GET /admin/users` enforces no authorization | HIGH | `security` |
| 3 | New endpoint ships with no tests covering observable behaviour | MEDIUM | `qa` |
| 4 | Pooled DB connection never released on the error path | MEDIUM | `senior-dev` |

Plus one `code_correction` (route grouping, from `senior-dev`) applied
mechanically, and two `new_questions` carried forward.

## Expected pass log — exactly ONE block for three lenses

```markdown
## Pass 1 — 2026-07-28 09:14 [HISTORICAL]

**Scope:** working · **Diff size:** 14 lines · **Verdict:** REVISE (worst-of; no FAILED lenses) · **Lenses:** senior-dev, security, qa

### Findings

1. **SQL injection via the `q` query parameter** — HIGH · lens: senior-dev, security: src/routes/admin.js:17 concatenates untrusted `req.query.q` into the WHERE clause; `%' OR '1'='1` returns every row.
   → Opus: incorporated — replaced concatenation with a bound parameter.
2. **`GET /admin/users` enforces no authorization** — HIGH · lens: security: src/routes/admin.js:15 registers the route with no auth middleware; returns id/email/name for every user.
   → Opus: incorporated — added the requireAdmin middleware to the route.
3. **New endpoint ships with no tests covering observable behaviour** — MEDIUM · lens: qa: empty `q`, LIKE metacharacters, and the db-rejection path are all unexercised.
   → Opus: incorporated — added tests for all three paths.
4. **Pooled DB connection never released on the error path** — MEDIUM · lens: senior-dev: src/routes/admin.js:16 has no try/finally; repeated query failures exhaust the pool.
   → Opus: incorporated — wrapped the query in try/finally.

### Code corrections applied

- src/routes/admin.js:14 — new route separated from the other registrations → regrouped above module.exports.

### New questions Codex raised

- Is this router mounted behind app-level authentication middleware, or is each route expected to guard itself?
- Should `q` containing `%` or `_` be treated as a literal search string, or is metacharacter matching intended?

### Lens run summary

- senior-dev: REVISE · security: REVISE · qa: APPROVE

### Diff snapshot reference

Diff captured at 2026-07-28 09:14; head SHA `abc1234`.
```

## Expected checkpoint — exactly ONE prompt for three lenses

```
Pass 1: REVISE across senior-dev, security, qa, 4 findings, 1 correction.
Recommendation: Continue. Choose: (C)ontinue / (V)Converge / (A)bort / (L)oop
```

Three Codex calls, one HISTORICAL block, one prompt. That invariant is what keeps
fan-out from multiplying the human's workload (plan risk **R1**).

## Secondary assertion — loop mode halts here

If this pass ran under `--loop`, it would **not** auto-continue, despite the
verdict being REVISE and every finding incorporated. The fifth guardrail
("fold needs human judgment") fires on the first `new_question`: whether the
router sits behind app-level auth **cannot be answered from the diff** — the diff
shows the route file, not the mount point. Loop mode stops and escalates.

Worth pinning because it's the easiest guardrail to under-apply: it is tempting
to treat "all findings incorporated" as sufficient to keep looping.

## What a wrong merge looks like

Both directions of R4, so a regression is recognisable:

| Wrong output | Which failure |
|---|---|
| 5 findings, SQL listed twice under different titles | **Under-dedupe** — co-reported defect not collapsed; the human triages the same issue twice and lens attribution is unusable for ROI |
| 3 findings, authz and no-tests collapsed into one "endpoint problems" entry | **Over-dedupe** — location-keyed rather than defect-keyed; a HIGH disappears into a MEDIUM's wording |
| 4 findings, SQL tagged `security` only | **Attribution loss** — a co-report must retain *all* contributing lens ids or the ROI metric under-counts `senior-dev` |
| Aggregate APPROVE | **Aggregation inverted** — best-of instead of worst-of; `qa`'s APPROVE must not outrank two REVISEs |
| Two checkpoints, or one block per lens | **Single-checkpoint invariant broken** (R1) |
