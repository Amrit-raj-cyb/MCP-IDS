"""Tests for two lab-infrastructure fixes.

Fix #1, uniform client capabilities: the client advertises the sampling
capability in EVERY session, so `initialize` no longer differs with the
mounted servers (it used to reveal the sampling-simulation label: 176 vs 163 bytes).

Fix #2, shutdown records: the MCP SDK kills a proxy that misses its 2 s
shutdown grace period. The proxy now writes `proxy/client_eof` when the client
closes the connection (always before any kill), and on POSIX records
`proxy/stop` (terminated) on SIGTERM. `verify` and the live detector accept a
log that ends with a clean stop OR a client_eof with no unanswered requests.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from detector.detector import read_events_tolerant
from orchestrator.main import DataPaths, run_session, verify
from orchestrator.scenarios import get_scenario
from proxy.reader import CLIENT_CLOSED, INCOMPLETE, STOPPED, UNCLEAN, load_session, log_end_state
from common.registry import PROJECT_ROOT


def _lc(method: str, **body) -> dict:
    return {"method": method, "kind": "lifecycle", "body": body}


# ------------------------------------------------------------ log_end_state

@pytest.mark.parametrize("events,expected", [
    ([_lc("proxy/start"), _lc("proxy/client_eof", unanswered_requests=0),
      _lc("proxy/stop", exit_code=0, unanswered_requests=0)], STOPPED),
    ([_lc("proxy/start"), _lc("proxy/stop", exit_code=None, terminated="SIGTERM", unanswered_requests=0)], STOPPED),
    ([_lc("proxy/start"), _lc("proxy/client_eof", unanswered_requests=0)], CLIENT_CLOSED),
    ([_lc("proxy/start"), _lc("proxy/client_eof", unanswered_requests=2)], UNCLEAN),
    ([_lc("proxy/start"), _lc("proxy/stop", exit_code=1, unanswered_requests=0)], UNCLEAN),
    ([_lc("proxy/start"), _lc("proxy/stop", error="spawn failed")], UNCLEAN),
    ([_lc("proxy/start")], INCOMPLETE),
])
def test_log_end_state(events: list, expected: str) -> None:
    assert log_end_state(events)[0] == expected


# ------------------------------------------- proxy with a slow-to-exit server

# Reads stdin to EOF, then takes 6 s to exit, longer than the SDK's 2 s grace period.
SLOW_SERVER = "import sys, time\nfor _ in sys.stdin.buffer: pass\ntime.sleep(6)\n"


def _events(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_proxy_records_client_eof_and_survives_kill(tmp_path: Path) -> None:
    env = {**os.environ, "MCP_SESSION_ID": "slow", "MCP_LOG_DIR": str(tmp_path), "PYTHONPATH": str(PROJECT_ROOT)}
    proc = subprocess.Popen([sys.executable, "-m", "proxy.proxy", "--server-id", "slow", "--",
                             sys.executable, "-c", SLOW_SERVER],
                            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, env=env, cwd=PROJECT_ROOT)
    log = tmp_path / "slow" / "slow.jsonl"
    proc.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
    proc.stdin.close()                                    # what the SDK does first on shutdown

    deadline = time.monotonic() + 10
    while not any(e["method"] == "proxy/client_eof" for e in _events(log)) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert any(e["method"] == "proxy/client_eof" for e in _events(log)), "client_eof must be written promptly"
    assert proc.poll() is None                            # server is still "shutting down"

    if os.name == "nt":
        proc.kill()                                       # the SDK's Windows behaviour: immediate hard kill
        proc.wait(10)
        state, _ = log_end_state(_events(log))
        assert state == CLIENT_CLOSED
    else:
        proc.send_signal(signal.SIGTERM)                  # the SDK's POSIX behaviour: SIGTERM first
        proc.wait(10)
        stop = [e for e in _events(log) if e["method"] == "proxy/stop"]
        assert len(stop) == 1 and stop[0]["body"]["terminated"] == "SIGTERM"
        assert log_end_state(_events(log))[0] == STOPPED


# ------------------------------------------------ verify + detector accept it

def _drop_lines(path: Path, method: str) -> None:
    keep = [line for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and json.loads(line)["method"] != method]
    path.write_text("\n".join(keep) + "\n", encoding="utf-8")


def test_verify_and_detector_accept_client_closed_logs(tmp_path: Path) -> None:
    paths = DataPaths(tmp_path / "data")
    e = asyncio.run(run_session(get_scenario("benign:multi_region_share"), seed=1, paths=paths))
    assert e.status == "ok" and verify(paths) == []
    sdir = paths.sessions / e.session_id
    files = sorted(sdir.glob("*.jsonl"))

    # Simulate the SDK killing the first proxy after the client closed: no stop event.
    _drop_lines(files[0], "proxy/stop")
    # verify counts events, so the manifest's event count is updated for this simulation.
    _fix_event_count(paths, e.session_id)
    assert verify(paths) == []
    assert read_events_tolerant(sdir)[1:] == (len(files), len(files))   # detector: session complete

    # Lose the client_eof too: genuinely incomplete -> must be reported.
    _drop_lines(files[0], "proxy/client_eof")
    _fix_event_count(paths, e.session_id)
    problems = verify(paths)
    assert len(problems) == 1 and "incomplete" in problems[0]
    assert read_events_tolerant(sdir)[2] == len(files) - 1


def _fix_event_count(paths: DataPaths, session_id: str) -> None:
    rows = [json.loads(line) for line in paths.manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
    for r in rows:
        if r["session_id"] == session_id:
            r["n_log_events"] = len(load_session(session_id, paths.sessions))
    paths.manifest.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


# ---------------------------------------------- uniform client capabilities

def test_initialize_is_identical_regardless_of_mounted_servers(tmp_path: Path) -> None:
    paths = DataPaths(tmp_path / "data")
    sizes, caps = set(), set()
    for scenario in ("benign:calc_add", "benign:fs_sampling_probe", "benign:multi_region_share",
                     "attack:poisoned_tool:calc_add", "attack:shadowing:fs_shadowing_probe",
                     "attack:sampling_injection:fs_sampling_probe"):
        e = asyncio.run(run_session(get_scenario(scenario), seed=3, paths=paths))
        assert e.status == "ok"
        for ev in load_session(e.session_id, paths.sessions):
            if ev["method"] == "initialize" and ev["kind"] == "request":
                sizes.add(ev["message_size"])
                caps.add(tuple(sorted(ev["body"]["params"]["capabilities"])))
    assert caps == {("sampling",)}, "every session must advertise the same client capabilities"
    assert len(sizes) == 1, f"initialize must be byte-identical in size across sessions, got {sizes}"


# ------------------------------------------- late writes after the SDK returns

def _write_line(path: Path, method: str, delay: float = 0.0) -> None:
    import threading

    def go() -> None:
        time.sleep(delay)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"method": method, "kind": "lifecycle"}, separators=(",", ":")) + "\n")
    t = threading.Thread(target=go)
    t.start()
    if not delay:
        t.join()


def test_settle_waits_for_a_late_proxy_stop(tmp_path: Path) -> None:
    from orchestrator.main import settle_session_logs
    d = tmp_path / "s"
    d.mkdir()
    log = d / "srv.jsonl"
    _write_line(log, "proxy/start")
    _write_line(log, "proxy/client_eof")
    _write_line(log, "proxy/stop", delay=0.4)       # proxy still exiting when the SDK returned
    t0 = time.monotonic()
    assert asyncio.run(settle_session_logs(d, quiet=1.0)) == "stopped"
    assert 0.3 < time.monotonic() - t0 < 1.0          # waited for the stop, not the full quiet window
    assert len(log.read_text().splitlines()) == 3


def test_settle_accepts_killed_proxy_after_quiet_period(tmp_path: Path) -> None:
    from orchestrator.main import settle_session_logs
    d = tmp_path / "s"
    d.mkdir()
    _write_line(d / "srv.jsonl", "proxy/client_eof")   # killed after the client finished
    assert asyncio.run(settle_session_logs(d, quiet=0.2)) == "quiet"


def test_settle_times_out_on_unfinished_log(tmp_path: Path) -> None:
    from orchestrator.main import settle_session_logs
    d = tmp_path / "s"
    d.mkdir()
    _write_line(d / "srv.jsonl", "proxy/start")
    assert asyncio.run(settle_session_logs(d, timeout=0.5, quiet=0.1)) == "timeout"


def test_manifest_records_log_end_states(tmp_path: Path) -> None:
    paths = DataPaths(tmp_path / "data")
    e = asyncio.run(run_session(get_scenario("benign:multi_region_share"), seed=1, paths=paths))
    assert e.log_end_states == {"calculator": STOPPED, "filesystem": STOPPED}
    assert verify(paths) == []
