#!/usr/bin/env bash
# Symlink each skill in this repo into ~/.claude/skills/ so Claude Code
# picks them up. Re-run after `git pull` is unnecessary — symlinks track
# the repo automatically.
#
# Override the destination with CLAUDE_SKILLS_DIR=/some/path ./install.sh
# Refuses to overwrite an existing non-symlink directory at the target.

set -euo pipefail

SKILLS_DIR="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS=(create-plan iterate-plan iterate-review)

mkdir -p "$SKILLS_DIR"

echo "Installing trinity skills:"
echo "  repo:     $REPO_DIR"
echo "  skills/:  $SKILLS_DIR"
echo

for s in "${SKILLS[@]}"; do
  target="$SKILLS_DIR/$s"
  source="$REPO_DIR/$s"

  if [ ! -d "$source" ]; then
    echo "  SKIP  $s — source directory not found at $source"
    continue
  fi

  if [ -L "$target" ]; then
    existing="$(readlink "$target")"
    if [ "$existing" = "$source" ]; then
      echo "  OK    $s — already linked to this repo"
      continue
    fi
    echo "  RELINK $s — was pointing at $existing"
    rm "$target"
  elif [ -e "$target" ]; then
    echo "  ERROR $s — $target exists and is not a symlink."
    echo "        Move or remove it, then re-run: rm -rf \"$target\""
    exit 1
  fi

  ln -s "$source" "$target"
  echo "  LINK  $s -> $source"
done

echo
echo "Done. Restart Claude Code (or open a new session) to pick up the skills."
echo "Verify install: ls -la \"$SKILLS_DIR\""
