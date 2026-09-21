#!/usr/bin/env python3
"""
Live LSL viewer: EEG scroll plot + GLYPHMIND markers.

Needs:
  - BrainVision LSL Connector (EEG on LSL)
  - scripts/lsl_marker_bridge.py (GLYPHMIND_Markers on LSL)

Does not record. Run LabRecorder in parallel if you want an .xdf file.

Example:
  source .venv-eeg/bin/activate
  python3 scripts/live_eeg_viewer.py
  python3 scripts/live_eeg_viewer.py --channels 0,1,2 --window 8
"""
from __future__ import annotations

import argparse
import sys
import time
from collections import deque
from typing import Deque, List, Optional, Tuple

import numpy as np

try:
    from pylsl import StreamInlet, resolve_byprop, resolve_streams
except ImportError:
    print("Install deps: pip install -r scripts/requirements-eeg.txt", file=sys.stderr)
    raise

try:
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation
except ImportError:
    print("Install matplotlib: pip install matplotlib", file=sys.stderr)
    raise


MarkerEvent = Tuple[float, str]  # (lsl_time, label)


def resolve_one(prop: str, value: str, timeout: float, kind: str) -> StreamInlet:
    print(f"[live] looking for {kind}: {prop}={value!r} (timeout {timeout:.0f}s)...")
    streams = resolve_byprop(prop, value, timeout=timeout)
    if not streams:
        print(f"[live] no stream with {prop}={value!r}", file=sys.stderr)
        print("[live] streams currently visible:", file=sys.stderr)
        for s in resolve_streams(wait_time=1.0):
            print(
                f"  name={s.name()} type={s.type()} ch={s.channel_count()}",
                file=sys.stderr,
            )
        raise SystemExit(1)
    info = streams[0]
    print(
        f"[live] connected {kind}: name={info.name()} type={info.type()} "
        f"ch={info.channel_count()} rate={info.nominal_srate()}"
    )
    return StreamInlet(info, max_buflen=60, processing_flags=0)


def resolve_eeg(name_substr: str, eeg_type: str, timeout: float) -> StreamInlet:
    if name_substr:
        print(f"[live] looking for EEG name containing {name_substr!r}...")
        deadline = time.time() + timeout
        while time.time() < deadline:
            for s in resolve_streams(wait_time=0.5):
                if name_substr.lower() in (s.name() or "").lower():
                    print(
                        f"[live] connected EEG: name={s.name()} type={s.type()} "
                        f"ch={s.channel_count()} rate={s.nominal_srate()}"
                    )
                    return StreamInlet(s, max_buflen=60, processing_flags=0)
        print(f"[live] no EEG stream name containing {name_substr!r}", file=sys.stderr)
        for s in resolve_streams(wait_time=1.0):
            print(
                f"  name={s.name()} type={s.type()} ch={s.channel_count()}",
                file=sys.stderr,
            )
        raise SystemExit(1)
    return resolve_one("type", eeg_type, timeout, "EEG")


def parse_channels(spec: str, n_available: int) -> List[int]:
    if not spec.strip():
        return list(range(min(4, n_available)))
    idxs = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        i = int(part)
        if i < 0 or i >= n_available:
            raise SystemExit(f"channel {i} out of range 0..{n_available - 1}")
        idxs.append(i)
    if not idxs:
        raise SystemExit("no channels selected")
    return idxs


def main() -> None:
    ap = argparse.ArgumentParser(description="Live EEG + LSL marker viewer")
    ap.add_argument("--eeg-type", default="EEG", help="LSL type for EEG (default: EEG)")
    ap.add_argument(
        "--eeg-name",
        default="",
        help="Optional LSL stream name filter for EEG (substring match)",
    )
    ap.add_argument(
        "--marker-name",
        default="GLYPHMIND_Markers",
        help="LSL marker stream name (default: GLYPHMIND_Markers)",
    )
    ap.add_argument(
        "--channels",
        default="",
        help="Comma-separated channel indices (default: first 4)",
    )
    ap.add_argument(
        "--window",
        type=float,
        default=6.0,
        help="Seconds of EEG shown (default: 6)",
    )
    ap.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="Seconds to wait for streams (default: 20)",
    )
    ap.add_argument(
        "--scale",
        type=float,
        default=50.0,
        help="Vertical spacing between channels in plot units (default: 50)",
    )
    args = ap.parse_args()

    # Resolve EEG
    eeg_inlet = resolve_eeg(args.eeg_name, args.eeg_type, args.timeout)
    eeg_info = eeg_inlet.info()
    n_ch = eeg_info.channel_count()
    srate = float(eeg_info.nominal_srate() or 0.0)
    if srate <= 0:
        srate = 500.0
        print(f"[live] nominal_srate missing; assuming {srate} Hz")

    ch_idxs = parse_channels(args.channels, n_ch)
    ch_names = []
    ch = eeg_info.desc().child("channels").child("channel")
    for i in range(n_ch):
        label = ch.child_value("label") or f"ch{i}"
        ch_names.append(label)
        ch = ch.next_sibling()
    if len(ch_names) < n_ch:
        ch_names = [f"ch{i}" for i in range(n_ch)]

    # Resolve markers (optional but expected)
    marker_inlet: Optional[StreamInlet] = None
    try:
        marker_inlet = resolve_one("name", args.marker_name, args.timeout, "Markers")
    except SystemExit:
        print(
            "[live] continuing without markers. Start lsl_marker_bridge.py to enable them.",
            file=sys.stderr,
        )

    window_s = max(1.0, args.window)
    max_samples = int(window_s * srate) + 10
    buffers: List[Deque[float]] = [deque(maxlen=max_samples) for _ in ch_idxs]
    times: Deque[float] = deque(maxlen=max_samples)
    markers: Deque[MarkerEvent] = deque(maxlen=200)

    t0 = time.time()
    last_eeg_time: Optional[float] = None

    fig, ax = plt.subplots(figsize=(12, 6))
    fig.canvas.manager.set_window_title("GLYPHMIND live EEG + markers")
    lines = []
    for i, ci in enumerate(ch_idxs):
        (ln,) = ax.plot([], [], lw=0.8, label=ch_names[ci] if ci < len(ch_names) else f"ch{ci}")
        lines.append(ln)

    marker_vlines = []
    marker_texts = []
    status = ax.text(
        0.01,
        0.99,
        "",
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontsize=9,
        family="monospace",
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
    )

    ax.set_xlabel("time (s, relative)")
    ax.set_ylabel("channels (offset)")
    ax.set_title("Live EEG (LSL) with game markers")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, alpha=0.25)

    def pull_eeg() -> None:
        nonlocal last_eeg_time
        # Pull in chunks
        samples, timestamps = eeg_inlet.pull_chunk(timeout=0.0, max_samples=1024)
        if not timestamps:
            return
        for sample, ts in zip(samples, timestamps):
            times.append(float(ts))
            last_eeg_time = float(ts)
            for bi, ci in enumerate(ch_idxs):
                buffers[bi].append(float(sample[ci]))

    def pull_markers() -> None:
        if marker_inlet is None:
            return
        while True:
            sample, ts = marker_inlet.pull_sample(timeout=0.0)
            if ts is None:
                break
            label = sample[0] if sample else ""
            if isinstance(label, (bytes, bytearray)):
                label = label.decode("utf-8", errors="replace")
            markers.append((float(ts), str(label)))
            print(f"[marker] {ts:.3f}  {label}")

    def update(_frame):
        pull_eeg()
        pull_markers()

        # Clear old artists
        while marker_vlines:
            marker_vlines.pop().remove()
        while marker_texts:
            marker_texts.pop().remove()

        if not times:
            status.set_text("waiting for EEG samples...")
            return lines + [status]

        t_arr = np.asarray(times, dtype=float)
        t_end = t_arr[-1]
        t_start = t_end - window_s
        rel = t_arr - t_end

        for bi, ln in enumerate(lines):
            y = np.asarray(buffers[bi], dtype=float)
            if y.size != rel.size:
                n = min(y.size, rel.size)
                ln.set_data(rel[-n:], y[-n:] + bi * args.scale)
            else:
                ln.set_data(rel, y + bi * args.scale)

        # Markers in window
        recent = [m for m in markers if m[0] >= t_start]
        for ts, label in recent[-12:]:
            x = ts - t_end
            vl = ax.axvline(x, color="crimson", alpha=0.75, lw=1.2)
            marker_vlines.append(vl)
            short = label if len(label) <= 40 else label[:37] + "..."
            txt = ax.text(
                x,
                (len(ch_idxs) - 0.3) * args.scale,
                short,
                rotation=90,
                va="top",
                ha="right",
                fontsize=7,
                color="crimson",
            )
            marker_texts.append(txt)

        ax.set_xlim(-window_s, 0.2)
        ymin = -args.scale * 0.8
        ymax = args.scale * (len(ch_idxs) - 0.2)
        ax.set_ylim(ymin, ymax)

        age = time.time() - t0
        n_mark = len(recent)
        status.set_text(
            f"EEG {srate:.0f} Hz | ch {','.join(str(i) for i in ch_idxs)} | "
            f"markers in view: {n_mark} | running {age:.0f}s"
        )
        return lines + marker_vlines + marker_texts + [status]

    print("[live] window open. Close the plot window to quit.")
    print("[live] LabRecorder can record the same streams at the same time.")
    _anim = FuncAnimation(fig, update, interval=50, blit=False, cache_frame_data=False)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
