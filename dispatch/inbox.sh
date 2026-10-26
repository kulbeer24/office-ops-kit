#!/bin/bash
# Issue inbox. Claude (Cowork) drops dispatch/inbox/<slug>.md; this creates the GitHub issue
# with the owner's own authenticated gh, so the owner never relays a command.
# File format:
#   title: <issue title>
#   label: <bug|enhancement|documentation|chore>
#   queue: <now|hold>        now = append the new number to batch.txt (agent starts); hold = create only
#   ---
#   <issue body, markdown>
# Claude writes <slug>.tmp then renames to <slug>.md so a half-written file is never picked up.
# PR inbox (same idea, PRs only -- never merge/close): dispatch/inbox/pr/<slug>.md with
#   title: <PR title>
#   head: <branch already pushed>
#   base: <optional, default main>
#   ---
#   <PR body, must contain Closes #N>
# Called at the start of every run_batch.sh pass (loop.sh, every 20s).
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"; cd "$REPO_DIR" || exit 1
R=__REPO__
IN=dispatch/inbox
mkdir -p "$IN/done" "$IN/failed"
for f in "$IN"/*.md; do
  [ -f "$f" ] || continue
  slug=$(basename "$f" .md)
  title=$(sed -n 's/^title: //p' "$f" | head -1)
  label=$(sed -n 's/^label: //p' "$f" | head -1)
  queue=$(sed -n 's/^queue: //p' "$f" | head -1)
  tmp=$(mktemp)
  awk 'f{print} /^---$/{f=1}' "$f" > "$tmp"
  if [ -z "$title" ] || [ ! -s "$tmp" ]; then
    echo "missing title or body" > "$IN/failed/$slug.err"; mv "$f" "$IN/failed/$slug.md"; rm -f "$tmp"; continue
  fi
  out=$(gh issue create --repo "$R" --title "$title" --label "${label:-enhancement}" --body-file "$tmp" 2>&1)
  rm -f "$tmp"
  url=$(echo "$out" | grep -oE 'https://github.com/[^ ]+/issues/[0-9]+' | tail -1)
  if [ -z "$url" ]; then
    echo "$out" > "$IN/failed/$slug.err"; mv "$f" "$IN/failed/$slug.md"
    echo "- inbox $slug FAILED (see dispatch/inbox/failed/$slug.err) $(date -u +%FT%TZ)" >> dispatch/status.md
    continue
  fi
  n=${url##*/}
  echo "$n" > "$IN/done/$slug.number"; mv "$f" "$IN/done/$slug.md"
  if [ "$queue" = "now" ]; then
    [ -s dispatch/batch.txt ] && [ -n "$(tail -c1 dispatch/batch.txt)" ] && echo >> dispatch/batch.txt
    echo "$n" >> dispatch/batch.txt
  fi
  echo "- inbox $slug -> #$n ($queue) $(date -u +%FT%TZ)" >> dispatch/status.md
done

# ---- PR inbox: create pull requests for branches Claude pushed through the connector ----
mkdir -p "$IN/pr/done" "$IN/pr/failed"
for f in "$IN"/pr/*.md; do
  [ -f "$f" ] || continue
  slug=$(basename "$f" .md)
  title=$(sed -n 's/^title: //p' "$f" | head -1)
  head=$(sed -n 's/^head: //p' "$f" | head -1)
  base=$(sed -n 's/^base: //p' "$f" | head -1)
  tmp=$(mktemp)
  awk 'f{print} /^---$/{f=1}' "$f" > "$tmp"
  if [ -z "$title" ] || [ -z "$head" ] || ! grep -qE 'Closes #[0-9]+' "$tmp"; then
    echo "need title, head, and 'Closes #N' in the body" > "$IN/pr/failed/$slug.err"; mv "$f" "$IN/pr/failed/$slug.md"; rm -f "$tmp"; continue
  fi
  out=$(gh pr create --repo "$R" --base "${base:-main}" --head "$head" --title "$title" --body-file "$tmp" 2>&1)
  rm -f "$tmp"
  url=$(echo "$out" | grep -oE 'https://github.com/[^ ]+/pull/[0-9]+' | tail -1)
  if [ -z "$url" ]; then
    echo "$out" > "$IN/pr/failed/$slug.err"; mv "$f" "$IN/pr/failed/$slug.md"
    echo "- pr-inbox $slug FAILED (see dispatch/inbox/pr/failed/$slug.err) $(date -u +%FT%TZ)" >> dispatch/status.md
    continue
  fi
  echo "${url##*/}" > "$IN/pr/done/$slug.number"; mv "$f" "$IN/pr/done/$slug.md"
  echo "- pr-inbox $slug -> PR #${url##*/} $(date -u +%FT%TZ)" >> dispatch/status.md
done
