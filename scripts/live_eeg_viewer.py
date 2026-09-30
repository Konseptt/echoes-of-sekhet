#!/usr/bin/env python3
"""
Live LSL viewer: EEG scroll plot + GLYPHMIND markers.

Needs:
  - BrainVision LSL Connector (EEG on LSL)
  - scripts/lsl_marker_bridge.py (GLYPHMIND_Markers on LSL)

Usage:
  python scripts/live_eeg_viewer.py
  python scripts/live_eeg_viewer.py --montage all
  python scripts/live_eeg_viewer.py --channels 0,1,2,3 --window 8
"""
from __future__ import annotations

import argparse
import sys
import time
from collections import deque
from typing import Deque, Dict, List, Optional, Tuple

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

# Standard actiCAP 32 montage with brain regions and functions
CHANNEL_CATALOG: Dict[int, Tuple[str, str]] = {
    0:  ("Fp1",  "Frontopolar L / Blink"),
    1:  ("Fp2",  "Frontopolar R / Blink"),
    2:  ("F3",   "Frontal L / DLPFC"),
    3:  ("F4",   "Frontal R / DLPFC"),
    4:  ("C3",   "Central L / Motor"),
    5:  ("C4",   "Central R / Motor"),
    6:  ("P3",   "Parietal L / Memory"),
    7:  ("P4",   "Parietal R / Memory"),
    8:  ("O1",   "Occipital L / Visual"),
    9:  ("O2",   "Occipital R / Visual"),
    10: ("F7",   "Frontolateral L"),
    11: ("F8",   "Frontolateral R"),
    12: ("T7",   "Temporal L / Auditory"),
    13: ("T8",   "Temporal R / Auditory"),
    14: ("P7",   "Temporoparietal L"),
    15: ("P8",   "Temporoparietal R"),
    16: ("Fz",   "Frontal Midline"),
    17: ("Cz",   "Central Midline / Vertex"),
    18: ("Pz",   "Parietal Midline / P300"),
    19: ("Oz",   "Occipital Midline / Visual"),
    20: ("FC1",  "Frontocentral L"),
    21: ("FC2",  "Frontocentral R"),
    22: ("CP1",  "Centroparietal L"),
    23: ("CP2",  "Centroparietal R"),
    24: ("FC5",  "Frontocentral L-Lat"),
    25: ("FC6",  "Frontocentral R-Lat"),
    26: ("CP5",  "Centroparietal L-Lat"),
    27: ("CP6",  "Centroparietal R-Lat"),
    28: ("TP9",  "Mastoid Ref L"),
    29: ("TP10", "Mastoid Ref R"),
    30: ("POz",  "Parieto-occipital Midline"),
    31: ("ECG",  "Cardiac / AUX"),
}
for i in range(32, 40):
    CHANNEL_CATALOG[i] = (f"AUX{i-31}", f"Auxiliary / Trigger {i-31}")

# Core working memory and visual montage for N-back
NBACK_CHANNELS = [0, 1, 2, 3, 16, 17, 4, 5, 6, 7, 18, 8, 9, 19]


def get_channel_label(i: int, short: bool = False) -> str:
    if i in CHANNEL_CATALOG:
        name, desc = CHANNEL_CATALOG[i]
        return f"{name}" if short else f"{name} ({desc})"
    return f"Ch{i+1}"


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


def detect_all_active_channels(inlet: StreamInlet, n_ch: int) -> List[int]:
    """Sample a short chunk and detect channels with active variance."""
    samples, _ = inlet.pull_chunk(timeout=0.8, max_samples=1000)
    if not samples:
        return list(range(min(32, n_ch)))
    data = np.asarray(samples)
    stds = np.std(data, axis=0)
    active = [i for i in range(min(32, n_ch)) if stds[i] > 0.1]
    return active if active else list(range(min(8, n_ch)))


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
        "--montage",
        choices=["all", "active", "nback", "custom"],
        default="all",
        help="Montage preset: 'all', 'active', 'nback', or 'custom'",
    )
    ap.add_argument(
        "--channels",
        default="",
        help="Comma-separated channel indices if montage=custom (e.g. 0,1,2,3)",
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
        default=0.0,
        help="Vertical spacing between channels in uV (default: auto)",
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

    def select_channels_for_mode(mode: str) -> List[int]:
        if mode == "all":
            return list(range(min(32, n_ch)))
        elif mode == "active":
            return detect_all_active_channels(eeg_inlet, n_ch)
        elif mode == "nback":
            return [i for i in NBACK_CHANNELS if i < n_ch]
        elif mode == "custom":
            if args.channels.strip():
                idxs = [int(p.strip()) for p in args.channels.split(",") if p.strip()]
                return [i for i in idxs if 0 <= i < n_ch]
            return list(range(min(4, n_ch)))
        return list(range(min(32, n_ch)))

    current_mode = args.montage
    ch_idxs = select_channels_for_mode(current_mode)

    scale = args.scale
    if scale <= 0.0:
        if len(ch_idxs) > 20:
            scale = 35.0
        elif len(ch_idxs) > 10:
            scale = 50.0
        else:
            scale = 75.0

    print(f"\n[live] actiCHamp connected ({srate:.0f} Hz, {n_ch} channels)")
    print(f"[live] montage: {current_mode.upper()} ({len(ch_idxs)} channels)")
    for ci in ch_idxs:
        print(f"  [{ci:2d}] {get_channel_label(ci)}")

    # Resolve markers
    marker_inlet: Optional[StreamInlet] = None
    try:
        found_markers = resolve_byprop("name", args.marker_name, timeout=1.0)
        if found_markers:
            marker_inlet = StreamInlet(found_markers[0], max_buflen=60, processing_flags=0)
            print(f"[live] connected markers: {args.marker_name}")
    except Exception:
        pass
    if marker_inlet is None:
        print("[live] marker stream not detected yet; will attach when game starts.")

    window_s = max(1.0, args.window)
    max_samples = int(window_s * srate) + 100

    hardware_buffers: List[Deque[float]] = [deque(maxlen=max_samples) for _ in range(n_ch)]
    times: Deque[float] = deque(maxlen=max_samples)
    markers: Deque[MarkerEvent] = deque(maxlen=400)

    decimate_step = max(1, int(srate / 250.0))
    last_marker_display = ""
    is_paused = False

    fig = plt.figure(figsize=(15, 9))
    fig.canvas.manager.set_window_title("GLYPHMIND - Live actiCHamp EEG + Markers")
    ax = fig.add_subplot(111)

    lines: List[plt.Line2D] = []

    def rebuild_plot_lines():
        nonlocal lines, scale
        ax.clear()
        lines = []
        for i, ci in enumerate(ch_idxs):
            lbl = get_channel_label(ci, short=True)
            (ln,) = ax.plot([], [], lw=0.9, label=lbl)
            lines.append(ln)

        y_ticks = [i * scale for i in range(len(ch_idxs))]
        y_labels = [get_channel_label(ci, short=False) for ci in ch_idxs]
        ax.set_yticks(y_ticks)
        ax.set_yticklabels(y_labels, fontsize=8)

        ax.set_xlim(-window_s, 0.2)
        ax.set_ylim(-scale * 0.8, (len(ch_idxs) - 0.2) * scale)
        ax.set_xlabel("Time (seconds relative to now)", fontsize=9)
        ax.set_title(
            f"actiCHamp EEG ({srate:.0f} Hz) | Montage: {current_mode.upper()} ({len(ch_idxs)} ch) | Scale: {scale:.0f} uV\n"
            f"[Keys: 'a' All 32 | 'g' Active | 'n' N-back | '+' / '-' Scale | Space Pause]",
            fontsize=10,
            pad=10
        )
        ax.grid(True, alpha=0.2, linestyle="--")

    rebuild_plot_lines()

    marker_vlines: List[plt.Line2D] = []
    marker_texts: List[plt.Text] = []

    def on_key(event):
        nonlocal current_mode, ch_idxs, scale, is_paused
        if event.key in ('+', '='):
            scale *= 1.25
            rebuild_plot_lines()
        elif event.key in ('-', '_'):
            scale = max(5.0, scale / 1.25)
            rebuild_plot_lines()
        elif event.key == 'a':
            current_mode = "all"
            ch_idxs = select_channels_for_mode("all")
            if scale > 40.0:
                scale = 35.0
            rebuild_plot_lines()
        elif event.key == 'g':
            current_mode = "active"
            ch_idxs = select_channels_for_mode("active")
            scale = 50.0
            rebuild_plot_lines()
        elif event.key == 'n':
            current_mode = "nback"
            ch_idxs = select_channels_for_mode("nback")
            scale = 50.0
            rebuild_plot_lines()
        elif event.key == ' ':
            is_paused = not is_paused

    fig.canvas.mpl_connect('key_press_event', on_key)

    def pull_eeg() -> None:
        samples, timestamps = eeg_inlet.pull_chunk(timeout=0.0, max_samples=2048)
        if not timestamps:
            return
        for sample, ts in zip(samples, timestamps):
            times.append(float(ts))
            for ci in range(min(n_ch, len(sample))):
                hardware_buffers[ci].append(float(sample[ci]))

    def pull_markers() -> None:
        nonlocal marker_inlet, last_marker_display
        if marker_inlet is None:
            try:
                found = resolve_byprop("name", args.marker_name, timeout=0.0)
                if found:
                    marker_inlet = StreamInlet(found[0], max_buflen=60, processing_flags=0)
                    print(f"[live] attached to marker stream: {args.marker_name}")
            except Exception:
                return

        while True:
            sample, ts = marker_inlet.pull_sample(timeout=0.0)
            if ts is None:
                break
            label = sample[0] if sample else ""
            if isinstance(label, (bytes, bytearray)):
                label = label.decode("utf-8", errors="replace")
            markers.append((float(ts), str(label)))
            last_marker_display = str(label)
            print(f">>> [MARKER] {label} (ts={ts:.3f})")

    def update(_frame):
        pull_eeg()
        pull_markers()

        if is_paused or not times:
            return lines

        while marker_vlines:
            marker_vlines.pop().remove()
        while marker_texts:
            marker_texts.pop().remove()

        t_arr = np.asarray(times, dtype=float)
        t_end = t_arr[-1]
        t_start = t_end - window_s
        rel = t_arr - t_end

        rel_disp = rel[::decimate_step]

        for bi, ci in enumerate(ch_idxs):
            if bi >= len(lines):
                break
            y_raw = np.asarray(hardware_buffers[ci], dtype=float)
            if y_raw.size == 0:
                continue

            y_centered = y_raw - np.median(y_raw)
            y_disp = y_centered[::decimate_step]

            n = min(rel_disp.size, y_disp.size)
            if n > 0:
                lines[bi].set_data(rel_disp[-n:], y_disp[-n:] + bi * scale)

        recent = [m for m in markers if m[0] >= t_start - 0.2]
        for ts, label in recent[-16:]:
            x = ts - t_end
            if x < -window_s or x > 0.2:
                continue
            vl = ax.axvline(x, color="#d90429", alpha=0.85, lw=1.8, linestyle="--")
            marker_vlines.append(vl)

            parts = label.split(":")
            short = f"{parts[1]} ({parts[3]})" if len(parts) >= 4 else (label[:20] + "..." if len(label) > 20 else label)

            txt = ax.text(
                x,
                (len(ch_idxs) - 0.3) * scale,
                short,
                rotation=90,
                va="top",
                ha="right",
                fontsize=8,
                fontweight="bold",
                color="#d90429",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="#ffebee", edgecolor="#d90429", alpha=0.9),
            )
            marker_texts.append(txt)

        return lines + marker_vlines + marker_texts

    print("\n[live] window open. Press 'a' all, 'g' active, 'n' n-back, '+/-' scale, space pause.\n")
    _anim = FuncAnimation(fig, update, interval=40, blit=False, cache_frame_data=False)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
