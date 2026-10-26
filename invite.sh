#!/bin/bash
# Gives one person read access to the private kit repo. They get an email invitation from GitHub (or see it at github.com/notifications).
# Usage: ./invite.sh <github-username> [repo-name]      Remove access later: gh api -X DELETE repos/<you>/<repo>/collaborators/<username>
set -e
U="${1:?usage: ./invite.sh <github-username> [repo-name]}"; NAME="${2:-office-ops-kit}"; OWNER=$(gh api user -q .login)
gh api -X PUT "repos/$OWNER/$NAME/collaborators/$U" -f permission=pull >/dev/null && echo "Invitation sent to $U for $OWNER/$NAME (read-only)."
