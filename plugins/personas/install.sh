#!/usr/bin/env bash
# install.sh — install the totebag `personas` harness into ~/.claude.
#
# Installs:
#   1. the personas skill  -> ~/.claude/skills/personas/SKILL.md
#   2. (optional) generates persona subagents from your totebag workspaces -> ~/.claude/agents/
#      (and each persona's private skills -> ~/.claude/personas/<persona>/)
#
# Safe and idempotent. Does NOT edit ~/.claude/settings.json.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_DIR="${CLAUDE_HOME:-$HOME/.claude}"
SKILL_DIR="$CLAUDE_DIR/skills/personas"

mkdir -p "$SKILL_DIR"
cp "$HERE/SKILL.md" "$SKILL_DIR/SKILL.md"
echo "OK  installed skill: $SKILL_DIR/SKILL.md"

if command -v totebag >/dev/null 2>&1; then
  echo "Syncing persona subagents from totebag workspaces..."
  python3 "$HERE/generate_agents.py" || echo "WARN generator failed (set \$TOTEBAG_ROOT and add a charter, then re-run generate_agents.py)"
else
  echo "WARN totebag not on PATH — install it, then run: python3 $HERE/generate_agents.py"
fi

echo "Done."
