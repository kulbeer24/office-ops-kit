#!/bin/bash
# Cheap gate for the architect review. Prints CHANGED or UNCHANGED (plus why) from local files only, no network, no AI.
# Fingerprint = open PRs and their last-update times, finished-agent markers, unseen notes, queue. Run "changed.sh ack" after a review to remember it.
cd "$(dirname "$0")" || exit 1
mkdir -p cache; date +%s > cache/arch.checked
FP=$( { python3 -c "
import json
try:
    for p in sorted(json.load(open('cache/prs.json')), key=lambda x:x['number']): print('PR',p['number'],p['updatedAt'])
except Exception: print('noprs')"
  ls -l --time-style=+%s done 2>/dev/null | awk '{print $6,$7}' | sort
  ls notes 2>/dev/null; ls inbox/pr inbox/failed 2>/dev/null; ls requeue 2>/dev/null; grep -Ev '^\s*(#|$)' batch.txt | sort | md5sum; } | md5sum | cut -d' ' -f1)
[ "$1" = ack ] && { echo "$FP" > cache/arch.seen; echo acked; exit 0; }
if [ -f cache/arch.seen ] && [ "$(cat cache/arch.seen)" = "$FP" ]; then echo "UNCHANGED"; else echo "CHANGED"; fi
