#!/usr/bin/env python3
"""Start the GLYPHMIND browser, marker bridge, and live EEG viewer together.

BrainVision LSL Connector and LabRecorder remain operator-controlled because
they require hardware selection and recording-file confirmation.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

try:
    from pylsl import resolve_streams
except ImportError:
    print(
        "pylsl is required. Install with: "
        "python -m pip install -r scripts/requirements-eeg.txt",
        file=sys.stderr,
    )
    raise SystemExit(2)


ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "logs"


def command_python() -> str:
    venv_python = ROOT / ".venv-eeg" / ("Scripts" if sys.platform == "win32" else "bin") / (
        "python.exe" if sys.platform == "win32" else "python"
    )
    return str(venv_python) if venv_python.exists() else sys.executable


def find_eeg(timeout: float):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        streams = [
            stream
            for stream in resolve_streams(wait_time=min(2.0, max(0.1, deadline - time.monotonic())))
            if (stream.type() or "").strip().lower() == "eeg"
        ]
        if streams:
            return streams[0]
    return None


def stop_process(process: subprocess.Popen[bytes] | None, name: str) -> None:
    if process is None or process.poll() is not None:
        return
    print(f"[run] stopping {name}...", flush=True)
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def main() -> int:
    parser = argparse.ArgumentParser(description="Start the complete GLYPHMIND local experiment setup")
    parser.add_argument("--port", type=int, default=4173, help="Game server port")
    parser.add_argument("--bridge-port", type=int, default=8765, help="Marker bridge WebSocket port")
    parser.add_argument("--eeg-name", default="", help="Optional substring filter for the EEG LSL stream")
    parser.add_argument("--eeg-timeout", type=float, default=30.0, help="Seconds to wait for an EEG stream")
    parser.add_argument("--montage", choices=("all", "active", "nback"), default="all")
    parser.add_argument("--window", type=float, default=6.0)
    args = parser.parse_args()

    python = command_python()
    bridge = server = viewer = None
    LOG_DIR.mkdir(exist_ok=True)

    try:
        print("[run] checking for a real EEG LSL stream...", flush=True)
        eeg = find_eeg(args.eeg_timeout)
        if eeg is None:
            print(
                "[run] no EEG stream found. Start BrainVision LSL Connector and "
                "confirm LiveAmp is streaming, then run this command again.",
                file=sys.stderr,
            )
            return 1
        if args.eeg_name and args.eeg_name.lower() not in (eeg.name() or "").lower():
            print(
                f"[run] EEG stream {eeg.name()!r} does not match --eeg-name {args.eeg_name!r}.",
                file=sys.stderr,
            )
            return 1
        print(
            f"[run] EEG: {eeg.name()} | {eeg.channel_count()} channels | "
            f"{eeg.nominal_srate():.0f} Hz",
            flush=True,
        )

        bridge = subprocess.Popen(
            [
                python,
                str(ROOT / "scripts" / "lsl_marker_bridge.py"),
                "--host",
                "127.0.0.1",
                "--port",
                str(args.bridge_port),
                "--log",
                str(LOG_DIR / "markers.csv"),
            ],
            cwd=ROOT,
        )
        server = subprocess.Popen(
            [sys.executable, "-m", "http.server", str(args.port), "--bind", "127.0.0.1"],
            cwd=ROOT,
        )
        time.sleep(1)
        if bridge.poll() is not None:
            raise RuntimeError("marker bridge exited during startup")
        if server.poll() is not None:
            raise RuntimeError("game server exited during startup")

        viewer = subprocess.Popen(
            [
                python,
                str(ROOT / "scripts" / "live_eeg_viewer.py"),
                "--eeg-name",
                eeg.name(),
                "--montage",
                args.montage,
                "--window",
                str(args.window),
                "--timeout",
                "10",
            ],
            cwd=ROOT,
        )
        webbrowser.open(f"http://127.0.0.1:{args.port}/")
        print("[run] game: http://127.0.0.1:{0}/".format(args.port), flush=True)
        print("[run] press Ctrl+C here after the session to stop all local services.", flush=True)
        while True:
            if viewer.poll() is not None:
                return viewer.returncode or 0
            if bridge.poll() is not None:
                raise RuntimeError("marker bridge stopped unexpectedly")
            if server.poll() is not None:
                raise RuntimeError("game server stopped unexpectedly")
            time.sleep(1)
    except KeyboardInterrupt:
        return 0
    finally:
        stop_process(viewer, "live EEG viewer")
        stop_process(server, "game server")
        stop_process(bridge, "marker bridge")


if __name__ == "__main__":
    raise SystemExit(main())
