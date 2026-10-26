# Office Ops Kit

A small "software team" that runs on your own computer: AI agents build issues from your GitHub repo, a solution architect reviews and QA-tests their pull requests, and you merge. Three live views show everything: the **Founder view** (what needs you, the road to launch, priorities), the **Status view** (agents, PRs, logs) and a **3D office** where the founder, architect, orchestrator and developer agents work, take coffee breaks and chat. It runs by itself; nothing to start by hand after setup.

## What you need
- Your project as a **git clone of a GitHub repo** (agents work through GitHub issues and pull requests).
- A **Claude** account with Claude Code (agents use it; usage counts against your plan) and the **GitHub CLI** (`gh`).
- Mac (fully supported) or Windows (through WSL2 Ubuntu, experimental). Linux works the same as WSL.

## Setup in three steps (with Cowork)
1. Open **Claude Cowork**. Select two folders: this kit and your project clone. Connect GitHub when asked.
2. Paste the prompt from **SETUP-WITH-COWORK.md**. Cowork asks a few questions (project name, city for the clock and weather, test command), then configures everything.
3. Double-click **Finish Setup (Mac).command** (or **Finish Setup (Windows).bat**). It signs you in to GitHub, installs auto-start, and starts the dispatcher. That is the only manual step, once.

Afterwards the dispatcher starts at every login. Open **http://localhost:8787/** for the Founder view, `/status.html` for the Status view and `/FounderView3D.html` for the 3D office. (The phone address over Tailscale is optional; skip it.)

No Cowork? Just double-click Finish Setup: it asks for your project folder, repo and city itself.

## Day to day
- Put work in as **GitHub issues**, then add the issue numbers to `dispatch/batch.txt` (one per line), or drop a note file in `dispatch/inbox/` (Cowork can do this for you: see ORCHESTRATOR.md). Agents start by themselves (3 at a time).
- The architect reviews every PR about every 20 minutes. When a PR is **ready to merge**, the views and a notification tell you. **You** merge it on GitHub. Agents never merge or close anything.
- **Pause / start** from the Founder view (top of the Systems tab), or put a `dispatch/PAUSED` file in place. A timed pause: write `YYYYMMDDHHMM` (local time) into `dispatch/pause_at`.
- **Review now** button (bottom left of each view) forces an architect or orchestrator review straight away.
- Stuck? `dispatch/logs/loop.out` has the loop's output; the Systems tab lists problems in plain words.

## Things to know
- The views were built for an app that ships test builds, so some labels say "test build", "release" and "launch". Edit `dispatch/release.txt`, `success.txt`, `roadmap.txt`, `journey.txt`, `targets.txt` to match your project (Cowork can rewrite them for you).
- Every agent follows the **CLAUDE.md** at the root of your project: put the exact test command and your rules there. The kit makes a starter one if you have none.
- macOS may ask once to let `bash` access Documents/Desktop if your project lives there. Allow it, or keep the project under your home folder.
- Updating the kit later: replace the kit folder and run Finish Setup again; it upgrades scripts and never overwrites your data files.
