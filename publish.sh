#!/bin/bash
# Run once by the person SHARING the kit (needs the GitHub CLI logged in). Creates a PRIVATE repo from this folder (default name: office-ops-kit)
# and pushes it. Re-run any time to push an updated kit. Inviting people is a separate step: ./invite.sh <github-username>
set -e
cd "$(dirname "$0")"
NAME="${1:-office-ops-kit}"; OWNER=$(gh api user -q .login)
[ -d .git ] || git init -q -b main
git add -A; git commit -q -m "Office Ops Kit" 2>/dev/null || true
if gh repo view "$OWNER/$NAME" >/dev/null 2>&1; then git remote get-url origin >/dev/null 2>&1 || git remote add origin "https://github.com/$OWNER/$NAME.git"; git push -u origin main
else gh repo create "$NAME" --private --source . --remote origin --push; fi
echo "Done (private): https://github.com/$OWNER/$NAME"
echo "Invite someone with:  ./invite.sh <their-github-username>"
