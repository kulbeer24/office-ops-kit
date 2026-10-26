#!/bin/bash
# architect.sh: headless architect review on this Mac, at most every 20 min, only when dispatch/changed.sh says something changed.
# It reviews, comments and queues fixes; it can NOT merge (merge/close/push are disallowed). Approved PRs are marked "ready to merge" in owner_hold.txt and alerted.
# Usage: architect.sh [force]   (force skips the 20-minute spacing and the change check)
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"; cd "$REPO_DIR" || exit 0
mkdir -p dispatch/cache dispatch/locks dispatch/logs
[ -f dispatch/PAUSED ] && [ "$1" != force ] && exit 0
[ -f dispatch/LIMIT_HIT ] && exit 0
command -v claude >/dev/null 2>&1 || exit 0
ST=dispatch/cache/architect.run
[ "$1" != force ] && [ -n "$(find "$ST" -mmin -20 2>/dev/null)" ] && exit 0
L=dispatch/locks/architect.pid; p=$(cat "$L" 2>/dev/null); [ -n "$p" ] && kill -0 "$p" 2>/dev/null && exit 0
echo $$ > "$L"; trap 'rm -f "$L"' EXIT
if [ "$1" != force ]; then bash dispatch/changed.sh 2>/dev/null | grep -q '^UNCHANGED' && { touch "$ST"; exit 0; }; fi
touch "$ST"; echo "- architect review started $(date -u +%FT%TZ)" >> dispatch/status.md
PR="$(cat dispatch/architect_prompt.md)"; [ "$1" = force ] && PR="OWNER-FORCED REVIEW from a dashboard button: ignore the UNCHANGED gate in STEP 0 and do the full review now, even if nothing looks changed. Also read dispatch/cache/freshness.json. End with a one-line summary of what you checked, even if nothing needed doing. $PR"
perl -e 'alarm 1500; exec @ARGV' claude -p "$PR" --model sonnet --permission-mode acceptEdits \
  --allowedTools "Read" "Write" "Edit" "Bash(gh pr list:*)" "Bash(gh pr view:*)" "Bash(gh pr diff:*)" "Bash(gh pr comment:*)" "Bash(gh issue view:*)" "Bash(gh issue list:*)" "Bash(gh api:*)" "Bash(git fetch:*)" "Bash(git diff:*)" "Bash(git log:*)" "Bash(git show:*)" "Bash(bash dispatch/changed.sh:*)" "Bash(bash dispatch/arch_act.sh:*)" "Bash(cat:*)" "Bash(ls:*)" "Bash(grep:*)" "Bash(sed:*)" "Bash(date:*)" \
  --disallowedTools "Bash(gh pr merge:*)" "Bash(gh issue close:*)" "Bash(gh pr close:*)" "Bash(git push:*)" "Bash(git checkout:*)" "Bash(git reset:*)" \
  > dispatch/logs/architect.log 2>&1
RC=$?
[ "$RC" = 0 ] && bash dispatch/changed.sh ack >/dev/null 2>&1
echo "- architect review finished (exit $RC) $(date -u +%FT%TZ)" >> dispatch/status.md
exit 0
