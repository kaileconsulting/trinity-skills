# V1 — frozen single-reviewer skills

A frozen snapshot of `iterate-plan` and `iterate-review` as they shipped at commit
**`30e2a0b`**, before Axis 2 added persona lenses. Kept installable for anyone who
wants the original basic loop: **one Codex call per pass, no lens selection, no
fan-out, no merge, no loop mode.**

```bash
./install.sh --with-v1     # installs V1 alongside the current skills
```

They install as `iterate-plan-v1` and `iterate-review-v1`, so they coexist with the
current versions rather than replacing them.

## Frozen means frozen

**Do not fix bugs here.** This directory documents what V1 *was*, and its value is
that it still behaves the way it behaved. Two known consequences:

- `iterate-review-v1/examples/pass-1-response.json` and
  `pass-malformed.response.json` both carry a `$comment` key that makes them
  **schema-invalid** (the schema sets `additionalProperties: false`). The Phase 4
  audit found this and fixed it in the current skill — including renaming
  `pass-malformed.response.json`, whose name was actively misleading since the file
  is neither malformed JSON nor schema-invalid *because* of malformation. Those
  fixes are deliberately **not** applied here.
- `tools/` does not scan this directory. `check-parity.py` compares only the two
  current skills, and `check-examples.py` validates only their fixtures. Pointing
  either at V1 would report failures that are historically accurate.

If you want a V1 bug fixed, the answer is to use the current skill.

## What was changed from the snapshot, and why

Everything is byte-identical to `30e2a0b` **except** the changes required to let V1
and V2 coexist without silently corrupting each other. Nothing about the review
logic was touched.

| Change | Why |
|---|---|
| `name:` → `iterate-plan-v1` / `iterate-review-v1` | A skill's identity is its `name:` plus its installed directory. Two skills named `iterate-plan` is ambiguous. |
| `description:` rewritten | Both variants appear in the skill roster every session. The V1 descriptions state explicitly that they should not be used unless asked for by name, so a generic "review this plan" request routes to the current skill. |
| `~/.claude/skills/<skill>/…` → `…-v1/…` | The SKILL.md bodies hardcode paths to their own `reviewer-prompt.md`, schema, and state dir. Left unrewritten, V1 would have read the **multi-lens** prompt and schema — a silent cross-contamination bug. |
| State dir now `…-v1/state/` | Follows from the path rewrite. V1 and V2 keep separate pass state. |
| `/tmp/iterate-review-input-…` → `/tmp/iterate-review-v1-input-…` | Temp input files would otherwise collide mid-run. |
| Default pass log `code-review-<tag>.md` → `code-review-v1-<tag>.md` | V2 writes the same default. Without namespacing, running both in one repo silently overwrites the other's review trail. |
| `<plan>.handoff-prompt.md` → `…-v1.md` | Same collision, for `iterate-plan`'s Sonnet-handoff artefact. |
| Schema `$id` repointed at `v1/` | Accuracy only; `$id` is not resolved at runtime. |
| CLI examples and prose self-references | So the docs tell you to type `iterate-review-v1`, not `iterate-review`. |

Verified after rewriting: **no file under `v1/` references a non-`-v1` skill
directory** (except `create-plan`, which Axis 2 did not change and which both
versions legitimately share), and every path either resolves to a file present here
or is created at runtime by a `mkdir -p` in the skill itself.

`iterate-plan-v1/state/example.json` is included because it was tracked at
`30e2a0b`, and because `iterate-plan` — unlike `iterate-review` — never `mkdir`s its
state directory, so the tracked example is what makes the directory exist. That was
true of V1 as shipped and is preserved rather than fixed.

## Rolling back entirely

If you want V1 as *the* skills rather than a sidecar, the repo history is the better
route — the tag `v1.0` marks the pre-Axis-2 state:

```bash
git checkout v1.0 && ./install.sh
```

Because `install.sh` symlinks rather than copies, that switches the installed skills
with no further steps. Switching back is `git checkout main && ./install.sh`.

## Why keep this at all

The multi-lens versions fan out to 2–5 concurrent `codex exec` calls per pass, which
costs latency and tokens, and they add machinery (selection, merge, worst-of
aggregation, loop guardrails) that a simple review does not need. V1 is the smaller
tool. For a short diff where one reviewer pass is plainly enough, it is the right
one — and having it on disk means that choice does not require a git operation.
