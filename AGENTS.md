# AGENTS.md — find-agent-pane

Instructions for coding agents working in this repository.

- **What it is.** A CLI and Python module that says which coding agent owns each tmux pane, from
  `ps` and `tmux` output only. Standard library only, Python 3.9+.
- **Layout.** `find_agent_pane/core.py` (classification and ownership rules), `cli.py` (tmux and ps
  reading, output), `agents.json` (the agent table), `tests/fixtures/*.json` (real panes).
- **Test.** `python -m pytest -q tests`. Every fixture must pass; add a fixture for every fix.
- **Rules that must hold.** Identity comes from the executable (ucomm, argv[0], runtime entry
  script), never from later arguments. A known shell's spoofed argv[0] is not an agent. A
  version-shaped ucomm defers to argv[0]. Helpers below an agent are its work. Ambiguity prints
  `unknown` with the candidates.
- **Do not** add dependencies, network calls, or anything that writes to tmux.
