"""Board scripts run with PYTHONPATH unset and stamp laptop time (Phase 0b setup)."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from bench import board

ROOT = Path(__file__).resolve().parent.parent


def test_board_script_drops_pythonpath():
    env = dict(os.environ, PYTHONPATH="/nonexistent/qairt/lib/python")
    p = subprocess.run([sys.executable, "-m", "bench.board", "env"], cwd=ROOT,
                       env=env, capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr
    assert json.loads(p.stdout)["PYTHONPATH"] is None


def test_clean_env_has_no_pythonpath(monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "/x")
    env = board.clean_env()
    assert "PYTHONPATH" not in env and env["PATH"] == os.environ["PATH"]


def test_adb_subprocess_gets_clean_env(monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "/x")
    seen = {}

    def fake_run(cmd, **kw):
        seen.update(kw)
        return subprocess.CompletedProcess(cmd, 0, "cpu-0-0-0 31000\n", "")

    monkeypatch.setattr(board.subprocess, "run", fake_run)
    out = board.chip_temperature()
    assert "PYTHONPATH" not in seen["env"]
    # laptop time: ISO with a UTC offset, and the laptop's year, not the board's
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d{4}", out["t"])
