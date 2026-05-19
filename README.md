# trinity-skills

Three Claude Code skills that formalize the **Opus ⇄ Codex review loop** for planning and code review:

| Skill | What it does |
|---|---|
| **`create-plan`** | Scaffold a new plan markdown file in `docs/` using a canonical template (phases, iterate-review markers, HISTORICAL stubs). |
| **`iterate-plan`** | Iterate a plan between Opus (sole editor) and Codex (structured reviewer) until APPROVE. Codex never edits — it returns JSON-schema-validated findings + plan corrections + question answers; Opus folds them in. |
| **`iterate-review`** | Same loop applied to **code changes** — review a working-tree diff, a feature branch, or a PR (open or merged) with Codex; Opus folds findings into the working code. |

They're independent — install any one of them — but compose naturally:

```
                              human
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
         create-plan ──▶ iterate-plan ──▶ iterate-review
         (scaffold)      (design review)   (code review)
```

## Why this exists

Sending a plan or diff to Codex for review is high-value but tedious to do by hand: copy the markdown out, paste into a Codex prompt, copy the response back, manually decide what to incorporate, repeat. The trinity skills automate the shuttle while preserving the load-bearing invariants:

- **Opus is the sole editor.** Codex runs in a `-s read-only -a never` sandbox with `--output-schema` enforcement. It returns structured findings; Opus does every file edit.
- **No silent iteration.** After every pass the human is prompted to Continue / Converge / Abort. The skills never decide convergence themselves.
- **HISTORICAL audit trail.** Every pass appends a `[HISTORICAL]` block to the plan (or pass log) so subsequent passes see the full review history and can spot regressions or unfolded findings.

## Prerequisites

- [Claude Code](https://claude.com/claude-code) (the skills run inside it)
- [Codex CLI](https://github.com/openai/codex) — tested against `codex-cli 0.125.0+`. The skills shell out via `codex -a never exec ... --output-schema ...`.
- `git`, `bash`, and `gh` (only needed for `iterate-review --scope=pr:<n>`).

## Install

```bash
git clone https://github.com/kaileconsulting/trinity-skills.git
cd trinity-skills
./install.sh
```

`install.sh` creates symlinks from `~/.claude/skills/{create-plan,iterate-plan,iterate-review}/` into the cloned repo, so your local Claude Code sees them as installed skills and any `git pull` updates them immediately. It refuses to overwrite existing non-symlink directories (so a hand-edited skill of the same name won't be clobbered).

Restart Claude Code after installing for the skills to appear in the available-skills list.

## Quick start

Inside any Claude Code session:

```
/create-plan refactor-payments
```

walks you through plan-type selection (`initiative` or `fix`), phase metadata, and writes `docs/refactor-payments-YYYY-MM-DD.md`. Fill in TL;DR / Why / Approach, then:

```
/iterate-plan docs/refactor-payments-2026-05-19.md
```

sends the plan to Codex; Opus folds Codex's structured findings back into the file; you confirm Continue / Converge after each pass. On convergence, Opus optionally writes a handoff prompt for a fresh Sonnet session to execute the plan.

Per phase, ship commits then:

```
/iterate-review --scope=branch
```

runs the same loop against `git diff $(git merge-base HEAD main)...HEAD`. Pass log lands at `code-review-branch-<name>.md` next to your work. Other scopes:

- `--scope=working` — uncommitted working-tree changes
- `--scope=pr:123` — open or merged GitHub PR (uses `gh pr diff`)
- `--once` — single-pass review, no loop

## Directory layout

```
trinity-skills/
├── create-plan/
│   ├── SKILL.md
│   └── template.md
├── iterate-plan/
│   ├── SKILL.md
│   ├── reviewer-prompt.md
│   ├── reviewer-output.schema.json
│   ├── examples/   # synthetic Codex response fixtures
│   └── state/      # gitignored at runtime; only example.json tracked
└── iterate-review/
    ├── SKILL.md
    ├── reviewer-prompt.md
    ├── reviewer-output.schema.json
    ├── examples/   # synthetic Codex response fixtures
    └── state/      # gitignored at runtime
```

`state/` directories hold per-invocation run state (Codex response JSON, final state files). They're populated at runtime through the symlink and excluded from version control.

## How it works under the hood

Each iterate-* skill invokes Codex as a subprocess with three structural guarantees:

1. **Sandbox** — `codex -a never exec -s read-only --skip-git-repo-check` makes file writes structurally impossible from Codex's side.
2. **Output schema** — `--output-schema <reviewer-output.schema.json>` forces Codex's response into a strict JSON shape (verdict + findings + corrections + answers). Free-form prose is rejected by Codex's runtime before it reaches Opus.
3. **Patch-marker rejection** — Opus scans the response for `*** Begin Patch`, unified-diff markers, and merge-conflict markers before folding. Defense in depth against a Codex response that smuggles a patch into a description field.

This makes the editor/reviewer separation a structural property of the system, not a trust property. Even an out-of-contract response gets caught at the gateway.

## License

MIT — see [LICENSE](LICENSE).

## Contributing

Issues and PRs welcome. Two things to know:

- **Don't edit `state/`** in PRs — it's runtime artifact. Only `state/example.json` is tracked, and that's reference documentation, not test data.
- **Reviewer prompts (`reviewer-prompt.md`) and schemas (`reviewer-output.schema.json`) are load-bearing** — changing them changes how every plan / diff is reviewed going forward. Treat edits to those files as protocol changes, not refactors.
