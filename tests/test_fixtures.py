"""Every fixture is a real (or incident-derived) pane: its process subtree and the expected owner."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from find_agent_pane.core import Proc, Table, classify, resolve_pane  # noqa: E402

FIXTURES = sorted((Path(__file__).parent / "fixtures").glob("*.json"))
TABLE = Table.load()


def load(path):
    d = json.loads(path.read_text())
    procs = {p["pid"]: Proc(p["pid"], p["ppid"], p.get("ucomm", ""), p.get("args", ""),
                            p.get("pgid") or 0, p.get("tpgid") or 0, p.get("stat", ""), p.get("tty", ""))
             for p in d["processes"]}
    root = (d.get("pane") or {}).get("pane_pid")
    if not root or root not in procs:          # non-pane captures: start at the top of the tree
        root = next(p.pid for p in procs.values() if p.ppid not in procs)
    return d, procs, root


@pytest.mark.parametrize("path", FIXTURES, ids=[p.stem for p in FIXTURES])
def test_fixture(path):
    d, procs, root = load(path)
    verdict = resolve_pane(root, procs, TABLE)
    expected = d["expected_family"]
    expected = None if expected in ("shell", "none") else expected
    assert verdict.family == expected, f"{verdict.evidence} | fixture: {d['evidence']}"
    if "expected_owner_pid" in d:
        assert verdict.owner_pid == d["expected_owner_pid"], verdict.evidence


def test_fixture_count():
    assert len(FIXTURES) >= 38


def P(ucomm, args, pid=10, ppid=1):
    return Proc(pid, ppid, ucomm, args)


def test_spoofed_argv0_on_a_shell_is_not_an_agent():
    assert classify(P("bash", "claude --noprofile --norc -i"), TABLE)[0] is None


def test_version_ucomm_defers_to_argv0():
    assert classify(P("2.1.328", "claude --resume x"), TABLE)[0] == "claude"
    assert classify(P("2.1.328", "ugrep -n foo"), TABLE)[0] is None


def test_task_prose_never_identifies():
    assert classify(P("codex", "codex 'ask claude about it'"), TABLE)[0] == "codex"
    assert classify(P("python3", "python3 tool.py --name claude"), TABLE)[0] is None


def test_launcher_unwrap():
    assert classify(P("zsh", "zsh -lic 'ccd --model opus'"), TABLE)[0] == "claude"
    assert classify(P("env", "env FOO=1 BAR=2 codex"), TABLE)[0] == "codex"
    assert classify(P("zsh", "zsh -i"), TABLE)[0] is None


def test_helpers_are_flagged():
    assert classify(P("codex", "codex mcp-server"), TABLE)[1] is True
    assert classify(P("2.1.3", "claude -p hi --output-format stream-json"), TABLE)[1] is True
    assert classify(P("claude", "claude"), TABLE)[1] is False


def test_runtime_entry_scripts():
    assert classify(P("node", "node /x/node_modules/@google/gemini-cli/bundle/gemini.js"), TABLE)[0] == "gemini"
    assert classify(P("node", "node /x/node_modules/@qwen-code/qwen-code/cli-entry.js"), TABLE)[0] == "qwen"
    assert classify(P("node", "node /x/node_modules/@charmland/crush/run-crush.js"), TABLE)[0] == "crush"


def test_session_hint():
    d = {1: P("zsh", "-zsh", 1, 0), 2: P("claude", "claude --resume 9f0c1d2e-aaaa-bbbb-cccc-ddddeeeeffff", 2, 1)}
    assert resolve_pane(1, d, TABLE).session_hint == "9f0c1d2e-aaaa-bbbb-cccc-ddddeeeeffff"
