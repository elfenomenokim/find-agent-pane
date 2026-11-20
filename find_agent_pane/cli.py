"""find-agent-pane: list tmux panes with the coding agent that owns each one."""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
from pathlib import Path

from . import __version__
from .core import Proc, Table, resolve_pane

FIELDS = ["pane_id", "pane_pid", "pane_tty", "pane_current_path", "pane_title", "session_name",
          "window_index", "pane_index"]
SEP = "\t|fap|\t"  # tmux escapes control characters such as \x1f in -F output


def snapshot() -> dict[int, Proc]:
    # -ww: without a terminal (launchd, cron) ps cuts args to a default width; a Claude command
    # line is 220+ chars and its --session-id sits at the end (2026-11-21, topology recorder).
    out = subprocess.run(["ps", "-ww", "-e", "-o", "pid=,ppid=,pgid=,tpgid=,stat=,tty=,ucomm=,args="],
                         capture_output=True, text=True, timeout=10,
                         env={**os.environ, "LC_ALL": "C"}).stdout
    procs: dict[int, Proc] = {}
    for line in out.splitlines():
        parts = line.split(None, 7)
        if len(parts) < 7 or not parts[0].isdigit():
            continue
        pid, ppid, pgid, tpgid, stat, tty, ucomm = parts[:7]
        args = parts[7] if len(parts) > 7 else ucomm
        try:
            procs[int(pid)] = Proc(int(pid), int(ppid), ucomm, args, int(pgid), int(tpgid), stat, tty)
        except ValueError:
            continue
    return procs


def servers(args) -> list[list[str]]:
    """tmux argument prefixes, one per server to read."""
    if args.socket_path:
        return [["-S", args.socket_path]]
    if args.socket_name:
        return [["-L", args.socket_name]]
    if not args.all_servers:
        return [[]]
    found: dict[str, None] = {}
    tmpdir = os.environ.get("TMUX_TMPDIR") or "/tmp"
    for path in glob.glob(os.path.join(tmpdir, f"tmux-{os.getuid()}", "*")) + \
            glob.glob(f"/private/tmp/tmux-{os.getuid()}/*"):
        found[os.path.realpath(path)] = None
    # live servers started with -S <path> elsewhere
    ps = subprocess.run(["ps", "-u", str(os.getuid()), "-o", "args="], capture_output=True, text=True).stdout
    for line in ps.splitlines():
        words = line.split()
        if words and os.path.basename(words[0]).startswith("tmux") and "-S" in words:
            i = words.index("-S")
            if i + 1 < len(words):
                found[os.path.realpath(words[i + 1])] = None
    return [["-S", p] for p in found if os.path.exists(p)]


def panes(prefix: list[str]) -> list[dict]:
    fmt = SEP.join("#{%s}" % f for f in FIELDS)
    proc = subprocess.run(["tmux", *prefix, "list-panes", "-a", "-F", fmt],
                          capture_output=True, text=True, timeout=10)
    if proc.returncode != 0:
        return []
    rows, seen = [], set()
    for line in proc.stdout.splitlines():
        values = line.split(SEP)
        if len(values) != len(FIELDS):
            continue
        row = dict(zip(FIELDS, values))
        if row["pane_id"] in seen:          # grouped sessions list a pane once per member
            continue
        seen.add(row["pane_id"])
        row["server"] = " ".join(prefix) or "default"
        rows.append(row)
    return rows


def tilde(path: str) -> str:
    home = str(Path.home())
    return "~" + path[len(home):] if path == home or path.startswith(home + "/") else path


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="find-agent-pane", description=__doc__)
    p.add_argument("--agent", action="append", help="only panes owned by this family (repeatable)")
    p.add_argument("--json", action="store_true", help="one JSON object per pane")
    p.add_argument("--all", action="store_true", help="also list panes with no agent")
    p.add_argument("-L", dest="socket_name", help="tmux socket name, as tmux -L")
    p.add_argument("-S", dest="socket_path", help="tmux socket path, as tmux -S")
    p.add_argument("--all-servers", action="store_true",
                   help="read every tmux server of this user, including ones on -S paths")
    p.add_argument("--agents", type=Path, action="append", default=[],
                   help="extra agent table (JSON, same shape as the bundled agents.json)")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = p.parse_args(argv)

    user_table = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "find-agent-pane/agents.json"
    table = Table.load([user_table, *args.agents])
    procs = snapshot()
    rows = []
    for prefix in servers(args):
        for pane in panes(prefix):
            pid = int(pane["pane_pid"]) if pane["pane_pid"].isdigit() else 0
            v = resolve_pane(pid, procs, table)
            rows.append({
                "pane_id": pane["pane_id"], "server": pane["server"],
                "target": f'{pane["session_name"]}:{pane["window_index"]}.{pane["pane_index"]}',
                "family": v.family, "owner_pid": v.owner_pid, "headless": v.headless,
                "cwd": tilde(pane["pane_current_path"]), "session_hint": v.session_hint,
                "title": pane["pane_title"], "evidence": v.evidence,
                "candidates": [{"pid": c[0], "family": c[1]} for c in v.candidates],
            })
    if args.agent:
        rows = [r for r in rows if r["family"] in args.agent]
    elif not args.all:
        rows = [r for r in rows if r["family"]]
    multi = len({r["server"] for r in rows}) > 1
    for r in rows:
        if args.json:
            print(json.dumps(r, ensure_ascii=False))
            continue
        fam = r["family"] or "-"
        if r["headless"]:
            fam += "*"
        owner = str(r["owner_pid"]) if r["owner_pid"] else "-"
        extra = r["evidence"] if r["family"] == "unknown" else (
            f'resume={r["session_hint"][:12]}' if r["session_hint"] else "")
        cols = ([r["server"]] if multi else []) + [r["pane_id"], r["target"], fam, owner, r["cwd"], extra, r["title"]]
        print("\t".join(c for c in cols))
    return 0


if __name__ == "__main__":
    sys.exit(main())
