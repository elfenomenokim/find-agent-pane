"""Which coding agent owns each tmux pane: classification and ownership from process evidence.

The rules (see DESIGN.md in the research folder for their history):
1. one ps snapshot and one tmux pane list;
2. a process is identified by its executable only: ucomm, then argv[0], then a generic runtime's
   entry script; later argv tokens are payload and never identity;
3. launchers (env assignments, shell -c, our aliases) are unwrapped to their first real token;
4. helper invocations (headless flags, helper subcommands, tool runtimes) are never owners;
5. walking down from the pane pid, the first classified process on a branch owns it;
6. a same-family direct chain collapses: a wrapper hands ownership down to the real binary, a
   same-executable child is a clone and the parent keeps it;
7. several owners: keep the single foreground (pgid == tpgid, not stopped) one when all others are
   stopped; otherwise the pane is ambiguous and every candidate is reported.
"""
from __future__ import annotations

import json
import os
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

VERSION_RE = re.compile(r"^\d+(\.\d+)+([.-][0-9A-Za-z]+)*$")


@dataclass
class Proc:
    pid: int
    ppid: int
    ucomm: str
    args: str
    pgid: int = 0
    tpgid: int = 0
    stat: str = ""
    tty: str = ""


@dataclass
class Verdict:
    family: str | None                   # agent family, "unknown" when ambiguous, None for no agent
    owner_pid: int | None = None
    session_hint: str | None = None
    evidence: str = ""
    candidates: list[tuple[int, str]] = field(default_factory=list)
    headless: bool = False               # a one-shot/headless run (e.g. `claude -p`) owns the pane


class Table:
    """The agent table (agents.json) with lookups precomputed."""

    def __init__(self, data: dict):
        self.data = data
        self.shells = set(data.get("shells", ()))
        self.runtimes = set(data.get("runtimes", ()))
        self.tool_runtimes = tuple(data.get("tool_runtimes", ()))
        self.by_exe: dict[str, str] = {}
        self.prefixes: list[tuple[str, str]] = []
        self.entries: list[tuple[str, str]] = []
        self.families = data["families"]
        for fam, spec in self.families.items():
            for name in list(spec.get("executables", ())) + list(spec.get("aliases", ())):
                self.by_exe[name.lower()] = fam
            for prefix in spec.get("executable_prefixes", ()):
                self.prefixes.append((prefix.lower(), fam))
            for pat in spec.get("entry_patterns", ()):
                self.entries.append((pat.lower(), fam))
        self.resume = {fam: [re.compile(p) for p in spec.get("resume_patterns", ())]
                       for fam, spec in self.families.items()}

    @classmethod
    def load(cls, extra: Iterable[Path] = ()) -> "Table":
        data = json.loads((Path(__file__).with_name("agents.json")).read_text())
        for path in extra:
            if path.exists():
                more = json.loads(path.read_text())
                data["families"].update(more.get("families", {}))
                for key in ("shells", "runtimes", "tool_runtimes"):
                    data[key] = sorted(set(data.get(key, [])) | set(more.get(key, [])))
        return cls(data)

    def family_of_exe(self, token: str) -> str | None:
        base = os.path.basename(token).lower()
        if not base:
            return None
        fam = self.by_exe.get(base)
        if fam:
            return fam
        for prefix, fam in self.prefixes:
            if base.startswith(prefix):
                return fam
        return None

    def family_of_entry(self, path: str) -> str | None:
        low = path.lower()
        for pat, fam in self.entries:
            if pat in low:
                return fam
        return None


def _split(args: str) -> list[str]:
    try:
        return shlex.split(args)
    except ValueError:
        return args.split()


def classify(proc: Proc, table: Table) -> tuple[str | None, bool, str]:
    """(family, is_helper, executable token) for one process; family None when not an agent."""
    low = f" {proc.ucomm.lower()} {proc.args.lower()} "
    if any(f" {t} " in low or f"/{t}" in low for t in table.tool_runtimes):
        return None, False, ""
    words = _split(proc.args)
    ucomm = os.path.basename(proc.ucomm)
    ucomm_l = ucomm.lower()
    family = token = None
    rest: list[str] = []

    # 1. ucomm: trusted unless it is a version string (Claude rewrites it; a child ugrep in a
    #    Claude pane carried the same version) or a generic runtime.
    if ucomm and not VERSION_RE.match(ucomm) and ucomm_l not in table.runtimes:
        family = table.family_of_exe(ucomm)
        if family:
            token, rest = ucomm, words[1:]
        elif ucomm_l in table.shells:
            # A shell's argv[0] may be spoofed (exec -a claude bash); only an explicit
            # `shell -c X` / `shell -lic X` names a launched program.
            family, token, rest = _unwrap(words, table)
            if not family:
                return None, False, ""
    # 2. argv[0] when ucomm says nothing useful (version-shaped, truncated, unknown).
    if not family and words:
        first = os.path.basename(words[0]).lower()
        if first in table.runtimes or first.startswith("python"):
            for i, w in enumerate(words[1:], 1):
                if w.startswith("-"):
                    continue
                family = table.family_of_entry(w) or table.family_of_exe(w)
                if family:
                    token, rest = w, words[i + 1:]
                break
            if not family:
                family = table.family_of_entry(proc.ucomm)
                token = proc.ucomm if family else None
        elif first == "env" or first in table.shells:
            family, token, rest = _unwrap(words, table)
        else:
            family = table.family_of_exe(words[0]) or table.family_of_entry(words[0])
            if family:
                token, rest = words[0], words[1:]
    if not family:
        return None, False, ""
    return family, _is_helper(family, rest, table), token or ""


def _unwrap(words: list[str], table: Table) -> tuple[str | None, str | None, list[str]]:
    """env A=1 X … / sh -c 'X …' / zsh -lic 'X …' → the family of X."""
    if not words:
        return None, None, []
    first = os.path.basename(words[0]).lower()
    i = 1
    if first == "env":
        while i < len(words) and ("=" in words[i] or words[i].startswith("-")):
            i += 1
    elif first in table.shells:
        has_c = False
        while i < len(words) and words[i].startswith("-"):
            has_c = has_c or "c" in words[i].lstrip("-")
            i += 1
        if not has_c:
            return None, None, []
        if i < len(words) and " " in words[i]:
            words = words[:i] + _split(words[i]) + words[i + 1:]
        # a script that assigns or execs first: take the first word that is a known executable
        while i < len(words) and ("=" in words[i] or words[i] in ("exec", "command", "builtin")):
            i += 1
    else:
        return None, None, []
    if i >= len(words):
        return None, None, []
    fam = table.family_of_exe(words[i]) or table.family_of_entry(words[i])
    return (fam, words[i], words[i + 1:]) if fam else (None, None, [])


def _is_helper(family: str, rest: list[str], table: Table) -> bool:
    spec = table.families[family]
    flags = spec.get("helper_flags", ())
    tokens = set(spec.get("helper_tokens", ()))
    for w in rest:
        if w in tokens:
            return True
        if any(w == f or w.startswith(f + "=") for f in flags):
            return True
    first = next((w for w in rest if not w.startswith("-")), None)
    return first in spec.get("helper_subcommands", ())


def session_hint(family: str, args: str, table: Table) -> str | None:
    for pat in table.resume.get(family, ()):
        m = pat.search(args)
        if m:
            return m.group(1)
    return None


def resolve(pane_pid: int, procs: dict[int, Proc], table: Table) -> Verdict:
    """Owner of the pane rooted at pane_pid (rules 5-7)."""
    children: dict[int, list[int]] = {}
    for p in procs.values():
        children.setdefault(p.ppid, []).append(p.pid)
    owners: list[tuple[int, str]] = []
    headless: list[tuple[int, str]] = []
    stack, seen = [pane_pid], set()
    while stack:
        pid = stack.pop()
        if pid in seen or pid not in procs:
            continue
        seen.add(pid)
        fam, helper, _ = classify(procs[pid], table)
        if fam:
            # A helper invocation (headless flag, helper subcommand) below another agent is that
            # agent's work. With no agent above it on this branch, it is the pane's own run.
            (headless if helper else owners).append((pid, fam))
            continue
        stack.extend(sorted(children.get(pid, ()), reverse=True))
    one_shot = False
    if not owners and headless:
        owners, one_shot = headless, True
    if not owners:
        return Verdict(None, evidence="no agent process under the pane")
    if len(owners) == 1:
        pid, fam = owners[0]
        return Verdict(fam, pid, session_hint(fam, procs[pid].args, table),
                       f"{fam} {os.path.basename(procs[pid].ucomm) or '?'} pid {pid}"
                       + (" (headless run)" if one_shot else ""), headless=one_shot)
    fg = [o for o in owners if _foreground(procs[o[0]])]
    stopped = [o for o in owners if "T" in procs[o[0]].stat]
    if len(fg) == 1 and len(stopped) == len(owners) - 1:
        pid, fam = fg[0]
        return Verdict(fam, pid, session_hint(fam, procs[pid].args, table),
                       f"{fam} pid {pid} in the foreground; {len(stopped)} stopped", owners)
    desc = ", ".join(f"{fam} {pid}{' (stopped)' if 'T' in procs[pid].stat else ''}" for pid, fam in owners)
    return Verdict("unknown", evidence=f"{len(owners)} owners: {desc}", candidates=owners)


def owner_pid_of(pid: int, fam: str, procs: dict[int, Proc], table: Table) -> int:
    """Follow a same-family direct chain down to the real binary; stop at a same-exe clone."""
    children: dict[int, list[int]] = {}
    for p in procs.values():
        children.setdefault(p.ppid, []).append(p.pid)
    current = pid
    for _ in range(16):
        nxt = None
        cur_exe = os.path.basename(procs[current].ucomm)
        for child in children.get(current, ()):
            cfam, helper, _ = classify(procs[child], table)
            if cfam == fam and not helper:
                if os.path.basename(procs[child].ucomm) == cur_exe:
                    continue                      # clone: the parent keeps ownership
                nxt = child
                break
        if nxt is None:
            return current
        current = nxt
    return current


def _foreground(p: Proc) -> bool:
    return p.pgid > 0 and p.pgid == p.tpgid and "T" not in p.stat


def resolve_pane(pane_pid: int, procs: dict[int, Proc], table: Table) -> Verdict:
    v = resolve(pane_pid, procs, table)
    if v.family not in (None, "unknown") and v.owner_pid is not None:
        deep = owner_pid_of(v.owner_pid, v.family, procs, table)
        if deep != v.owner_pid:
            v.owner_pid = deep
            v.session_hint = v.session_hint or session_hint(v.family, procs[deep].args, table)
            v.evidence += f" -> {os.path.basename(procs[deep].ucomm) or '?'} pid {deep}"
    return v
