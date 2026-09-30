# 06 — Lockfile exclusion (`generated` + `docs`), disclosed

Built from a real review: ResearchLogix_v2's Dependabot cleanup
(`docs/reviews/code-review-branch-chore-dependabot-cleanup-2026-09-10.md`),
which left its lockfiles out of the reviewed diff by hand, with the audit
written into the intent ("every npm `resolved` → registry.npmjs.org; every
composer `dist.url` → api.github.com zipball"). This scenario is the same
review done through the runner (docs/review-diff-exclusions-2026-09-29.md
§2). Unlike scenarios 01–05 it is **run, not only read**:
`tools/check-runners.py` feeds these files to `apply_exclusions()` and to
lens selection and compares the results byte for byte.

## Inputs

| File | Role |
|---|---|
| `input.diff` | real `git diff` output: `frontend/package.json`, `frontend/package-lock.json`, `composer.lock`, `docs/development-history.md` |
| `intent.txt` | the intent, with one `=== EXCLUDED SUMMARY ===` entry per lockfile |
| `exclude-args.txt` | the editor's flags: `--exclude generated:**/*.lock`, `--exclude generated:frontend/package-lock.json`, `--exclude docs:docs/**` |
| `expected-exclusion.json.golden` | the summary's `excluded` / `diff_lines` fields, plus `warnings` (named `.golden` so `check-examples.py` doesn't read it as a reviewer response) |
| `expected-reviewed.diff` | what the lenses see under `=== DIFF ===` |

## Expected result

- **Excluded:** `composer.lock` (generated, 17 lines), `frontend/package-lock.json`
  (generated, 25 lines), `docs/development-history.md` (docs, 12 lines). Each
  `generated` entry carries its audit property, copied from the intent.
- **Reviewed:** `frontend/package.json` only (13 of 67 lines). It is production
  under the §3 heuristic and no class names it, so it stays in review.
- **Lens selection reads the original diff:** `security` is selected because
  `**/package-lock.json` matches the excluded lockfile (and a lockfile URL
  matches a content regex). Selecting on the reviewed diff would drop it and
  leave only `senior-dev`, which is the failure §3 exists to prevent.

## Expected pass header

```markdown
**Scope:** branch (excluded: generated composer.lock 17 lines — every composer `dist.url` is an https://api.github.com/repos/<owner>/<repo>/zipball/<sha> URL for the named package; only guzzlehttp/guzzle changed; docs docs/development-history.md 12 lines; generated frontend/package-lock.json 25 lines — every npm `resolved` URL points at https://registry.npmjs.org/; versions match the package.json ranges; no new packages) · **Diff size:** 67 lines · … · **Lenses:** security, senior-dev
```

Copied from the summary's `excluded` array, in its order, never written
from memory. A `generated` entry shows its audit property after ` — ` so
the human sees, in the header itself, what the editor claims to have
checked instead of reading the file.

## What a wrong result looks like

| Wrong output | The misreading that produces it |
|---|---|
| `frontend/package.json` excluded | a glob treated as "anything near a lockfile", or `docs`/`generated` rules applied to a path no spec names |
| Lenses `senior-dev` only | selection run on the reviewed diff instead of the original (§3) |
| Refused: "`generated:**/*.lock` matches no path" | the leading `**/` not matching zero segments, so root-level `composer.lock` is missed |
| A lockfile excluded with no audit shown in the header | the Scope line written from memory instead of copied from `excluded[].audit` |
| The run proceeds after deleting one audit entry | the audit presence check skipped; it must refuse before any Codex call |
