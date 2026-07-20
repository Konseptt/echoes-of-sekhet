#!/usr/bin/env python3
"""
WebSocket → LSL marker outlet for Echoes of Sekhet (GLYPHMIND protocol).

The browser game cannot open LSL sockets directly. This bridge receives JSON
marker messages over WebSocket and pushes them into an LSL Marker stream that
LabRecorder / BrainVision can record alongside actiCHamp EEG.

Usage:
  pip install -r scripts/requirements-eeg.txt
  python3 scripts/lsl_marker_bridge.py
  python3 scripts/lsl_marker_bridge.py --port 8765 --log markers.csv
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from pylsl import StreamInfo, StreamOutlet
except ImportError:
    print("Install dependencies: pip install -r scripts/requirements-eeg.txt", file=sys.stderr)
    raise

try:
    import websockets
except ImportError:
    print("Install dependencies: pip install -r scripts/requirements-eeg.txt", file=sys.stderr)
    raise

STREAM_NAME = "GLYPHMIND_Markers"
STREAM_TYPE = "Markers"
SOURCE_ID = "glyphmind-echoes-of-sekhet-v1"


def make_outlet() -> StreamOutlet:
    info = StreamInfo(
        name=STREAM_NAME,
        type=STREAM_TYPE,
        channel_count=1,
        nominal_srate=0,
        channel_format="string",
        source_id=SOURCE_ID,
    )
    info.desc().append_child_value("manufacturer", "Echoes of Sekhet")
    info.desc().append_child_value("protocol", "GLYPHMIND")
    return StreamOutlet(info)


def format_marker(payload: dict) -> str:
    code = payload.get("code", "")
    label = payload.get("label", "")
    return f"{code}:{label}"


class MarkerLogger:
    def __init__(self, path: Path | None) -> None:
        self.path = path
        self._file = None
        self._writer = None
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            new_file = not path.exists()
            self._file = path.open("a", newline="", encoding="utf-8")
            self._writer = csv.writer(self._file)
            if new_file:
                self._writer.writerow(
                    [
                        "received_iso",
                        "code",
                        "label",
                        "perf_ms",
                        "wall_iso",
                        "pid",
                        "session",
                        "block",
                        "trial",
                        "nback",
                        "raw_json",
                    ]
                )

    def write(self, payload: dict, marker: str) -> None:
        if not self._writer:
            return
        self._writer.writerow(
            [
                datetime.now(timezone.utc).isoformat(),
                payload.get("code", ""),
                payload.get("label", ""),
                payload.get("perfMs", ""),
                payload.get("wallIso", ""),
                payload.get("pid", ""),
                payload.get("session", ""),
                payload.get("block", ""),
                payload.get("trial", ""),
                payload.get("nback", ""),
                json.dumps(payload, separators=(",", ":")),
            ]
        )
        self._file.flush()

    def close(self) -> None:
        if self._file:
            self._file.close()


async def handle_client(websocket, outlet: StreamOutlet, logger: MarkerLogger) -> None:
    peer = websocket.remote_address
    print(f"[bridge] client connected: {peer}")
    try:
        async for message in websocket:
            try:
                payload = json.loads(message)
            except json.JSONDecodeError:
                print(f"[bridge] invalid JSON from {peer}: {message[:120]!r}")
                continue

            if payload.get("type") != "marker":
                continue

            marker = format_marker(payload)
            outlet.push_sample([marker])
            logger.write(payload, marker)
            print(f"[bridge] {marker}  pid={payload.get('pid', '')} trial={payload.get('trial', '')}")
    finally:
        print(f"[bridge] client disconnected: {peer}")


async def main_async(host: str, port: int, log_path: Path | None) -> None:
    outlet = make_outlet()
    logger = MarkerLogger(log_path)
    print(f"[bridge] LSL outlet ready: {STREAM_NAME} ({STREAM_TYPE})")
    print(f"[bridge] WebSocket listening on ws://{host}:{port}")
    if log_path:
        print(f"[bridge] CSV log: {log_path}")

    async with websockets.serve(
        lambda ws: handle_client(ws, outlet, logger),
        host,
        port,
        ping_interval=20,
        ping_timeout=20,
    ):
        await asyncio.Future()


def main() -> None:
    parser = argparse.ArgumentParser(description="Echoes of Sekhet WebSocket → LSL marker bridge")
    parser.add_argument("--host", default="127.0.0.1", help="WebSocket bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="WebSocket port (default: 8765)")
    parser.add_argument(
        "--log",
        default="",
        help="Optional CSV path for marker backup log (default: none)",
    )
    args = parser.parse_args()
    log_path = Path(args.log) if args.log else None
    try:
        asyncio.run(main_async(args.host, args.port, log_path))
    except KeyboardInterrupt:
        print("\n[bridge] stopped")


if __name__ == "__main__":
    main()
