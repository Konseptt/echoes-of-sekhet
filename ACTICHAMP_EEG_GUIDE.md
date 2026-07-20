# Echoes of Sekhet - actiCHamp EEG Integration Guide

This guide explains how to run **Echoes of Sekhet** (GLYPHMIND protocol) with a **Brain Products actiCHamp** system for research-grade synchronized recording.

## Overview

| Layer | Role |
|--------|------|
| **actiCHamp + BrainVision LSL Connector** | Records EEG at amplifier sample rate |
| **LSL marker bridge** (`scripts/lsl_marker_bridge.py`) | Receives trial markers from the browser and publishes an LSL `Markers` stream |
| **LabRecorder** (or BrainVision Recorder) | Records EEG + marker streams with LSL timestamps |
| **Photodiode (bottom-right square)** | Hardware backup for stimulus onset - place an optical sensor on the black square |

Browsers cannot speak LSL directly. The included Python bridge is the recommended path used in many LSL labs (same pattern as Brain Products’ own WebSocket examples).

---

## 1. Hardware checklist

1. **actiCHamp (Plus)** powered on, electrodes impedance-checked per your lab SOP.
2. **Trigger path (choose one or combine):**
 - **Software markers (primary):** LSL marker bridge + LabRecorder (no extra wiring).
 - **Hardware trigger (optional):** actiCHamp trigger input via TriggerBox / Sensor & Trigger Extension (STE).
3. **Photodiode backup (recommended):**
 - Affix a photodiode to the **bottom-right black square** on the game monitor (`#photodiode`).
 - Keep **TRIAL FLASH MARKER** enabled in Accessibility (on by default).
 - The square flashes white for ~120 ms on every gate reveal (stimulus onset).
4. **Dedicated fullscreen display** for the participant; researcher uses a second screen for setup.

---

## 2. Software install (once per machine)

### 2.1 BrainVision LSL Connector (actiCHamp)

Download the current **BrainVision LSL Connector for actiCHamp** from Brain Products (not the deprecated GitHub build):

- [Brain Products LSL support page](https://www.brainproducts.com/support-resources/tips-and-tricks-for-lsl/)
- [BrainVision LSL tools announcement](https://pressrelease.brainproducts.com/brainvision-lsl-tools/)

**Recommended trigger settings in the connector:**

| Setting | Recommendation |
|---------|----------------|
| **EEG Channel triggers** | Enable if you use hardware photodiode → amplifier trigger input (best timing precision) |
| **Unsampled String Markers** | Enable for hardware triggers and/or separate marker devices |
| **Sampling rate** | Your study rate (e.g. 500 Hz or 1000 Hz) |

Save a connector configuration file (`.lslconfig`) for repeatability.

### 2.2 LabRecorder

Install [LabRecorder](https://github.com/labstreaminglayer/App-LabRecorder) to record multiple LSL streams into one `.xdf` file.

### 2.3 Marker bridge (this repository)

```bash
cd /path/to/glyphmind-lab-version-main
python3 -m venv .venv-eeg
source .venv-eeg/bin/activate   # Windows: .venv-eeg\Scripts\activate
pip install -r scripts/requirements-eeg.txt
```

---

## 3. Marker protocol (research-grade)

The game emits numeric codes (also logged in the XLSX **Events** sheet):

| Code | Label | When |
|------|--------|------|
| 1 | `SESSION_START` | Participant session begins |
| 10 | `STIM_ONSET` | Scored gate glyph revealed (photodiode flashes) |
| 11 | `STIM_OBSERVE` | Observe-only gate revealed (photodiode flashes) |
| 20 | `RESP_MATCH` | Participant answered MATCH |
| 21 | `RESP_NO_MATCH` | Participant answered NO MATCH |
| 30 | `BLOCK_PRACTICE_START` | Practice corridor entered |
| 31 | `BLOCK_SCORED_START` | Scored block corridor entered |
| 40 | `BLOCK_END` | Block finished |
| 50 | `SESSION_END` | Session complete (before export) |
| 60 | `PAUSE_ON` | Pause menu opened |
| 61 | `PAUSE_OFF` | Pause menu closed |

LSL marker strings are formatted as `CODE:LABEL` (example: `10:STIM_ONSET`).

**Stimulus onset** is marked at gate reveal. The photodiode flash is tied to the same moment (`flashPhotodiode()`), so LSL and optical traces should align within one monitor frame plus network jitter (typically &lt; 5 ms on localhost).

---

## 4. Run order (every session)

### Step A - Start EEG

1. Connect actiCHamp.
2. Launch **BrainVision LSL Connector** → verify EEG stream appears.
3. Open **LabRecorder** → refresh streams → confirm EEG stream is listed.

### Step B - Start marker bridge

```bash
source .venv-eeg/bin/activate
python3 scripts/lsl_marker_bridge.py --log logs/markers.csv
```

You should see:

```
[bridge] LSL outlet ready: GLYPHMIND_Markers (Markers)
[bridge] WebSocket listening on ws://127.0.0.1:8765
```

In LabRecorder, refresh again - **`GLYPHMIND_Markers`** should appear.

### Step C - Start game server

```bash
python3 -m http.server 4173
```

Open in Chrome (recommended): `http://127.0.0.1:4173`

Use **localhost only** for the marker bridge (browser security blocks mixed remote pages from talking to `127.0.0.1` unless you serve the game from the same machine).

### Step D - Researcher setup (title screen)

1. Enter **Participant ID** and **Session**.
2. Set **Stimulation** and **Block order**.
3. **EEG MARKERS (LSL):** leave enabled (default).
4. Bridge URL: `ws://127.0.0.1:8765` (change only if you altered `--port`).
5. Status should show **Connected** (green) before the participant starts.
6. Click **READY FOR PARTICIPANT**.

### Step E - Record

1. In LabRecorder, select **EEG stream** + **`GLYPHMIND_Markers`**.
2. Click **Record** and choose filename (include PID, session, date).
3. Participant clicks **BEGIN** and completes the session.
4. Stop LabRecorder when the participant reaches **DOWNLOAD DATA**.

### Step F - Save behavioural data

Participant (or researcher) clicks **DOWNLOAD DATA** on the session-complete screen.

The `.xlsx` file contains:

- **Trials** - one row per exported trial with RT, RSI, accuracy fields
- **Events** - full marker log with `perfMs` (high-resolution browser clock) and ISO timestamps
- **Meta** - protocol IDs, block seeds, marker protocol version, bridge URL, timezone

---

## 5. Dual sync strategy (LSL + photodiode)

| Method | Strength | Use for |
|--------|----------|---------|
| **LSL markers** | Software timestamps, rich labels (trial #, block, N) | Primary event alignment in analysis |
| **Photodiode → trigger input** | Sample-aligned hardware trigger in EEG channel | Gold-standard onset verification |
| **XLSX Events sheet** | Offline backup if LSL recording failed | Recovery / QC |

**Best practice:** Record LSL markers **and** run a photodiode into the actiCHamp trigger input for a subset of sessions. Compare `STIM_ONSET` LSL times to the trigger channel to quantify end-to-end latency once per setup.

Photodiode placement:

1. Enable **TRIAL FLASH MARKER** in Accessibility.
2. Tape the sensor over the **bottom-right black square** (not the white flash - the housing should cover the square).
3. In the LSL connector, enable **EEG Channel** trigger output for the trigger input.

---

## 6. Analysis notes

### Aligning XLSX with EEG

- LSL `.xdf` files: import with [pyxdf](https://github.com/xdf-modules/pyxdf) or EEGLAB/MNE-LSL.
- Match `10:STIM_ONSET` markers to trial rows via `trial` and `block` fields in the Events sheet.
- `perfMs` in Events is monotonic from session start (`performance.now()`); use Meta `sessionStartISO` + `sessionPerfOriginMs` for wall-clock reconstruction.

### Behavioural QC

```bash
node scripts/verify-logic.mjs
node scripts/verify-session-data.mjs
node scripts/audit-export.mjs path/to/export.xlsx --strict
```

A complete session should have **140 scored+warmup rows** (70 per block) and zero pending scored rows under `--strict`.

---

## 7. Troubleshooting

| Symptom | Fix |
|---------|-----|
| Marker status **Disconnected** | Start `lsl_marker_bridge.py`; confirm URL `ws://127.0.0.1:8765` |
| Markers in game but not in LabRecorder | Click Refresh in LabRecorder; restart bridge |
| EEG stream missing | actiCHamp power/USB; restart BrainVision LSL Connector |
| Photodiode never flashes | Enable **TRIAL FLASH MARKER** in Accessibility |
| High marker jitter | Prefer **EEG Channel** hardware triggers for onset; use LSL markers for response labels |
| `pip install pylsl` fails | Install liblsl: `brew install labstreaminglayer/tap/lsl` (macOS) or see [liblsl releases](https://github.com/sccn/liblsl/releases) |

---

## 8. References

- [Brain Products - LSL tips & tricks](https://www.brainproducts.com/support-resources/tips-and-tricks-for-lsl/)
- [BCI+ - LSL markers vs hardware triggers](https://bci.plus/lsl-markers-vs-hardware-triggers/)
- [Lab Streaming Layer](https://labstreaminglayer.org/)
- [LabRecorder](https://github.com/labstreaminglayer/App-LabRecorder)

---

## 9. Operator quick checklist

- [ ] actiCHamp connected, impedances OK  
- [ ] BrainVision LSL Connector running, EEG stream visible  
- [ ] `python3 scripts/lsl_marker_bridge.py --log logs/markers.csv` running  
- [ ] LabRecorder armed (EEG + GLYPHMIND_Markers)  
- [ ] Game served at `http://127.0.0.1:4173`  
- [ ] Title screen marker status **Connected**  
- [ ] Photodiode on bottom-right square (backup)  
- [ ] Participant ID + session entered  
- [ ] Record started **before** participant begins  
- [ ] **DOWNLOAD DATA** clicked at session end  
- [ ] LabRecorder stopped and file backed up  

For the full behavioural protocol see [GLYPHMIND_Game_Run_Protocol.md](./GLYPHMIND_Game_Run_Protocol.md).
