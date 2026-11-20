# Contributing

Thanks for helping. The most valuable contribution is a **fixture**: a pane the tool got wrong.

1. Capture the pane: `tmux display -p -t %N '#{pane_id} #{pane_pid} #{pane_tty}'` and
   `ps -ww -e -o pid=,ppid=,pgid=,tpgid=,stat=,tty=,ucomm=,args=` for the pane pid and its
   descendants. Remove secrets and replace your home directory with `~`.
2. Save it as `tests/fixtures/<short-name>.json` in the shape of the existing fixtures, with
   `expected_family` (and `expected_owner_pid` when it matters) and one line of `evidence`.
3. Make it pass: a new agent is usually an `agents.json` entry; a new trap is a rule in `core.py`
   with a comment that names the case.
4. Run `python -m pytest -q tests`.

Rules of the road: the standard library only; executable identity, never task prose; when two
owners are plausible the answer is `unknown`, never a guess.
