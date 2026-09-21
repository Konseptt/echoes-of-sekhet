"""Plot EEG from a LabRecorder .xdf (pyxdf + MNE).

Usage:
  .\\.venv-eeg\\Scripts\\python.exe plot_xdf.py
  .\\.venv-eeg\\Scripts\\python.exe plot_xdf.py path\\to\\recording.xdf
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pyxdf
import mne

DEFAULT_XDF = Path(
    r"C:\Users\Ranjan\Documents\CurrentStudy\sub-P001\ses-S001\eeg"
    r"\sub-P001_ses-S001_task-Default_run-001_eeg.xdf"
)


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_XDF
    if not path.is_file():
        raise SystemExit(f"XDF not found: {path}")

    streams, _ = pyxdf.load_xdf(str(path))

    print("Streams found:")
    for s in streams:
        name = s["info"]["name"][0]
        stype = s["info"]["type"][0]
        n = s["time_series"].shape[0] if hasattr(s["time_series"], "shape") else len(s["time_series"])
        print(f"  {name} | {stype} | samples={n}")

    eeg_streams = [s for s in streams if s["info"]["type"][0] == "EEG"]
    if not eeg_streams:
        raise SystemExit(
            "No EEG stream in this XDF. "
            "Markers-only recording (BrainVision LSL Connector was not selected/recording)."
        )

    eeg = eeg_streams[0]
    data = np.asarray(eeg["time_series"]).T  # channels x samples
    sfreq = float(eeg["info"]["nominal_srate"][0] or 0.0)
    if sfreq <= 0:
        raise SystemExit("EEG stream has no valid nominal_srate")

    n_ch = data.shape[0]
    ch_names = [f"ch{i}" for i in range(n_ch)]
    try:
        chans = eeg["info"]["desc"][0]["channels"][0]["channel"]
        ch_names = [c["label"][0] for c in chans]
    except Exception:
        pass

    # actiCHamp LSL is typically microvolts → volts for MNE
    info = mne.create_info(ch_names=ch_names, sfreq=sfreq, ch_types="eeg")
    raw = mne.io.RawArray(data * 1e-6, info)

    # Attach GLYPHMIND markers if present
    markers = next(
        (s for s in streams if s["info"]["name"][0] == "GLYPHMIND_Markers"),
        None,
    )
    if markers is not None and len(markers["time_stamps"]):
        onset = np.asarray(markers["time_stamps"]) - float(eeg["time_stamps"][0])
        desc = [str(x[0]) for x in markers["time_series"]]
        raw.set_annotations(mne.Annotations(onset=onset, duration=0.0, description=desc))
        print(f"Markers attached: {len(desc)}")

    print(raw)
    raw.plot(
        duration=10,
        n_channels=min(16, n_ch),
        scalings="auto",
        block=True,
    )


if __name__ == "__main__":
    main()
