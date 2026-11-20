# Security policy

## Supported versions

Security fixes go into the latest release. Upgrade before reporting, in case the
problem is already fixed.

| Version | Supported |
| --- | --- |
| 0.1.x | Yes |
| Older | No |

## Reporting a vulnerability

Report it privately, not in a public issue: use the
[Report a vulnerability](https://github.com/elfenomenokim/find-agent-pane/security/advisories/new)
form on the repository's Security tab.

Include the command you ran, the Python version and platform, and what an attacker
could do with the result. You get a reply within a few days, and you hear when a
fix is out. Say how you want to be credited if you want a name in the release
note.

## In scope

- Running a pane's command line, title or path as code. The tool only reads `ps` and `tmux`
  output and never evaluates it.
- Reading another user's processes or tmux servers beyond what `ps` and the user's own tmux
  sockets already show.
- An extra agent table (`--agents`, `~/.config/find-agent-pane/agents.json`) causing anything
  other than a different classification.

## Out of scope

- A wrong or `unknown` classification. That is a bug report with the pane's process tree.
- Command lines visible in the output. They come from `ps`, which any local user can run.
