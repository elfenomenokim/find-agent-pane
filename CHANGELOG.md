# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses `MAJOR.MINOR.PATCH`.

## [Unreleased]

## [0.1.0] - 2026-11-21

### Added

- `find-agent-pane` CLI and `find_agent_pane` module: one `ps` snapshot and one `tmux list-panes`,
  owner per pane by executable identity, launcher unwrap, helper and clone exclusion, outermost
  owner per branch, job-control tie-break, `unknown` with evidence.
- Agent table (`agents.json`) for claude, codex, kimi, agy, pi, gemini, qwen, opencode, amp, crush,
  copilot, cursor-agent, goose and aider, each measured in a live pane; extensible with `--agents`
  or `~/.config/find-agent-pane/agents.json`.
- `--all-servers` reads every tmux server of the user, including servers on `-S` paths.
- 51 fixtures from real panes on macOS and Linux plus incident-derived cases.
