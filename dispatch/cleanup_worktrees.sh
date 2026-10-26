#!/bin/bash
# Removes finished agent worktrees and cloned simulators. Safe by design: skips live agents, recently used worktrees,
# worktrees with tracked changes, and any worktree whose HEAD is not already on origin. Never touches the main repo
# folder or a *-release worktree. Run by the dispatch loop about every 2 hours.
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export GIT_TERMINAL_PROMPT=0 GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.hooksPath GIT_CONFIG_VALUE_0=/dev/null
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"; cd "$REPO_DIR" || exit 1
git fetch origin -q 2>/dev/null
live() { pgrep -f "AGENT-ID-(fix-)?$1\." >/dev/null || pgrep -f "agent\.sh (fix-)?$1( |\$)" >/dev/null; }
git worktree list --porcelain | awk '/^worktree /{print $2}' | while read -r WT; do
  case "$WT" in */__SLUG__-wt-*) ;; *) continue ;; esac
  id="${WT##*-wt-}"
  live "$id" && continue
  # QA/fix agents are tagged qa-<PR>/fix-<issue> but work in wt-pr-<issue>: never remove a pr-* worktree while any QA or fix agent is running (a QA run was killed mid-way on 25 Oct)
  case "$id" in pr-*) pgrep -f "AGENT-ID-(qa|fix)-" >/dev/null && continue ;; esac
  [ -n "$(find "$WT" -maxdepth 0 -mmin -15 2>/dev/null)" ] && continue
  git -C "$WT" diff --quiet 2>/dev/null && git -C "$WT" diff --cached --quiet 2>/dev/null || continue
  git -C "$WT" branch -r --contains HEAD 2>/dev/null | grep -q . || continue
  git worktree remove --force "$WT" 2>/dev/null && echo "- cleanup: removed worktree $(basename "$WT")" >> dispatch/status.md
done
git worktree prune 2>/dev/null
exit 0
