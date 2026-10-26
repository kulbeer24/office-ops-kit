#!/bin/bash
# Run by the loop every ~5 minutes. (1) Acknowledges owner "[note]" issues, labels them ops, drops them in dispatch/notes/.
# (2) Watches open PRs and writes dispatch/events.md + a Mac banner when a PR opens, gets new commits, or closes/merges.
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
REPO=__REPO__; REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"; cd "$REPO_DIR" || exit 1
mkdir -p dispatch/notes dispatch/alerts dispatch/cache
alert() { printf '%s\n%s\n' "$1" "$2" > "dispatch/alerts/$(date -u +%Y%m%dT%H%M%S)-$3.txt"; }
gh label create ops --color 6A737D --description "Orchestration and process, not app work" --repo "$REPO" >/dev/null 2>&1
for n in $(gh issue list --repo "$REPO" --state open --limit 30 --json number,title --jq '.[]|select(.title|startswith("[note]"))|.number' 2>/dev/null); do
  [ -f "dispatch/notes/$n.seen" ] && continue
  touch "dispatch/notes/$n.seen"
  gh issue view "$n" --repo "$REPO" --json title,body --jq '"# "+.title+"\n\n"+.body' > "dispatch/notes/$n.md" 2>/dev/null
  gh issue edit "$n" --repo "$REPO" --add-label ops >/dev/null 2>&1
  gh issue comment "$n" --repo "$REPO" --body "Received by the dispatcher at $(date '+%a %d %b %H:%M'). Claude (the orchestrator) answers here when it next picks this up; for anything urgent message Claude in the Cowork chat." >/dev/null 2>&1
  echo "- note #$n received from owner (acknowledged, waiting for Claude)" >> dispatch/status.md
  alert "Note received" "Your note #$n reached the dispatcher." "note-$n"
done
NOW=$(gh pr list --repo "$REPO" --state open --json number,headRefOid,title --jq '.[]|"\(.number) \(.headRefOid[0:7]) \(.title)"' 2>/dev/null)
[ -z "$NOW" ] && [ ! -s dispatch/cache/prs.snap ] && exit 0
if [ -f dispatch/cache/prs.snap ]; then
  echo "$NOW" | while read -r num sha title; do
    [ -z "$num" ] && continue
    old=$(grep "^$num " dispatch/cache/prs.snap | cut -d' ' -f2)
    if [ -z "$old" ]; then echo "- $(date -u +%FT%TZ) PR #$num opened: $title" >> dispatch/events.md; alert "PR opened" "#$num $title" "pr-$num"
    elif [ "$old" != "$sha" ]; then echo "- $(date -u +%FT%TZ) PR #$num updated (new commits $old to $sha): $title" >> dispatch/events.md; alert "PR updated" "#$num has new commits" "pr-$num"; fi
  done
  while read -r num sha title; do
    [ -z "$num" ] && continue
    echo "$NOW" | grep -q "^$num " || { echo "- $(date -u +%FT%TZ) PR #$num closed or merged: $title" >> dispatch/events.md; alert "PR closed or merged" "#$num $title" "pr-$num"; }
  done < dispatch/cache/prs.snap
fi
[ -n "$NOW" ] && echo "$NOW" > dispatch/cache/prs.snap || : > dispatch/cache/prs.snap
exit 0
