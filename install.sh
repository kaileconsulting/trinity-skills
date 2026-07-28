#!/usr/bin/env bash
# Symlink each skill in this repo into ~/.claude/skills/ so Claude Code
# picks them up. Re-run after `git pull` is unnecessary — symlinks track
# the repo automatically.
#
# Usage:
#   ./install.sh              # current (multi-lens) skills
#   ./install.sh --with-v1    # also install the frozen V1 single-reviewer skills
#   ./install.sh --help
#
# Override the destination with CLAUDE_SKILLS_DIR=/some/path ./install.sh
# Refuses to overwrite an existing non-symlink directory at the target.
#
# NOTE: symlinks mean the installed skills track your checked-out branch. Moving
# the repo to a branch without these skills changes the installed behaviour with
# no warning.

set -euo pipefail

SKILLS_DIR="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Repo-relative source paths; the installed name is each path's basename.
SKILLS=(create-plan iterate-plan iterate-review)
V1_SKILLS=(v1/iterate-plan-v1 v1/iterate-review-v1)

WITH_V1=0
for arg in "$@"; do
  case "$arg" in
    --with-v1)
      WITH_V1=1
      ;;
    -h|--help)
      sed -n '2,17p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      echo "Try: ./install.sh --help" >&2
      exit 2
      ;;
  esac
done

if [ "$WITH_V1" -eq 1 ]; then
  SKILLS+=("${V1_SKILLS[@]}")
fi

mkdir -p "$SKILLS_DIR"

echo "Installing trinity skills:"
echo "  repo:     $REPO_DIR"
echo "  skills/:  $SKILLS_DIR"
if [ "$WITH_V1" -eq 1 ]; then
  echo "  v1:       included (--with-v1)"
else
  echo "  v1:       skipped — pass --with-v1 to install the frozen V1 skills"
fi
echo

for rel in "${SKILLS[@]}"; do
  name="$(basename "$rel")"
  target="$SKILLS_DIR/$name"
  source="$REPO_DIR/$rel"

  if [ ! -d "$source" ]; then
    echo "  SKIP  $name — source directory not found at $source"
    continue
  fi

  if [ -L "$target" ]; then
    existing="$(readlink "$target")"
    if [ "$existing" = "$source" ]; then
      echo "  OK    $name — already linked to this repo"
      continue
    fi
    echo "  RELINK $name — was pointing at $existing"
    rm "$target"
  elif [ -e "$target" ]; then
    echo "  ERROR $name — $target exists and is not a symlink."
    echo "        Move or remove it, then re-run: rm -rf \"$target\""
    exit 1
  fi

  ln -s "$source" "$target"
  echo "  LINK  $name -> $source"
done

echo
echo "Done. Restart Claude Code (or open a new session) to pick up the skills."
echo "Verify install: ls -la \"$SKILLS_DIR\""
if [ "$WITH_V1" -eq 1 ]; then
  echo
  echo "V1 installed alongside V2. Both appear in the skill roster every session;"
  echo "the V1 descriptions are written to trigger only when asked for by name."
  echo "To remove them later: rm \"$SKILLS_DIR\"/iterate-{plan,review}-v1"
fi
