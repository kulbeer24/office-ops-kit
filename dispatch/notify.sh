#!/bin/bash
# Shows a macOS notification for each dispatch/alerts/*.txt (line 1 = title, rest = message), then moves it to alerts/sent/.
# Written by the orchestrator (Cowork review task); displayed here because only the Mac can notify. Called by run_batch.sh every loop.
export PATH="/usr/bin:/bin:$PATH"
D="$(cd "$(dirname "$0")" && pwd)/alerts"; mkdir -p "$D/sent"
for f in "$D"/*.txt; do
  [ -f "$f" ] || continue
  T=$(head -1 "$f" | tr -d '"'); M=$(tail -n +2 "$f" | tr '\n' ' ' | tr -d '"' | cut -c1-220)
  source "$(dirname "$D")/lib_kit.sh" 2>/dev/null; REPO_DIR="$(cd "$(dirname "$D")/.." && pwd)"; notify_user "__PROJECT__: $T" "$M"
  ( "$(dirname "$D")/push.sh" "$T" "$M" "$(basename "$f")" & ) >/dev/null 2>&1
  mv "$f" "$D/sent/"
done
