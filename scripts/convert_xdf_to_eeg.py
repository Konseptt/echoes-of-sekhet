#!/usr/bin/env python3
"""
Convert LabRecorder .xdf to BrainVision, EEGLAB, EDF, or FIF.

Usage:
  python scripts/convert_xdf_to_eeg.py path/to/recording.xdf --format vhdr
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

try:
    import pyxdf
except ImportError:
    print("Install pyxdf: pip install pyxdf", file=sys.stderr)
    raise

try:
    import mne
except ImportError:
    print("Install mne: pip install mne", file=sys.stderr)
    raise

ACTICAP_32 = [
    "Fp1", "Fp2", "F3", "F4", "C3", "C4", "P3", "P4",
    "O1", "O2", "F7", "F8", "T7", "T8", "P7", "P8",
    "Fz", "Cz", "Pz", "Oz", "FC1", "FC2", "CP1", "CP2",
    "FC5", "FC6", "CP5", "CP6", "TP9", "TP10", "POz", "ECG"
]


def load_xdf_as_raw(xdf_path: Path) -> mne.io.RawArray:
    if not xdf_path.is_file():
        raise SystemExit(f"File not found: {xdf_path}")

    print(f"[convert] Loading XDF: {xdf_path.name}")
    streams, _ = pyxdf.load_xdf(str(xdf_path))

    eeg_streams = [s for s in streams if s["info"]["type"][0] == "EEG"]
    if not eeg_streams:
        raise SystemExit("Error: No EEG stream found in this XDF.")

    eeg = eeg_streams[0]
    data = np.asarray(eeg["time_series"]).T
    sfreq = float(eeg["info"]["nominal_srate"][0] or 0.0)
    if sfreq <= 0:
        raise SystemExit("Error: EEG stream nominal_srate is 0")

    n_ch = data.shape[0]

    ch_names = []
    try:
        chans = eeg["info"]["desc"][0]["channels"][0]["channel"]
        ch_names = [c["label"][0] for c in chans if c.get("label")]
    except Exception:
        pass

    if len(ch_names) < n_ch:
        ch_names = []
        for i in range(n_ch):
            if i < len(ACTICAP_32):
                ch_names.append(ACTICAP_32[i])
            else:
                ch_names.append(f"AUX{i - 31}")

    print(f"[convert] {n_ch} channels @ {sfreq:.0f} Hz ({data.shape[1]} samples)")

    info = mne.create_info(ch_names=ch_names, sfreq=sfreq, ch_types="eeg")
    raw = mne.io.RawArray(data * 1e-6, info)

    markers = next((s for s in streams if "Marker" in s["info"]["type"][0] or "GLYPHMIND" in s["info"]["name"][0]), None)
    if markers is not None and len(markers["time_stamps"]):
        onset = np.asarray(markers["time_stamps"]) - float(eeg["time_stamps"][0])
        desc = [str(x[0]) if isinstance(x, (list, tuple)) else str(x) for x in markers["time_series"]]
        valid = onset >= 0
        raw.set_annotations(mne.Annotations(onset=onset[valid], duration=np.zeros(np.sum(valid)), description=np.asarray(desc)[valid]))
        print(f"[convert] Attached {np.sum(valid)} markers")
    else:
        print("[convert] No marker stream found in XDF")

    return raw


def main():
    ap = argparse.ArgumentParser(description="Convert LabRecorder .xdf to standard EEG formats")
    ap.add_argument("xdf_file", help="Path to input .xdf file")
    ap.add_argument("--format", choices=["vhdr", "set", "edf", "fif"], default="vhdr",
                    help="Target format: vhdr, set, edf, fif")
    ap.add_argument("-o", "--output", default="", help="Output filename")
    args = ap.parse_args()

    xdf_path = Path(args.xdf_file)
    raw = load_xdf_as_raw(xdf_path)

    stem = xdf_path.stem
    parent = xdf_path.parent

    if args.format == "vhdr":
        out_path = Path(args.output) if args.output else parent / f"{stem}.vhdr"
        raw.export(str(out_path), fmt="brainvision", overwrite=True)
        print(f"[convert] Created {out_path}")
    elif args.format == "set":
        out_path = Path(args.output) if args.output else parent / f"{stem}.set"
        raw.export(str(out_path), fmt="eeglab", overwrite=True)
        print(f"[convert] Created {out_path}")
    elif args.format == "edf":
        out_path = Path(args.output) if args.output else parent / f"{stem}.edf"
        raw.export(str(out_path), fmt="edf", overwrite=True)
        print(f"[convert] Created {out_path}")
    elif args.format == "fif":
        out_path = Path(args.output) if args.output else parent / f"{stem}_raw.fif"
        raw.save(str(out_path), overwrite=True)
        print(f"[convert] Created {out_path}")


if __name__ == "__main__":
    main()
