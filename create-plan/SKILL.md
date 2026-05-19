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

### Step 3 — For initiatives only: collect phase metadata

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

### Step 4 — Resolve target file path

1. Locate the project root: run `git rev-parse --show-toplevel` via Bash. If that fails (not a git repo), fall back to the current working directory and warn the user.
2. Slugify the initiative name: lowercase, replace whitespace + non-alphanumerics with `-`, collapse multiple `-` into one, trim leading/trailing `-`.
3. **Append today's creation date as a `-YYYY-MM-DD` suffix** to the slug, then append `.md`. Use the date from your system context (e.g., the `# currentDate` block in the conversation); if unavailable, run `date -u +%Y-%m-%d` via Bash. Example: initiative "ORCID PI Unification" + creation date 2026-05-07 → filename `orcid-pi-unification-2026-05-07.md`.
4. Target path: `<project-root>/docs/<slug>-<YYYY-MM-DD>.md`.
5. If `docs/` doesn't exist under the project root, create it.
6. **If the target file already exists, refuse and stop.** Tell the user the path and ask whether they want to (a) pick a different name, (b) edit the existing file directly, or (c) explicitly delete and recreate. Don't auto-overwrite.

**Why the date suffix.** The dated filename makes the archived `docs/archive/` folder self-documenting — reviewers can see at a glance when each plan was drafted, which is useful for time-correlating plans with related ship commits, milestones-index entries (if the project tracks one), changelog updates, customer-feedback transcripts, or other external context. Reference / brainstorm / audit docs (non-plan documents in `docs/`) stay dateless; the suffix applies specifically to plans produced by this skill.

### Step 5 — Generate the plan file

Read the template at `~/.claude/skills/create-plan/template.md`. Apply these transforms before writing to the target path:

1. **Strip the top template-header HTML comment block** — the legend explaining REQUIRED / RECOMMENDED / TOOLING-RESERVED is authoring guidance for the template itself, not for individual plans. The scaffolded plan should start cleanly at the H1 title.

2. **Replace the H1 title.** The template has `# <Initiative Name> — Plan`; substitute the user's actual name: `# <ActualName> — Plan`.

3. **Keep all inline `<!-- ... -->` guidance comments under section headers.** These are intentional authoring hints. The template comment header (which you stripped in transform #1) instructs the author to remove them before committing — they're scaffolding for the author, not noise to delete here.

4. **Prune the unused phasing variant.**
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

5. **Leave the rest untouched** — Acceptance criteria, Risks, Open questions, Out of scope, Closeout, References, and the TOOLING-RESERVED tail (`## Review checkpoints`, `## Pre-flight review pass`, `## Codex review pass N`) all stay as the template provides them.

Write the result to the target path via the Write tool.

### Step 6 — Print next-step guidance

Tell the user:

1. The absolute path of the file you wrote.
2. The REQUIRED sections they need to fill in: TL;DR, Why/Context, Who/Use cases, Approach, Acceptance criteria, Risks, Open questions, Out of scope, **Closeout**, References. (For multi-phase plans: also fill in per-phase deliverables, acceptance, and time estimates.)
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

- `template.md` — the canonical plan template (read by step 5).
- Sibling skill: `~/.claude/skills/iterate-plan/SKILL.md` — same architectural pattern, design-review focus.
- Sibling skill: `~/.claude/skills/iterate-review/SKILL.md` — per-phase code review (reads the per-phase iterate-review markers this skill writes into the file).
