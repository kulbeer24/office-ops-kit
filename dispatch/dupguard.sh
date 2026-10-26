#!/bin/bash
# dupguard.sh: alert when an open PR branch contains iCloud duplicate files ("CLAUDE 2.md", ".git 2"). Cheap; run_batch calls it every ~5 min.
cd "$(dirname "$0")/.." || exit 0
S=dispatch/cache/dupguard.stamp; mkdir -p dispatch/cache dispatch/alerts
[ -n "$(find "$S" -mmin -5 2>/dev/null)" ] && exit 0; touch "$S"
python3 - <<'PY' 2>/dev/null | while read -r PR BR; do
import json
try:
    for p in json.load(open("dispatch/cache/prs.json")): print(p["number"], p["headRefName"])
except Exception: pass
PY
  perl -e 'alarm 30; exec @ARGV' git fetch -q origin "$BR" >/dev/null 2>&1
  SHA=$(git rev-parse -q --verify "origin/$BR" 2>/dev/null) || continue
  [ -f "dispatch/cache/dupguard.$PR.$SHA" ] && continue
  BAD=$(git diff --name-only origin/main..."origin/$BR" 2>/dev/null | grep -E ' [0-9]+(\.[^/]*)?$' | head -8)
  [ -z "$BAD" ] && continue
  touch "dispatch/cache/dupguard.$PR.$SHA"
  printf 'Stray duplicate files in PR %s\nBranch %s contains iCloud duplicates:\n%s\nThe architect removes them before merging.\n' "$PR" "$BR" "$BAD" > "dispatch/alerts/$(date -u +%Y%m%dT%H%M%S)-attn-dup-$PR.txt"
  echo "- dupguard: PR #$PR has iCloud duplicate files ($(echo "$BAD" | wc -l | tr -d ' ') shown), alerted $(date -u +%FT%TZ)" >> dispatch/status.md
done
exit 0
