#!/bin/bash
# Story: #254 -- classify agent failures, back off restarts, record exits. Run: bash dispatch/tests/test_failure_classification.sh (throwaway dirs).
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/../lib.sh" || { echo "FAIL: cannot source dispatch/lib.sh"; exit 1; }
FAILS=0
check() { if [ "$2" = "$3" ]; then echo "ok   - $1"; else echo "FAIL - $1 (want '$3', got '$2')"; FAILS=$((FAILS+1)); fi; }
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
REPO_DIR="$T/disp"; mkdir -p "$REPO_DIR/dispatch"
check "config lock race is transient" "$(classify_failure "error: could not lock config file .git/config: File exists")" transient
check "network is transient" "$(classify_failure "Could not resolve host: github.com")" transient
check "branch held is permanent" "$(classify_failure "branch 12-x held by another dirty worktree")" permanent
check "already checked out is permanent" "$(classify_failure "fatal: '12-x' is already checked out at '/p/wt'")" permanent
check "usage limit is transient (the loop pauses and resumes)" "$(classify_failure "You've hit your session limit")" transient
check "unknown defaults to transient" "$(classify_failure "something odd")" transient
record_exit 77 1 "branch held by x"
check "exit record 1" "$(sed 's/ ts=.*//' "$REPO_DIR/dispatch/exits/77")" "code=1 class=permanent attempts=1 reason=branch held by x"
record_exit 77 1 "branch held by x"
check "attempts increment" "$(grep -o 'attempts=[0-9]*' "$REPO_DIR/dispatch/exits/77")" "attempts=2"
check "backoff 1" "$(retry_delay 1)" 30
check "backoff 2" "$(retry_delay 2)" 60
check "backoff 3" "$(retry_delay 3)" 120
now=$(date +%s)
printf 'code=1 class=transient attempts=1 reason=x ts=%s next=%s\n' "$now" "$((now+600))" > "$REPO_DIR/dispatch/exits/a"
backoff_due a; check "backoff pending -> not due" "$?" 1
printf 'code=1 class=transient attempts=1 reason=x ts=%s next=%s\n' "$now" "$((now-1))" > "$REPO_DIR/dispatch/exits/a"
backoff_due a; check "backoff elapsed -> due" "$?" 0
backoff_due nosuch; check "no record -> due" "$?" 0
is_permanent 77; check "permanent record detected" "$?" 0
is_permanent a; check "transient record not permanent" "$?" 1
rm -rf "$REPO_DIR/dispatch/exits" "$REPO_DIR/dispatch/status.md"
record_exit 1 1 "Could not resolve host"; record_exit 2 1 "branch held by x"; record_exit 3 1 "Could not resolve host"
failure_summary
check "summary line" "$(grep -o 'FAILURES.*' "$REPO_DIR/dispatch/status.md" | sed 's/^FAILURES [0-9-]*: //')" "transient=2 permanent=1"
[ "$FAILS" -eq 0 ] && echo "ALL PASSED" || { echo "$FAILS FAILED"; exit 1; }
