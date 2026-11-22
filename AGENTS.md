# AGENTS.md — find-agent-pane

Instructions for coding agents working in this repository.

## Set up for a user

Goal: `find-agent-pane` lists which coding agent (Claude Code, Codex, Gemini CLI, ...) owns each tmux pane. macOS and Linux. Nothing here needs the person.

1. Check what is present.
   - `tmux -V` prints a version. If not: `brew install tmux` (macOS) or `sudo apt install tmux` (Debian/Ubuntu).
   - `uv --version` prints a version. If not: `curl -LsSf https://astral.sh/uv/install.sh | sh`, then `export PATH="$HOME/.local/bin:$PATH"` (or open a new shell).
2. Install: `uv tool install find-agent-pane`. It ends with `Installed 1 executable: find-agent-pane`; `find-agent-pane --version` prints `find-agent-pane 0.1.0` or newer. `uv tool update-shell` puts `~/.local/bin` on PATH for later shells. No Python dependencies; Python 3.9+ (uv fetches one if needed).
3. Prove it on a throwaway tmux server, so no real session is touched:
   `tmux -L fap-check new-session -d -s demo 'sleep 60'; find-agent-pane -L fap-check --all; tmux -L fap-check kill-server`
   prints one row such as `%0	demo:1.1	-	-	<cwd>		<title>` (agent column `-`: a pane with no agent) and exits 0. Then run `find-agent-pane --all-servers` to see the user's real panes; a row with an agent name in the third column is a recognized agent.
4. If it fails, in this order:
   - `find-agent-pane: command not found`: `~/.local/bin` is not on PATH (step 2).
   - Empty output with no `--all`: no pane currently runs a recognized agent, or no tmux server is running on that socket. Use `--all` to list every pane, and `--all-servers` or `-L NAME` / `-S PATH` for other tmux servers.
   - A row says `unknown`: two agents compete for the pane and neither is in the foreground; the candidates are printed on that row. Report them, do not guess.
   - It never writes to tmux; if you need to send keys, do that yourself with the printed pane id.

## Working in the repo

A CLI and Python module that says which coding agent owns each tmux pane, from `ps` and `tmux` output
only. Standard library only, Python 3.9+.

### Layout

- `find_agent_pane/core.py`: classification and ownership rules.
- `find_agent_pane/cli.py`: tmux and ps reading, output.
- `find_agent_pane/agents.json`: the agent table.
- `tests/fixtures/*.json`: real panes captured from live agents.

### Test

- `python -m pytest -q tests`. Every fixture must pass; add a fixture for every fix.
- Run the CLI against a throwaway server (`tmux -L NAME`), never the user's tmux server, when checking output.

### Rules that must hold

- Identity comes from the executable (ucomm, argv[0], runtime entry script), never from later arguments.
- A known shell's spoofed argv[0] is not an agent.
- A version-shaped ucomm defers to argv[0].
- Helpers below an agent are its work.
- Ambiguity prints `unknown` with the candidates.

### Do not

- Add dependencies, network calls, or anything that writes to tmux.
