#!/bin/bash
# orchestrator_review.sh: owner-forced ad-hoc Orchestrator review (headless claude, same guardrails as architect.sh). Started by serve.py (/api/control review_orchestrator).
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"; cd "$REPO_DIR" || exit 0
mkdir -p dispatch/cache dispatch/locks dispatch/logs
command -v claude >/dev/null 2>&1 || { echo "- orchestrator review: claude CLI not found $(date -u +%FT%TZ)" >> dispatch/status.md; exit 0; }
L=dispatch/locks/orch.pid; p=$(cat "$L" 2>/dev/null); [ -n "$p" ] && kill -0 "$p" 2>/dev/null && exit 0
echo $$ > "$L"; trap 'rm -f "$L"' EXIT
python3 dispatch/freshness.py >/dev/null 2>&1
touch dispatch/cache/orch.run; echo "- orchestrator ad-hoc review started $(date -u +%FT%TZ)" >> dispatch/status.md
perl -e 'alarm 900; exec @ARGV' claude -p "$(cat dispatch/orchestrator_prompt.md)" --model sonnet --permission-mode acceptEdits \
  --allowedTools "Read" "Write" "Edit" "Bash(gh pr list:*)" "Bash(gh pr view:*)" "Bash(gh issue view:*)" "Bash(gh issue list:*)" "Bash(bash dispatch/arch_act.sh:*)" "Bash(cat:*)" "Bash(ls:*)" "Bash(grep:*)" "Bash(sed:*)" "Bash(date:*)" \
  --disallowedTools "Bash(gh pr merge:*)" "Bash(gh issue close:*)" "Bash(gh pr close:*)" "Bash(git push:*)" "Bash(git checkout:*)" "Bash(git reset:*)" \
  > dispatch/logs/orchestrator_review.log 2>&1
RC=$?
python3 dispatch/freshness.py >/dev/null 2>&1
echo "- orchestrator ad-hoc review finished (exit $RC) $(date -u +%FT%TZ)" >> dispatch/status.md
touch dispatch/cache/orch.run
exit 0
