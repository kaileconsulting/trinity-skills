---
name: create-plan
description: Scaffold a new plan markdown file in the project's `docs/` directory using the standard template. Use whenever the user wants to draft a plan, write a plan, sketch a plan, start a plan, create a plan, or says things like "let's plan out X" / "I want to plan how we'll do Y" / "draft a plan for Z" — even if they don't explicitly say "scaffold." Sets up the structure that `iterate-plan` (Codex design review) and `iterate-review` (per-phase Codex code review) depend on. Trigger phrases: "/create-plan", "create a plan", "draft a plan", "scaffold a plan", "start a plan", "let's plan X out", "write a plan for Y."
---

# `create-plan`

Scaffolds a new plan document in the active project's `docs/` directory using the canonical template at `~/.claude/skills/create-plan/template.md`. The template encodes the structural conventions that `iterate-plan` (design review) and `iterate-review` (per-phase code review) rely on — Q-numbered open questions, per-phase iterate-review markers, HISTORICAL section stubs, etc.

**The skill scaffolds; the human authors.** This skill copies the template, sets the title, prunes the unused phasing variant, and pre-fills phase headers if applicable. It does not generate any TL;DR, Why, Approach, or other content — that's the author's job.

## When to invoke

Trigger when the user wants to start a new plan document. Common phrasings:
- "Let's create a plan for X"
- "Draft a plan to do Y"
- "Scaffold a plan for Z"
- `/create-plan <initiative name>`
- "I want to plan how we'll tackle the W refactor"

This is the first skill in the trinity workflow:
1. **`create-plan`** (this skill) — scaffold the plan file
2. **`iterate-plan`** — Codex design review of the drafted plan, fold findings, loop to APPROVE
3. **`iterate-review`** — per-phase Codex code review of the implementation against the approved plan

Do not invoke for editing or reviewing existing plans — those are `iterate-plan` / `iterate-review` jobs.

## Procedure

### Step 1 — Capture the initiative name

If the user provided a name in the invocation (e.g., `/create-plan ORCID PI Unification`), use it directly. Otherwise ask: "What's the initiative this plan is for? Give me a short name — it'll become both the plan's H1 title and its filename slug."

The name should be human-readable (a few words). Don't use it as-is for the filename; slugify it in step 4.

### Step 2 — Determine plan type

Ask the user:

> Is this an **initiative** (multi-track / multi-day work, broken into phases — e.g., "API+MCP server", "ORCID PI unification") or a **fix** (single-track / session-scope, broken into steps — e.g., a bug fix, a small audit)?

Reasoning to share with the user if they're unsure:
- **Initiative** → uses `## Phasing` with `### Phase 0/1/2/...` sub-sections, each with explicit iterate-review markers. Right when work spans multiple days, has parallel tracks, or has natural review checkpoints between phases.
- **Fix** → uses `## Step-by-step plan` with `### Step 1/2/3...` sub-sections. Right for single-session work where iterate-review (if used at all) runs once at the end.

### Step 3 — Capture risk posture (both plan types)

Ask the user three questions, regardless of plan type — these apply to every plan:

> 1. **Audience & reach** — who uses this, roughly how many, behind what perimeter?
> 2. **Blast radius & recoverability** — what does a defect cost, and is the damage reversible? (e.g., "a lost draft is retypeable" vs "a wrong merge ships to customers")
> 3. **Ship bar** — what class of defect blocks ship vs gets logged as an accepted risk? Name any trust boundaries where full rigor applies regardless (e.g., an auth boundary, an approve/merge path).

**For initiative plans:** record each answer under its own `PF-` subsection in the Risk posture section's full variant (`PF-audience`, `PF-blast`, `PF-shipbar`).

**For fix plans:** condense the three answers into the mandatory one-paragraph lightweight variant, labeling each inline by its `PF-` id.

Share with the user why this isn't optional: the `PF-` ids are stable anchors that both `iterate-plan` and `iterate-review`'s posture-aware composition, and both skills' `accepted-risk` disposition, reference by id, never by prose — a plan without this section can't participate in that machinery. This step cannot be skipped for either plan type.

**Then ask a fourth question — unconditionally, on every scaffold, for both plan types:**

> 4. Are you already accepting any known risks — specific, real behaviors you've decided not to fix?

Ask this every time, even when the answer is obviously "none" — it does not wait for the author to volunteer one. An unseeded register costs real re-litigation later: `iterate-review`'s provenance gate honors only register entries that predate the diff under review, and `iterate-plan`'s (Q5's HEAD-sourced register composition, never the working tree) honors only entries that exist at HEAD — so a risk seeded after the fact can never wave through the findings it was meant to cover, in either loop. Plan time is the last cheap moment to seed it, and this question is the only thing standing between "the author happened to mention it" and it actually getting recorded.

**"None" proceeds with nothing written** — no empty-register scaffolding, no ceremony.

**A dictated risk** (a real, disproportionate risk the author already knows they're accepting) flows into the seeding procedure below, unchanged:
1. Resolve `<project-root>/docs/risk-posture.md` (same project-root resolution as Step 5).
2. If it doesn't exist, create it with a `## Accepted risks` H2 and the new entry.
3. If it exists and already has a `## Accepted risks` H2, append the entry under that H2.
4. If it exists but has no `## Accepted risks` H2 yet (a valid file can carry only `PF-` fields, seeded some other way — e.g. authored directly by the repo owner for standalone-review fallback), add the H2 to the file and then the entry under it. Don't create a second file or a differently-named section.
5. Use the register shape from the template's "REGISTER SHAPE REFERENCE" comment: a stable `RR-<YYYY-MM-DD>-<slug>` id, the specific behavior, its bound, its recovery path, and the acceptance date. Never a blanket suppression ("ignore X findings") — if what the author describes reads as a category rather than a named behavior, push back and ask for the specific case.

This is the one path where an accepted risk needs no separate confirmation step: the author is dictating it directly into the plan-authoring conversation, which is itself the confirmation. (Contrast with `iterate-plan`'s or `iterate-review`'s `accepted-risk` disposition, either of which is an editor *proposal* during automated review and does require a later human confirm.)

**Commit-before-review boundary.** `iterate-plan`'s register-aware lens composition sources the register from the repo's committed `HEAD`, never the working tree — so a freshly seeded entry is review-visible, and provenance-valid, only once it's committed. **Commit the scaffolded plan and its register entry together before invoking `iterate-plan`.** This matches the existing workflow (plans are committed before review anyway); this note just says the boundary out loud instead of relying on it silently.

### Step 4 — For initiatives only: collect phase metadata

Skip this step entirely for fix-type plans.

For initiatives, ask:

> How many phases? For each phase I'll need: (1) a short name, (2) the iterate-review marker — `YES`, `NO`, or `CONDITIONAL`, with a one-line rationale.

The iterate-review marker is load-bearing because `iterate-review` reads it to know which phases to run a code-review pass against. Set deliberately:
- `YES` — phase ships meaningful code changes that warrant Codex code review (security model, data migration, API surface).
- `NO` — phase is doc-only, setup-only, or otherwise has no code surface worth reviewing.
- `CONDITIONAL` — phase may or may not warrant review depending on what gets built (e.g., "review only if migration touches new tables"). Capture the condition in the rationale.

Collect for each phase:
- `name` — short descriptor (e.g., "Foundations", "Skeleton + auth + first endpoint", "Full endpoint surface")
- `marker` — `YES` / `NO` / `CONDITIONAL`
- `rationale` — one-line explanation

Recommended phase 0 default: name="Foundations", marker="NO", rationale="setup-only, no code to review." Offer this as a starting point but let the user override.

**Recommended final-phase default: E2E test coverage** — when the plan ships user-facing UI or API behavior changes, propose a final phase named "E2E test coverage" (or similar) with marker=YES.

**Scope of an E2E test coverage phase:**
- **Write new specs** that cover behavior added or changed in earlier phases.
- **Audit existing specs** for any that test behavior the earlier phases *removed* or *significantly changed*; deprecate or rewrite them as appropriate.
- **NOT a suite-execution gate.** Running the full suite against production is the deploy CI/GHA workflow's job; the phase lands new specs into the suite, and the next deploy after the phase ships exercises them naturally. "All specs pass against prod" should not appear as Phase N acceptance — that pushes a CI responsibility onto the plan.

Rationale to share with the user: "User-facing affordances added in earlier phases need automated coverage so regressions don't slip on the next sprint, and iterating on test cases through the same Codex review loop catches fragile selectors, missing-coverage gaps, and missed deprecation candidates. Building tests as a phase rather than an afterthought keeps the test work in scope and accounted for."

Skip this default for: doc-only plans, plans that ship only data-pipeline / migration changes already covered by smoke checks, fixes already covered by existing E2E, plans where the user explicitly says they'll add E2E in a follow-up. When in doubt, propose it — the user can override down to NO.

Offer this as a starting point but let the user override.

### Step 5 — Resolve target file path

1. Locate the project root: run `git rev-parse --show-toplevel` via Bash. If that fails (not a git repo), fall back to the current working directory and warn the user.
2. Slugify the initiative name: lowercase, replace whitespace + non-alphanumerics with `-`, collapse multiple `-` into one, trim leading/trailing `-`.
3. **Append today's creation date as a `-YYYY-MM-DD` suffix** to the slug, then append `.md`. Use the date from your system context (e.g., the `# currentDate` block in the conversation); if unavailable, run `date -u +%Y-%m-%d` via Bash. Example: initiative "ORCID PI Unification" + creation date 2026-05-07 → filename `orcid-pi-unification-2026-05-07.md`.
4. Target path: `<project-root>/docs/<slug>-<YYYY-MM-DD>.md`.
5. If `docs/` doesn't exist under the project root, create it.
6. **If the target file already exists, refuse and stop.** Tell the user the path and ask whether they want to (a) pick a different name, (b) edit the existing file directly, or (c) explicitly delete and recreate. Don't auto-overwrite.

**Why the date suffix.** The dated filename makes the archived `docs/archive/` folder self-documenting — reviewers can see at a glance when each plan was drafted, which is useful for time-correlating plans with related ship commits, milestones-index entries (if the project tracks one), changelog updates, customer-feedback transcripts, or other external context. Reference / brainstorm / audit docs (non-plan documents in `docs/`) stay dateless; the suffix applies specifically to plans produced by this skill.

### Step 6 — Generate the plan file

Read the template at `~/.claude/skills/create-plan/template.md`. Apply these transforms before writing to the target path:

1. **Strip the top template-header HTML comment block** — the legend explaining REQUIRED / RECOMMENDED / TOOLING-RESERVED is authoring guidance for the template itself, not for individual plans. The scaffolded plan should start cleanly at the H1 title.

2. **Replace the H1 title.** The template has `# <Initiative Name> — Plan`; substitute the user's actual name: `# <ActualName> — Plan`.

3. **Keep all inline `<!-- ... -->` guidance comments under section headers.** These are intentional authoring hints. The template comment header (which you stripped in transform #1) instructs the author to remove them before committing — they're scaffolding for the author, not noise to delete here.

4. **Prune the unused Risk posture variant, under the `## Risk posture` H2, and populate the surviving one with Step 3's answers.** Unlike TL;DR/Why/Approach (author-authored later, never asked about at scaffold time), Step 3 actively collects these three answers *during this same conversation* — so, unlike those sections, don't leave `...` placeholders here.
   - **For `fix` type:** delete the `### Full variant (initiatives)` subsection (heading + its three `#### PF-` subsections, all the way until `### Lightweight variant (fixes)`). Keep the lightweight variant's structure, replacing its `**PF-audience:** ... **PF-blast:** ... **PF-shipbar:** ...` stub with the actual one-paragraph answer assembled in Step 3, each still labeled by its `PF-` id.
   - **For `initiative` type:** delete the `### Lightweight variant (fixes)` subsection (heading + body until the next H2 or comment block). Keep the full variant's three `#### PF-` subsections, replacing each one's `...` placeholder with that question's Step 3 answer.
   - **Both types:** keep the "REGISTER SHAPE REFERENCE" comment block as-is — it documents `docs/risk-posture.md`'s shape and isn't type-specific.

5. **Prune the unused phasing variant.**
   - **For `fix` type:** delete the entire `## Phasing` section (heading + all `### Phase N` sub-sections + their bodies, all the way until the next H2 heading). Keep `## Step-by-step plan` with the empty Step 1 / Step 2 stubs intact.
   - **For `initiative` type:** delete the entire `## Step-by-step plan` section (same rule — heading + body until next H2). Keep `## Phasing`, but **replace the three example phases** under it with one `### Phase N` entry per user-provided phase. Each generated phase should have:

   ```markdown
   ### Phase N — <user-provided name> (~estimate)
   **Deliverables:**
   - ...

   **Acceptance:**
   - ...

   **Iterate-review:** <YES|NO|CONDITIONAL> (rationale: <user-provided rationale>)
   **Status:** not started
   ```

   Number phases starting from 0 (Phase 0, Phase 1, ...). The `Status` field is initialized to `not started`; iterate-review updates it on phase APPROVE (`in progress` → `reviewed` → `shipped`). The author fills in deliverables, acceptance, and the time estimate.

   For `fix` type: the template's `## Step-by-step plan` already includes a `**Status:** not started` line under each Step heading — keep it as-is, no extra transform needed.

6. **Leave the rest untouched** — Acceptance criteria, Risks, Open questions, Out of scope, Closeout, References, and the TOOLING-RESERVED tail (`## Review checkpoints`, `## Pre-flight review pass`, `## Codex review pass N`) all stay as the template provides them.

Write the result to the target path via the Write tool.

### Step 7 — Print next-step guidance

Tell the user:

1. The absolute path of the file you wrote.
2. The REQUIRED sections they need to fill in: TL;DR, Why/Context, Who/Use cases, Approach, Acceptance criteria, Risks, Open questions, Out of scope, **Closeout**, References. (For multi-phase plans: also fill in per-phase deliverables, acceptance, and time estimates.) **Risk posture is already filled in** from Step 3's answers — mention this so the author doesn't waste time hunting for a placeholder that isn't there.
3. The RECOMMENDED sections to consider depending on plan type — see the inline `<!-- ... -->` comments in the file for guidance.
4. **Status discipline.** Each phase / step has a `**Status:** not started` field. Update it as work progresses (`in progress` when started, `shipped` when commits land). For phases marked Iterate-review YES or CONDITIONAL, iterate-review will update Status to `reviewed` automatically on APPROVE.
5. **Closeout discipline.** When all phases ship and acceptance is met, run the `## Closeout` checklist before declaring done. The final "git mv to archive" step is the canonical "this plan is done" signal — it makes plan state self-describing across session resumes and timeouts.
6. To remove all inline `<!-- ... -->` guidance comments before committing the plan.
7. When the plan content is drafted, invoke `iterate-plan` for Codex design review.

Keep the message short — the file's inline comments carry the detailed authoring guidance.

## Hard rules

- **Never auto-generate plan content.** Don't draft TL;DR, fabricate use cases, invent acceptance criteria, or speculate about open questions. The skill scaffolds structure; the human authors substance. If the user asks the skill to "fill in the TL;DR too," redirect: that's a separate authoring task that happens after scaffolding.
- **Never overwrite an existing plan file.** If the target path exists, refuse and surface alternatives.
- **Never modify the canonical template** at `~/.claude/skills/create-plan/template.md`. If the user wants to change template structure, that's a separate task and requires careful coordination with `iterate-plan`'s reviewer expectations (Q-numbering, HISTORICAL section format).
- **Don't validate REQUIRED sections after scaffolding.** That's `iterate-plan`'s job — its reviewer will flag missing TL;DR, Why, etc. as findings on the first pass. This skill's job ends at writing the file.

## Pointers

- `template.md` — the canonical plan template (read by step 6).
- Sibling skill: `~/.claude/skills/iterate-plan/SKILL.md` — same architectural pattern, design-review focus.
- Sibling skill: `~/.claude/skills/iterate-review/SKILL.md` — per-phase code review (reads the per-phase iterate-review markers this skill writes into the file).
