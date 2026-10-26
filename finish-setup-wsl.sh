#!/bin/bash
# Linux/WSL entry point (also what the Windows .bat calls). Prepares if needed, then activates.
cd "$(dirname "$0")" || exit 1
command -v python3 >/dev/null || { echo "Install python3: sudo apt install -y python3"; exit 1; }
for t in git perl curl; do command -v $t >/dev/null || { echo "Install $t: sudo apt install -y $t"; exit 1; }; done
command -v gh >/dev/null || echo "Missing gh. Install: https://github.com/cli/cli/blob/trunk/docs/install_linux.md"
command -v claude >/dev/null || echo "Missing Claude Code. Install: npm install -g @anthropic-ai/claude-code   (needs Node 18+)"
if [ ! -f .project-dir ]; then
  read -p "Path to your project git clone (inside WSL, e.g. /mnt/c/Users/you/Projects/app or ~/app): " PD; PD="${PD/#\~/$HOME}"
  read -p "GitHub repo (owner/name), or Enter to detect: " RP; read -p "Your city (optional): " CT
  python3 install.py --prepare --project-dir "$PD" ${RP:+--repo "$RP"} ${CT:+--city "$CT"} || exit 1
fi
python3 install.py --activate
