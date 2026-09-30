"""Plot EEG from a LabRecorder .xdf (pyxdf + MNE).

Usage:
  python plot_xdf.py
  python plot_xdf.py path/to/recording.xdf
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

ACTICAP_32 = [
    "Fp1", "Fp2", "F3", "F4", "C3", "C4", "P3", "P4",
    "O1", "O2", "F7", "F8", "T7", "T8", "P7", "P8",
    "Fz", "Cz", "Pz", "Oz", "FC1", "FC2", "CP1", "CP2",
    "FC5", "FC6", "CP5", "CP6", "TP9", "TP10", "POz", "ECG"
]


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

    # Resolve channel labels
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

    # Baseline correction for DC offset
    for i in range(n_ch):
        data[i] -= np.median(data[i])

    # actiCHamp LSL is typically microvolts -> volts for MNE
    info = mne.create_info(ch_names=ch_names, sfreq=sfreq, ch_types="eeg")
    raw = mne.io.RawArray(data * 1e-6, info)

    # Attach GLYPHMIND markers if present
    markers = next(
        (s for s in streams if s["info"]["name"][0] == "GLYPHMIND_Markers"),
        None,
    )
    if markers is None:
        markers = next(
            (s for s in streams if "Marker" in s["info"]["type"][0]),
            None,
        )

    if markers is not None and len(markers["time_stamps"]):
        onset = np.asarray(markers["time_stamps"]) - float(eeg["time_stamps"][0])
        desc = [str(x[0]) if isinstance(x, (list, tuple)) else str(x) for x in markers["time_series"]]
        valid = onset >= 0
        raw.set_annotations(mne.Annotations(
            onset=onset[valid],
            duration=np.zeros(np.sum(valid)),
            description=np.asarray(desc)[valid]
        ))
        print(f"Markers attached: {np.sum(valid)}")
    else:
        print("Warning: No marker stream found in this XDF.")

    print(raw)
    raw.plot(
        duration=10,
        n_channels=min(20, n_ch),
        scalings=dict(eeg=80e-6),
        block=True,
    )


if __name__ == "__main__":
    main()
