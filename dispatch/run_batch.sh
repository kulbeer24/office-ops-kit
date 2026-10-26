#!/bin/bash
# Launched automatically by launchd when dispatch/batch.txt changes (see install.sh).
# Opens one Terminal window per NEW issue (max 3) running dispatch/agent.sh.
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"; cd "$REPO_DIR" || exit 1
mkdir -p dispatch/started dispatch/done dispatch/logs dispatch/exits
source "$REPO_DIR/dispatch/lib.sh"; source "$REPO_DIR/dispatch/lib_kit.sh"   # classify_failure, retry_delay, record_exit (issue #254)
"$REPO_DIR/dispatch/inbox.sh"
"$REPO_DIR/dispatch/notify.sh"
python3 "$REPO_DIR/dispatch/digest.py" >/dev/null 2>&1
python3 "$REPO_DIR/dispatch/autoreview.py" >> dispatch/cache/metrics.log 2>&1   # no-AI: queue QA re-check as soon as a fix finishes
# Requeue requests: the Cowork orchestrator may not delete files (it would stop and ask for permission), so it creates dispatch/requeue/<name>
# and this script (your Mac, no prompt) clears that agent's started/done markers and the request so the agent runs again.
mkdir -p dispatch/requeue
for Q in dispatch/requeue/*; do
  [ -e "$Q" ] || continue; n=$(basename "$Q")
  rm -f "dispatch/started/$n" "dispatch/done/$n" "dispatch/retries/$n" "dispatch/retries/$n.gaveup" "dispatch/exits/$n" "$Q"
  echo "- #$n REQUEUED by orchestrator $(date -u +%FT%TZ)" >> dispatch/status.md
done
# PAUSED: if dispatch/PAUSED exists no agent is started or restarted (running agents finish). Remove the file to resume.
# Timed pause: dispatch/pause_at holds YYYYMMDDHHMM (Mac local time). Once that time passes the PAUSED flag is created and the file removed. No tokens used.
if [ -f dispatch/pause_at ] && [ "$(date +%Y%m%d%H%M)" -ge "$(tr -cd '0-9' < dispatch/pause_at)" ]; then touch dispatch/PAUSED; rm -f dispatch/pause_at; echo "- paused automatically at the scheduled time $(date -u +%FT%TZ)" >> dispatch/status.md; fi
# STOPALL: owner (or the architect) drops dispatch/STOPALL -> pause everything and end every running agent. They restart after the pause is lifted (the restart is not counted).
if [ -f dispatch/STOPALL ]; then
  touch dispatch/PAUSED; rm -f dispatch/STOPALL
  for S in dispatch/started/*; do
    [ -e "$S" ] || continue; n=$(basename "$S"); [ -f "dispatch/done/$n" ] && continue
    c=$(cat "dispatch/retries/$n" 2>/dev/null || echo 0); [ "$c" -gt 0 ] && echo $((c-1)) > "dispatch/retries/$n"
  done
  pkill -CONT -f "AGENT-ID-" 2>/dev/null; pkill -TERM -f "AGENT-ID-" 2>/dev/null
  echo "- dev STOPPED (all running agents ended, paused) $(date -u +%FT%TZ); they restart when PAUSED is removed" >> dispatch/status.md
fi
# run_once hook: drop dispatch/run_once.sh and the next pass runs it once on the Mac (output -> dispatch/logs/run_once.out), then deletes it. Keep it short.
if [ -f dispatch/run_once.sh ]; then ( bash dispatch/run_once.sh > dispatch/logs/run_once.out 2>&1 ); rm -f dispatch/run_once.sh; fi
PAUSED=0; [ -f dispatch/PAUSED ] && PAUSED=1
# USAGE LIMIT: if the newest agent terminal log (written in the last 30 min) shows "You've hit your ... limit", pause all launches and restarts.
# After 30 minutes the flag expires so one probe agent can try again (the limit may have reset or been topped up).
if [ -f dispatch/LIMIT_HIT ]; then
  if find dispatch/LIMIT_HIT -mmin +30 | grep -q .; then rm -f dispatch/LIMIT_HIT; else PAUSED=1; fi
fi
if [ ! -f dispatch/LIMIT_HIT ]; then
  MSG=""
  for NEWEST in $(ls -t dispatch/logs/*.term.log 2>/dev/null | head -3); do
    [ -n "$(find "$NEWEST" -mmin -30)" ] || continue
    # strip terminal colour/cursor codes first, then keep only the readable sentence ("You've hit your session limit  resets 3:20pm (...)")
    MSG=$(tail -c 8000 "$NEWEST" | perl -pe 's/\e\[[0-9;?]*[ -\/]*[@-~]//g; s/\e\][^\a]*\a//g' | LC_ALL=C tr -cd '[:print:]\n' | grep -io "hit your [a-z ]*limit.*" | tail -1 | sed -E 's/\[[0-9;?]*[A-Za-z]//g' | cut -c1-120)
    [ -n "$MSG" ] && { MSG="You've $MSG"; break; }
  done
    if [ -n "$MSG" ]; then echo "$MSG" > dispatch/LIMIT_HIT; PAUSED=1; echo "- usage limit hit: $MSG (launches paused, retry in 30 min)" >> dispatch/status.md
      printf 'Usage limit hit\n%s\n' "$MSG" > "dispatch/alerts/$(date -u +%Y%m%dT%H%M%S)-limit.txt"; fi
fi
# Stalled: the claude process is alive but sits at an empty prompt after "Can't reach the API server" (Mac slept / wifi dropped) and nothing has been written for 20 min.
# Kill it so the reaper below restarts it (the restart is not counted against the 3-restart cap: a network drop is not the agent's fault).
for S in dispatch/started/*; do
  [ -e "$S" ] || continue; n=$(basename "$S")
  [ -f "dispatch/done/$n" ] && continue
  [ -f "dispatch/logs/$n.term.log" ] || continue
  find "dispatch/logs/$n.term.log" -mmin +20 | grep -q . || continue
  pgrep -f "AGENT-ID-$n\." >/dev/null || continue
  tail -c 6000 "dispatch/logs/$n.term.log" | LC_ALL=C tr -cd '[:print:]\n' | grep -qiE "APIError|reach.{0,6}the.{0,6}API" || continue
  c=$(cat "dispatch/retries/$n" 2>/dev/null || echo 0); [ "$c" -gt 0 ] && echo $((c-1)) > "dispatch/retries/$n"
  pkill -f "AGENT-ID-$n\."; echo "- #$n STALLED (API unreachable, idle 20+ min), killed so it restarts $(date -u +%FT%TZ)" >> dispatch/status.md
done
bash dispatch/dupguard.sh >/dev/null 2>&1 &
python3 dispatch/gh_events.py >/dev/null 2>&1 &   # logs every PR/issue open, merge and close to dispatch/github.log
bash dispatch/architect.sh >/dev/null 2>&1 &   # headless architect review, at most every 20 min when something changed   # alerts when a PR branch carries iCloud duplicate files
python3 dispatch/automerge.py >/dev/null 2>&1 &   # OFF unless automerge.conf enabled=1; merges architect-approved PRs and logs them
# Idle at prompt: a local-model agent finished its turn ("Worked for ... done") without finishing the job and has been silent 20+ min. Kill it; the reaper below restarts it (counts as a restart, and a local try).
for S in dispatch/started/*; do
  [ -e "$S" ] || continue; n=$(basename "$S")
  [ -f "dispatch/done/$n" ] && continue
  [ -f "dispatch/logs/$n.term.log" ] || continue
  find "dispatch/logs/$n.term.log" -mmin +20 | grep -q . || continue
  pgrep -f "AGENT-ID-$n\." >/dev/null || continue
  tail -c 3000 "dispatch/logs/$n.term.log" | LC_ALL=C tr -cd '[:print:]\n' | grep -qE "Worked for .*done [0-9]" || continue
  pkill -f "AGENT-ID-$n\."; echo "- #$n IDLE at prompt 20+ min after ending its turn, killed so it restarts $(date -u +%FT%TZ)" >> dispatch/status.md
done
# Reaper: an agent that has a started marker but no live process and no done marker is dead (window closed, Mac slept/rebooted, crash).
# Clear the marker so the loop below restarts it (max 3 restarts, then alert and leave it).
mkdir -p dispatch/retries dispatch/alerts
for S in dispatch/started/*; do
  [ "$PAUSED" = 1 ] && break
  [ -e "$S" ] || continue; n=$(basename "$S")
  [ -f "dispatch/done/$n" ] && continue
  grep -Evx '\s*(#.*)?' dispatch/batch.txt | grep -qx "$n" || continue
  find "$S" -mmin +3 | grep -q . || continue
  pgrep -f "AGENT-ID-$n\." >/dev/null && continue   # a real claude process for this agent
  AP=$(pgrep -f "agent\.sh $n( |\$)" | head -1)
  if [ -n "$AP" ]; then   # launcher alive but no claude: allow 5 min startup, then kill the stuck orphan and restart
    ET=$(ps -o etime= -p "$AP" | tr -d ' ')
    case "$ET" in ??:??|?:??) [ "${ET%%:*}" -lt 5 ] && continue ;; esac
    pkill -f "agent\.sh $n( |\$)"; echo "- #$n STUCK (launcher up $ET, no claude), killed for restart" >> dispatch/status.md
  fi
  c=$(cat "dispatch/retries/$n" 2>/dev/null || echo 0)
  if [ "$c" -ge 3 ]; then
    [ -f "dispatch/retries/$n.gaveup" ] || { touch "dispatch/retries/$n.gaveup"; echo "- #$n DEAD: gave up after 3 restarts" >> dispatch/status.md
      printf 'Agent keeps dying\n%s died 3 times. I need to look at it.\n' "$n" > "dispatch/alerts/$(date -u +%Y%m%dT%H%M%S)-dead-$n.txt"; }
    continue
  fi
  backoff_due "$n" || continue   # wait 30/60/120 s between restarts instead of restarting at once (#254)
  LASTOUT=$(tail -c 1500 "dispatch/logs/$n.term.log" 2>/dev/null | LC_ALL=C tr -cd '[:print:]\n' | grep -v "^\s*$" | tail -2 | tr '\n' ' ' | cut -c1-200)
  record_exit "$n" 1 "$LASTOUT"
  if is_permanent "$n"; then   # branch/worktree conflicts will not fix themselves: park it and tell the owner once
    [ -f "dispatch/retries/$n.gaveup" ] || { touch "dispatch/retries/$n.gaveup"; echo "- #$n PARKED (permanent failure, not restarted): $LASTOUT" >> dispatch/status.md
      printf 'Agent parked\n%s hit a failure a restart will not fix. I need to look at it.\n' "$n" > "dispatch/alerts/$(date -u +%Y%m%dT%H%M%S)-parked-$n.txt"; }
    continue
  fi
  echo $((c+1)) > "dispatch/retries/$n"; rm -f "$S"
  echo "- #$n DEAD (no live agent process): restart $((c+1))/3 $(date -u +%FT%TZ) last output: $LASTOUT" >> dispatch/status.md
  printf 'Agent restarted\n%s had no live process, so I restarted it (%s of 3).\n' "$n" "$((c+1))" > "dispatch/alerts/$(date -u +%Y%m%dT%H%M%S)-restart-$n.txt"
done
[ "$(grep -c "FAILURES $(date +%F)" dispatch/status.md 2>/dev/null)" = 0 ] && [ -n "$(ls dispatch/exits 2>/dev/null)" ] && failure_summary   # once a day: failures by cause
mkdir -p dispatch/cache; ps -axo pid,ppid,etime,command | grep -E "agent\.sh|claude|caffeinate|AGENT-ID" | grep -v grep > dispatch/cache/ps.txt 2>/dev/null
[ -z "$(find dispatch/cache/notes.stamp -mmin -5 2>/dev/null)" ] && { touch dispatch/cache/notes.stamp; dispatch/notes.sh >> dispatch/cache/notes.log 2>&1; }
[ -z "$(find dispatch/cache/cleanup.stamp -mmin -120 2>/dev/null)" ] && { touch dispatch/cache/cleanup.stamp; ( dispatch/cleanup_worktrees.sh >> dispatch/cache/cleanup.log 2>&1 & ); }   # background: a hung simulator or git call must never freeze the loop
[ -z "$(find dispatch/cache/metrics.stamp -mmin -5 2>/dev/null)" ] && { touch dispatch/cache/metrics.stamp; python3 "$REPO_DIR/dispatch/metrics.py" >> dispatch/cache/metrics.log 2>&1; }
python3 "$REPO_DIR/dispatch/health.py" >> dispatch/cache/metrics.log 2>&1
python3 "$REPO_DIR/dispatch/dashboard.py" >/dev/null 2>&1
python3 "$REPO_DIR/dispatch/freshness.py" >> dispatch/cache/metrics.log 2>&1   # checks every page data source is current; fixes derived lists
python3 "$REPO_DIR/dispatch/founder.py" >> dispatch/cache/metrics.log 2>&1
python3 "$REPO_DIR/dispatch/founder3d.py" >> dispatch/cache/metrics.log 2>&1   # FounderView3D.html (separate 3D page; reads FounderStatus.html, never edits it)
python3 "$REPO_DIR/dispatch/inject_review.py" >/dev/null 2>&1   # adds the Review now button to the three dashboards
[ "$PAUSED" = 0 ] && python3 "$REPO_DIR/dispatch/autoqueue.py" >> dispatch/cache/metrics.log 2>&1
# iCloud sync creates conflict copies like "fix-240 2" in started/; they never get a done marker and used to count as running agents, blocking every start
for J in dispatch/started/*\ * dispatch/done/*\ *; do [ -e "$J" ] && rm -f "$J"; done
RUNNING=$(ls dispatch/started 2>/dev/null | grep -v " " | while read n; do [ -f "dispatch/done/$n" ] || [ -f "dispatch/retries/$n.gaveup" ] || echo $n; done | wc -l | tr -d ' ')
# LOCAL (Ollama) is a 4th slot: it does not count toward the 3 Claude slots. One local agent at a time, fix-/qa- jobs only, once per job.
LOCAL_ON=0; LOCAL_BUSY=0
if grep -qE '^enabled=1' dispatch/local.conf 2>/dev/null && curl -s -m 2 http://localhost:11434/api/tags >/dev/null 2>&1; then LOCAL_ON=1; fi
# self-heal: local model enabled but the Ollama server is not answering (crashed, killed, Mac slept) -> start it again (at most every 2 minutes)
if grep -qE '^enabled=1' dispatch/local.conf 2>/dev/null && [ "$LOCAL_ON" = 0 ] && [ -z "$(find dispatch/cache/ollama.stamp -mmin -2 2>/dev/null)" ]; then
  touch dispatch/cache/ollama.stamp
  if command -v ollama >/dev/null 2>&1 || [ -x /opt/homebrew/bin/ollama ]; then
    ( PATH="/opt/homebrew/bin:$PATH" OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=q8_0 OLLAMA_CONTEXT_LENGTH=65536 OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_KEEP_ALIVE=10m nohup ollama serve >/tmp/ollama.log 2>&1 & )
    echo "- ollama was not answering, started it again $(date -u +%FT%TZ)" >> dispatch/status.md
    sleep 4; curl -s -m 2 http://localhost:11434/api/tags >/dev/null 2>&1 && LOCAL_ON=1
  fi
fi
_lp=$(cat dispatch/locks/local.pid 2>/dev/null); [ -n "$_lp" ] && kill -0 "$_lp" 2>/dev/null && LOCAL_BUSY=1
CLAUDE_OFF=0; grep -qE '^claude=off' dispatch/local.conf 2>/dev/null && CLAUDE_OFF=1
_mt=$(grep -E '^max_tries=' dispatch/local.conf 2>/dev/null | cut -d= -f2); _mt=${_mt:-3}
if [ "$LOCAL_BUSY" = 1 ]; then _lj=$(tail -1 dispatch/local_runs.txt 2>/dev/null | cut -d'|' -f2 | tr -d ' '); [ -n "$_lj" ] && [ -f "dispatch/started/$_lj" ] && [ ! -f "dispatch/done/$_lj" ] && RUNNING=$((RUNNING-1)); fi
# WIP limit: do not start NEW feature agents while 4 or more PRs are open (finish review/QA first). fix-/qa- work is always allowed.
OPEN=$(gh pr list --repo __REPO__ --state open --json number -q length 2>/dev/null); OPEN=${OPEN:-0}
OPEN_LIM=$(grep -E '^open_pr_limit=' dispatch/wip.conf 2>/dev/null | cut -d= -f2); case "$OPEN_LIM" in ''|*[!0-9]*) OPEN_LIM=4;; esac
for N in $(python3 "$REPO_DIR/dispatch/order_batch.py" 2>/dev/null | grep . || grep -Ev '^\s*(#|$)' dispatch/batch.txt); do   # priority order (fix/qa first, then the Prioritise rank); plain batch order if the script fails
  [ "$PAUSED" = 1 ] && break
  [ -f "dispatch/started/$N" ] && continue
  EXTRA=0
  if [ "$CLAUDE_OFF" = 1 ]; then
    # LOCAL ONLY: never start a Claude agent. One local job at a time, each with a limited number of tries.
    [ "$LOCAL_ON" = 1 ] && [ "$LOCAL_BUSY" = 0 ] || continue
    _t=$(cat "dispatch/local_tried/$N" 2>/dev/null || echo 0); [ "$_t" -ge "$_mt" ] 2>/dev/null && continue
    case " $(grep -E '^skip=' dispatch/local.conf 2>/dev/null | cut -d= -f2-) " in *" $N "*) continue;; esac   # jobs too big for the local model wait for Claude
    case "$N" in fix-*|qa-*) ;; *) continue ;; esac   # local model only takes fix-/qa- jobs (kinds in local.conf); features wait for Claude
    EXTRA=1
  elif [ "$RUNNING" -ge 3 ]; then
    case "$N" in fix-*|qa-*) [ "$LOCAL_ON" = 1 ] && [ "$LOCAL_BUSY" = 0 ] && [ ! -f "dispatch/local_tried/$N" ] && EXTRA=1 ;; esac
    [ "$EXTRA" = 0 ] && continue
  fi
  case "$N" in fix-*|qa-*) ;; *) [ "$OPEN" -ge "$OPEN_LIM" ] && continue ;; esac
  touch "dispatch/started/$N"; if [ "$EXTRA" = 1 ]; then LOCAL_BUSY=1; else RUNNING=$((RUNNING+1)); fi
  echo "- #$N STARTED $(date -u +%FT%TZ)" >> dispatch/status.md
  launch_agent "$N" "$EXTRA"
  sleep 10   # stagger launches: simultaneous "git worktree add" calls fight over .git/config.lock and die
done
