#!/bin/bash
# One agent for one job, in its own git worktree. Names: <issue> = dev (opens a PR), fix-<issue> = fix an existing PR branch, qa-<PR> = adversarial QA of a PR.
# Started by run_batch.sh (launch_agent). Never merges or closes anything. Writes dispatch/done/<name> when finished (the loop reports it).
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export GIT_TERMINAL_PROMPT=0 GIT_EDITOR=true GIT_MERGE_AUTOEDIT=no
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.hooksPath GIT_CONFIG_VALUE_0=/dev/null   # repo git hooks can hang a worktree add; agents skip them
N="$1"; REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"; cd "$REPO_DIR" || exit 1
source "$REPO_DIR/dispatch/lib_kit.sh"; HEADLESS="${HEADLESS:-1}"
R=__REPO__; SLUG=__SLUG__; LOG="$REPO_DIR/dispatch/logs/$N.log"; DONE="$REPO_DIR/dispatch/done/$N"
TEST_CMD="$(ocfg test_cmd 'run the project test suite described in CLAUDE.md')"; MODEL="$(ocfg model sonnet)"
mkdir -p dispatch/logs dispatch/done dispatch/locks
# free_branch BR KEEP: git allows a branch in only one worktree. Remove any OTHER worktree holding BR if idle, clean and pushed (QA/fix worktrees are disposable).
free_branch() {
  local br="$1" keep="$2" p sfx
  git worktree list --porcelain 2>/dev/null | awk -v b="refs/heads/$br" '/^worktree /{w=substr($0,10)} $0=="branch " b {print w}' | while read -r p; do
    [ "$p" = "$keep" ] && continue
    sfx=$(basename "$p" | sed "s/^$SLUG-wt-//")
    if pgrep -f "AGENT-ID-$sfx\\." >/dev/null || pgrep -f "AGENT-ID-fix-$sfx\\." >/dev/null; then echo "$(date -u +%FT%TZ) $p still has a live agent; not freeing $br" >> "$LOG"; continue; fi
    if ! git -C "$p" merge-base --is-ancestor HEAD "origin/$br" 2>/dev/null; then git -C "$p" branch -f "salvage/$br-$(date +%s)" HEAD 2>>"$LOG"; fi   # never lose unpushed commits
    git worktree remove --force "$p" 2>>"$LOG"
  done
}
# acquire_lock KEY: one agent at a time per PR (dev/fix/QA share a worktree per PR). Waits up to ~2.5 min, then exits 3 and the loop retries.
acquire_lock() {
  local L="$REPO_DIR/dispatch/locks/$1.lock" t=0 op
  while ! mkdir "$L" 2>/dev/null; do
    op=$(cat "$L/pid" 2>/dev/null)
    if [ -n "$op" ] && ! kill -0 "$op" 2>/dev/null; then rm -rf "$L"; continue; fi
    t=$((t+1)); [ $t -gt 10 ] && { echo "$(date -u +%FT%TZ) busy: another agent holds PR $1" >> "$LOG"; exit 3; }
    sleep 15
  done
  echo $$ > "$L/pid"; trap 'rm -rf "$L"' EXIT
}
# make_worktree WT BR [DETACH]: add a worktree for BR from origin, retrying (parallel starts fight over .git/config.lock)
make_worktree() {
  local _try
  for _try in 1 2 3 4; do
    git worktree add "$1" -B "$2" "origin/$2" -q 2>>"$LOG" && return 0; [ -d "$1" ] && return 0; sleep $((RANDOM % 6 + 3))
  done; return 1
}
HYGIENE="GIT HYGIENE: stage only explicit paths (git add <path>); never git add -A or git add . or git commit -a. Before every commit run git status and git diff --cached --name-only and unstage anything not part of this task, especially cloud-sync duplicates whose names end in ' 2' or ' 3'. Never force-push. Never merge, close issues, or open PRs unless told below."
# Watcher: when the done file appears, report it and end this agent.
watch_done() {
  ( while [ ! -f "$DONE" ]; do sleep 10; done
    sleep 5; R2=$(cat "$DONE")
    echo "- #$N DONE: $R2" >> "$REPO_DIR/dispatch/status.md"; echo "$N|$(date -u +%FT%TZ)" >> "$REPO_DIR/dispatch/metrics.ends"
    notify_user "__PROJECT__ agent" "#$N: $R2"
    pkill -f "AGENT-ID-$N" ) &
}
CLAUDE_FLAGS=(--model "$MODEL" --permission-mode acceptEdits --allowedTools "Bash,Read,Write,Edit,Glob,Grep" --disallowedTools "Bash(gh pr merge:*),Bash(gh issue close:*),Bash(git push --force:*),Bash(git push -f:*)")
git fetch origin -q
BASE="$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's#^origin/##')"; BASE="${BASE:-main}"

if [[ "$N" == fix-* ]]; then   # ---- FIX MODE: dispatch/fixes/<issue>.txt = line 1 branch, rest instructions
  FID="${N#fix-}"; F="$REPO_DIR/dispatch/fixes/$FID.txt"; BR=$(head -1 "$F"); INSTR=$(tail -n +2 "$F"); WT="$REPO_DIR/../$SLUG-wt-pr-$FID"
  acquire_lock "$FID"; free_branch "$BR" "$WT"
  if [ -d "$WT" ]; then git -C "$WT" checkout "$BR" -q 2>/dev/null; git -C "$WT" pull --ff-only -q origin "$BR" 2>/dev/null; else make_worktree "$WT" "$BR"; fi
  [ -d "$WT" ] || { echo "BLOCKED: worktree add failed for $BR" > "$DONE"; exit 1; }
  cd "$WT" || exit 1
  PROMPT="AGENT-ID-$N. You are a dev agent fixing an EXISTING open PR for issue #$FID in $R, on branch $BR (checked out). Read CLAUDE.md first and follow it. $HYGIENE $INSTR STRICT TDD: write the failing tests first, run them, confirm they FAIL, commit them alone as 'test: ... (#$FID)'; then implement, make them pass, commit as 'fix: ... (#$FID)'. Run the full suite ($TEST_CMD). Then git push origin HEAD:$BR (normal push). Do NOT open a new PR, merge, or close anything. Finish by running exactly: echo 'FIXED: pushed to $BR' > $DONE   (or 'BLOCKED: <reason>'), then stop."
  watch_done; run_claude "$PROMPT" "${CLAUDE_FLAGS[@]}"; exit
fi
if [[ "$N" == qa-* ]]; then   # ---- QA MODE: adds failing tests only, never edits production code
  PRN="${N#qa-}"; BR=$(gh pr view "$PRN" --repo $R --json headRefName -q .headRefName); ISS=$(echo "$BR" | grep -oE "^[0-9]+"); ISS=${ISS:-$PRN}; WT="$REPO_DIR/../$SLUG-wt-pr-$ISS"
  acquire_lock "$ISS"; free_branch "$BR" "$WT"
  if [ -d "$WT" ]; then git -C "$WT" checkout "$BR" -q 2>/dev/null; git -C "$WT" pull --ff-only -q origin "$BR" 2>/dev/null; else make_worktree "$WT" "$BR" || git worktree add "$WT" --detach "origin/$BR" -q; fi
  [ -d "$WT" ] || { echo "BLOCKED: worktree add failed for $BR" > "$DONE"; exit 1; }
  cd "$WT" || exit 1
  PROMPT="AGENT-ID-$N. You are an adversarial QA agent for open PR #$PRN in $R (branch $BR, checked out). Read CLAUDE.md. $HYGIENE Run: gh pr view $PRN --json body,files and gh pr diff $PRN. Your job: find behaviour the PR author's own tests missed. Think like a hostile tester with real user input: false positives, false negatives, negation, past vs future, questions, empty/odd input, boundary values, date edges, concurrency and retry paths, privacy leaks in logs. Write 8-20 concrete adversarial test cases in a NEW test file named QA_PR${PRN}_Tests (in the project's test language and test folder), run them ($TEST_CMD). NEVER modify production code or the PR's existing tests. If some of your tests FAIL, those are findings: commit ONLY the new test file as 'test: adversarial QA cases (#$ISS)' and git push origin HEAD:$BR (normal push). If everything passes, do not push anything. Never merge, close, or open PRs. Finish by running exactly: echo 'QA: <n> cases, <k> findings: <one line each>' > $DONE   (or 'BLOCKED: <reason>'), then stop."
  watch_done; run_claude "$PROMPT" "${CLAUDE_FLAGS[@]}"; exit
fi
# ---- DEV MODE: issue number -> branch <n>-<slug>, strict TDD, opens a PR
TITLE=$(gh issue view "$N" --repo $R --json title -q .title)
SL=$(echo "$TITLE" | tr 'A-Z' 'a-z' | tr -cs 'a-z0-9' '-' | cut -c1-30 | sed 's/-$//'); BR="$N-$SL"; WT="$REPO_DIR/../$SLUG-wt-$N"
git worktree add "$WT" -b "$BR" "origin/$BASE" -q 2>/dev/null || git worktree add "$WT" "$BR" -q 2>/dev/null
[ -d "$WT" ] || { echo "BLOCKED: worktree add failed for $BR" > "$DONE"; exit 1; }
cd "$WT" || exit 1
PROMPT="AGENT-ID-$N. You are a dev agent for issue #$N in $R. Read CLAUDE.md first and follow it exactly. $HYGIENE Run: gh issue view $N --comments (comments may add scheduling and spec updates; the latest orchestrator comment wins). Work only on this issue on branch $BR (checked out). STRICT TDD, enforced: (1) write the tests only, run them, and confirm they FAIL; (2) git commit them alone as 'test: ... (#$N)' and paste the failing output summary in the PR body; (3) only then write the implementation, make them pass, commit as 'feat: ... (#$N)'. Never write tests and implementation in one pass. Test with: $TEST_CMD. When green: commit (Conventional Commit, (#$N)), git push -u origin $BR, gh pr create with body 'Closes #$N' plus summary and deliberate gaps. NEVER merge or close anything. If you are blocked or need a decision, run exactly: echo 'BLOCKED: <reason>' > $DONE and stop. When the PR exists, run exactly: echo 'PR: <url>' > $DONE then stop."
watch_done; run_claude "$PROMPT" "${CLAUDE_FLAGS[@]}"
exit
