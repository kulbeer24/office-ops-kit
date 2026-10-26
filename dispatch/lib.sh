#!/bin/bash
# Shared dispatcher helpers (ported from PR #400, issue #254, adapted to the live run_batch.sh reaper). Source it; needs REPO_DIR for record_exit / failure_summary.
# classify_failure <reason> -> "transient" (restart with backoff) or "permanent" (park, never restart).
# Branch conflicts and setup failures are permanent. Unknown reasons are transient; the 3-restart cap in run_batch.sh still bounds them.
# Usage limits are NOT permanent here: run_batch.sh pauses on LIMIT_HIT and resumes by itself.
classify_failure() {
  case "$1" in
    *"already checked out"*|*"already used by worktree"*|*"held by"*|*"cannot create"*|*"setup failed"*) echo permanent ;;
    *) echo transient ;;
  esac
}
# retry_delay <attempt> -> seconds to wait before the next restart (30, 60, 120, ...).
retry_delay() { echo $((30 * (1 << ($1 - 1)))); }
# record_exit <agent> <exit-code> <reason>: writes dispatch/exits/<agent> (code, class, attempts, reason, next-retry), bumping attempts.
record_exit() {
  local f="$REPO_DIR/dispatch/exits/$1" cls n=1 now; mkdir -p "$REPO_DIR/dispatch/exits"
  [ -f "$f" ] && n=$(( $(grep -o 'attempts=[0-9]*' "$f" | cut -d= -f2) + 1 ))
  cls=$(classify_failure "$3"); now=$(date +%s)
  echo "code=$2 class=$cls attempts=$n reason=$3 ts=$now next=$((now + $(retry_delay "$n")))" > "$f"
}
# backoff_due <agent>: rc 0 when no backoff is pending (no record, or its next-retry time has passed).
backoff_due() {
  local f="$REPO_DIR/dispatch/exits/$1"; [ -f "$f" ] || return 0
  [ "$(date +%s)" -ge "$(grep -o 'next=[0-9]*' "$f" | cut -d= -f2)" ]
}
# is_permanent <agent>: rc 0 when the last recorded failure is permanent.
is_permanent() { grep -q 'class=permanent' "$REPO_DIR/dispatch/exits/$1" 2>/dev/null; }
# failure_summary: one status.md line counting recorded failures by class.
failure_summary() {
  local t=0 p=0 f
  for f in "$REPO_DIR"/dispatch/exits/*; do
    [ -f "$f" ] || continue
    case "$f" in *" "[0-9]) continue ;; esac
    if grep -q 'class=permanent' "$f"; then p=$((p+1)); else t=$((t+1)); fi
  done
  echo "- FAILURES $(date +%F): transient=$t permanent=$p" >> "$REPO_DIR/dispatch/status.md"
}
