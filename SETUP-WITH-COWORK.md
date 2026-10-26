# Paste this into Claude Cowork

(Select the Office Ops Kit folder and your project folder first, and connect GitHub if Cowork offers it.)

---

I want to set up the Office Ops Kit for my project. The kit folder is the one containing `install.py` and `README.md`; my project is the other folder (a git clone of my GitHub repo). Please do the following, in order, and keep it simple for me:

1. Read the kit's `README.md` and `ORCHESTRATOR.md` so you know how it works. Look at my project folder (README, package files, existing tests) so you can propose answers instead of asking me everything.
2. Find my GitHub repo name (owner/name). Use the GitHub connector if it is connected, otherwise the git remote in the project folder. If GitHub is not connected, offer to connect it.
3. Ask me, in one short multiple-choice question set: the project name, my city (for the clock and weather in the 3D office), and the command that runs my tests (propose one from what you saw).
4. Run: `python3 <kit>/install.py --prepare --project-dir <my project folder> --repo <owner/name> --city "<city>" --project-name "<name>" --test-cmd "<test command>"` (use the folder paths as you see them).
5. Fill in my project's `CLAUDE.md` (create it from the kit's template if missing) with a short description, the test command, and anything in my README that agents must follow. Tell me it needs committing.
6. Rewrite the editable planning files in `<project>/dispatch/` (`targets.txt`, `release.txt`, `roadmap.txt`, `journey.txt`, `success.txt` if present) so they describe MY project (ask me for the launch date and the 3 to 5 big themes), replacing the generic examples.
7. If my repo has no open issues, offer to draft 3 to 5 starter issues with clear "done" criteria, and to queue them.
8. Tell me to double-click **Finish Setup** in the kit folder (it signs in to GitHub, installs auto-start and starts everything), then to open http://localhost:8787/ .

From then on, act as my Orchestrator as described in `ORCHESTRATOR.md`: when I message you, check `dispatch/status.md`, the Founder view data and open PRs, answer questions the architect left for me, queue work, and keep the planning files current. Never merge or close anything yourself.
