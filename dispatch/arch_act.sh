#!/bin/bash
# arch_act.sh: the only way the headless architect changes dispatch state. Idempotent. Usage:
#   arch_act.sh ready <pr> <sha7>   mark a PR "ready to merge" (owner_hold.txt line + phone alert + log)
#   arch_act.sh hold <pr> "<why>"   park a PR for the owner (owner_hold.txt)
#   arch_act.sh queue-fix <issue>   queue fix-<issue> (fixes/<issue>.txt must already exist)
#   arch_act.sh queue-qa <pr>       queue qa-<pr>
#   arch_act.sh log "<text>"        one line in orchestrator-log.md
#   arch_act.sh ack                 remember this review (changed.sh ack)
cd "$(dirname "$0")/.." || exit 1
D=dispatch; NOW=$(date -u +%FT%TZ)
queue() { n="$1"; [ -f "$D/started/$n" ] && [ ! -f "$D/done/$n" ] && { echo "$n already running"; return; }
  grep -Ev '^\s*(#|$)' "$D/batch.txt" | grep -qx "$n" && { echo "$n already queued"; return; }
  [ -n "$(tail -c1 "$D/batch.txt")" ] && echo >> "$D/batch.txt"; echo "$n" >> "$D/batch.txt"; echo "queued $n"; }
case "$1" in
  ready) PR="$2"; SHA="$3"
    grep -vE "^$PR[[:space:]]+# ready" "$D/owner_hold.txt" > "$D/owner_hold.tmp"; echo "$PR  # ready to merge (architect approved $SHA)" >> "$D/owner_hold.tmp"; mv "$D/owner_hold.tmp" "$D/owner_hold.txt"
    mkdir -p "$D/alerts"; printf 'PR %s ready to merge\nThe architect approved it (%s). Merge when you like.\n' "$PR" "$SHA" > "$D/alerts/$(date -u +%Y%m%dT%H%M%S)-attn-merge-$PR.txt"
    echo "- $NOW (architect run) PR #$PR approved at $SHA and marked ready to merge." >> "$D/orchestrator-log.md"; echo "ready $PR" ;;
  hold) PR="$2"; grep -qE "^$PR[[:space:]]" "$D/owner_hold.txt" || echo "$PR  # $3" >> "$D/owner_hold.txt"; echo "- $NOW (architect run) PR #$PR held for the owner: $3" >> "$D/orchestrator-log.md"; echo "held $PR" ;;
  queue-fix) touch "$D/requeue/fix-$2"; r=$(queue "fix-$2"); echo "$r"; echo "- $NOW (architect run) fix round for issue #$2: $r" >> "$D/orchestrator-log.md" ;;
  queue-qa) touch "$D/requeue/qa-$2"; r=$(queue "qa-$2"); echo "$r"; echo "- $NOW (architect run) QA for PR #$2: $r" >> "$D/orchestrator-log.md" ;;
  log) echo "- $NOW (architect run) $2" >> "$D/orchestrator-log.md"; echo logged ;;
  ack) bash "$D/changed.sh" ack ;;
  *) echo "unknown command"; exit 1 ;;
esac
