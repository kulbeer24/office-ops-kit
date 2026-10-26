#!/bin/bash
# Double-click once. Finishes the setup on this Mac (GitHub login, auto-start, first start). Safe to run again.
cd "$(dirname "$0")" || exit 1
echo "Office Ops Kit: finishing setup..."
if ! command -v python3 >/dev/null 2>&1; then echo "Python 3 is needed. A macOS dialog may offer to install the developer tools: accept it, then double-click this file again."; python3 --version; read -n1 -p "Press any key to close"; exit 1; fi
if [ ! -f .project-dir ]; then
  echo; echo "Your project is not set up yet (Cowork normally does this part)."
  read -p "Drag your project folder (a git clone of your GitHub repo) into this window and press Enter: " PD; PD="${PD%\"}"; PD="${PD#\"}"; PD="$(echo "$PD" | sed 's/\\ / /g; s/ *$//')"
  read -p "GitHub repo (owner/name), or press Enter to detect it: " RP
  read -p "Your city, for the clock and weather in the 3D office (optional): " CT
  python3 install.py --prepare --project-dir "$PD" ${RP:+--repo "$RP"} ${CT:+--city "$CT"} || { read -n1 -p "Press any key to close"; exit 1; }
fi
python3 install.py --activate
echo; read -n1 -p "Done. Press any key to close this window (the dispatcher keeps running in the background)."
