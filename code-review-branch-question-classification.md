# Code Review — branch-question-classification

## Pass 1 — 2026-07-28 14:05 [HISTORICAL]

**Scope:** branch (vs `main` @ a3d6060) · **Diff size:** 720 lines · **Verdict:** REVISE (worst-of; no FAILED lenses) · **Lenses:** senior-dev, security, qa

Single pass by design (`--once`): this is a small focused change to the shared
reviewer contract, and a full convergence loop was judged not worth it for
speculative infrastructure. See the note on lens selection below.

### Findings

1. **Repo-file reads classified as `needs_lookup`, collapsing the class boundary** — HIGH · lens: **senior-dev, qa** (co-reported): the schema and both reviewer prompts define `needs_lookup` as a fact requiring something the reviewer *cannot do* (network, API, benchmark, command), and `resolvable_in_fold` as answerable from the full plan plus the repository. But both `SKILL.md` fold steps said "perform the lookup (**read a file**, query an API, run the command)" — which makes ordinary file reads `needs_lookup`. The `architect` fixture then encoded the wrong reading: the gateway-timeout question was labelled `needs_lookup` with a `why` stating that a config file in the repo answers it. Because the goldens teach the fold behaviour, the drift would have normalised the misclassification rather than catching it.
   → Opus: **incorporated** — verified against my own text first: the schema and prompts were already correct, so the defect was confined to the two `SKILL.md` fold steps plus one fixture. Both steps now read "reading any file in the repo is this class, **not** `needs_lookup`," and `needs_lookup` is explicitly "the fact is **outside the repository**." Reclassified the gateway-timeout question to `resolvable_in_fold`, and added a genuinely-external question (production p95 row count) so the golden still covers all three classes. The `expected-merge.md` table now states the boundary and why collapsing it matters: `needs_lookup` would degrade into "the lens couldn't see it," putting ordinary file reads one failed lookup away from a spurious human escalation.
   *Both lenses reached this from different angles — senior-dev via contract drift across prose and goldens, qa via the observable consequence (a failed repo read escalating as human judgment). Both lines of evidence kept.*

2. **A fixture showcases an intent question as machine-resolvable, undercutting the safe default** — MEDIUM · lens: senior-dev: `iterate-review/examples/pass-1-response.json` classified *"Is web/lib/parse.ts **intended** to be public API or internal helper?"* as `resolvable_in_fold` on the grounds that imports are checkable. Import evidence shows what *is*, not what was *meant* — so the fixture demonstrated exactly the borderline case the "when unsure, choose `needs_human`" rule exists to catch.
   → Opus: **incorporated** — reclassified the fixture to `needs_human` (question text left verbatim, per the migration's verbatim guarantee). Also fixed the *prompt's* own example, which had the same flaw: it now asks *"Does anything outside this module import `foo()`?"* — a usage question files settle — and explicitly contrasts it with the intent phrasing, which is `needs_human`.

3. **Routing behaviour is untested; only schema shape is** — MEDIUM · lens: qa: the 8 new self-tests assert the schemas reject bare strings, unknown `settled_by`, and missing `why`. None exercises the promised loop behaviour (`resolvable_in_fold` continues, `needs_lookup` continues after a successful lookup, a failed lookup reclassifies, `needs_human` halts). Text-parity and schema checks can pass while the actual fold halts on every question or ignores `needs_human`.
   → Opus: **disputed in part, incorporated in part.** Disputed on the mechanical coverage: **there is no executable fold path to test.** Routing is prose Opus follows at runtime; the repo ships no orchestrator, which is the same reason merge correctness is pinned by goldens rather than assertions (plan Q3). A test asserting "`needs_human` halts" would have to re-implement the fold to have anything to call. Incorporated on the substance: the goldens are the coverage mechanism, so scenario 01 now states the continue-vs-halt outcome per class explicitly, and the iterate-plan golden gained the same table. **The finding is nonetheless correct that this is a coverage gap, not a covered case** — recorded as such in the CHANGELOG's Known gaps rather than papered over.

### Code corrections applied

- (none — no lens returned `code_corrections`)

### New questions Codex raised

- (none — no lens filed any, which is itself mildly notable for a change that adds a question-classification field)

### Lens run summary

- senior-dev: REVISE · security: **APPROVE** · qa: REVISE

### Note on lens selection (Opus)

The deterministic mechanic selected all three lenses, but **both non-floor lenses matched for spurious reasons**, and the reference implementation and I disagreed — which `lenses/README.md` says to treat as a finding:

- `qa` matched `\bresponse\b` inside the *filename* `pass-4-response.json`.
- `security` matched the SQL regex inside `pass-4-response.json`, which is **single-line minified JSON** — so the entire file is one "changed content line" and the regex's `.*` spans it end to end.

My own reading would have selected `senior-dev` alone. The over-inclusion bias makes running all three the correct call for this pass, and `security` returning a clean APPROVE cost one Codex call — but the mechanism issue is real: **content regexes matched against minified JSON effectively match against whole files.** Not fixed here (out of scope for a `--once` pass on an unrelated change); worth a fixture and a bound on how much of a "line" a content regex may span.

Recorded rather than actioned, deliberately.

### Diff snapshot reference

Diff captured at 2026-07-28 14:05; head SHA `31b2294`.
