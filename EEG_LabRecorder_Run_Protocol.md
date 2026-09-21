# EEG + game: LabRecorder run protocol (simple path)

Use this when you want one recording that has EEG and game markers together.

You need one computer for the game, the marker bridge, BrainVision LSL Connector, and LabRecorder. Use two screens if you can: participant on one, researcher on the other.

This is not the BrainVision Recorder path. BrainVision Recorder does not read the LSL marker bridge by itself. Here LabRecorder saves both EEG and markers.

---

## What each program does

| Program | Job |
|---------|-----|
| BrainVision LSL Connector | Puts actiCHamp EEG on LSL |
| `lsl_marker_bridge.py` | Takes markers from the game and puts them on LSL as `GLYPHMIND_Markers` |
| LabRecorder | Records EEG + markers into one `.xdf` file |
| `live_eeg_viewer.py` | Live plot of EEG + markers (does not record) |
| Game in the browser | Shows the task and sends markers to the bridge |
| Game Excel download | Behavioral data (accuracy, RT, and so on) |

---

## One-time install

### A. Lab software

1. Install BrainVision LSL Connector for actiCHamp (from Brain Products).
2. Install LabRecorder: https://github.com/labstreaminglayer/App-LabRecorder

### B. Python bridge (in this repo)

Open Terminal:

```bash
cd /Users/sharm/echoes-of-sekhet
python3 -m venv .venv-eeg
source .venv-eeg/bin/activate
pip install -r scripts/requirements-eeg.txt
```

On Windows, activate with:

```bash
.venv-eeg\Scripts\activate
```

Do this once per machine. Later sessions only need `source .venv-eeg/bin/activate`.

---

## Ports (do not mix these up)

| Port | Use |
|------|-----|
| 4173 | Game web server |
| 8765 | Marker bridge WebSocket |

---

## Every session: start order

Do these in order. Keep all windows open until the session is done.

### Step 1. Amp and EEG stream

1. Power on actiCHamp. Check impedances per your lab SOP.
2. Start BrainVision LSL Connector.
3. Confirm the EEG stream is running.

### Step 2. Marker bridge

```bash
cd /Users/sharm/echoes-of-sekhet
source .venv-eeg/bin/activate
mkdir -p logs
python3 scripts/lsl_marker_bridge.py --log logs/markers.csv
```

You want lines like:

```
[bridge] LSL outlet ready: GLYPHMIND_Markers (Markers)
[bridge] WebSocket listening on ws://127.0.0.1:8765
```

Leave this terminal running.

### Step 3. LabRecorder

1. Open LabRecorder.
2. Click Refresh.
3. You should see the EEG stream.
4. You should also see `GLYPHMIND_Markers`.
5. Select both.
6. Do not click Record yet. Wait until the title screen is ready (Step 5).

### Step 3b. Live EEG + markers (optional)

In a third terminal (bridge and game still running):

```bash
cd /Users/sharm/echoes-of-sekhet
source .venv-eeg/bin/activate
pip install -r scripts/requirements-eeg.txt
python3 scripts/live_eeg_viewer.py
```

A window opens with scrolling EEG. Red lines are game markers.

Useful options:

```bash
python3 scripts/live_eeg_viewer.py --channels 0,1,2 --window 8
python3 scripts/live_eeg_viewer.py --eeg-name "actiCHamp"
```

If it cannot find EEG, it prints the streams it can see. Match `--eeg-name` or `--eeg-type` to your LSL Connector.

You can run the live viewer and LabRecorder at the same time. The viewer does not save a file.

### Step 4. Game server

Open a second terminal:

```bash
cd /Users/sharm/echoes-of-sekhet
python3 -m http.server 4173 --bind 127.0.0.1
```

Open Chrome:

```
http://127.0.0.1:4173
```

Use localhost only. Remote pages cannot talk to the bridge on this machine.

### Step 5. Title screen

1. Enter Participant ID.
2. Set Session (1, 2, or 3).
3. Set Stimulation and Block order.
4. Leave **SEND LSL MARKERS** on.
5. Bridge URL: `ws://127.0.0.1:8765`
6. Status must show connected (green) before you continue.
7. Optional: in Accessibility, leave **PHOTODIODE (STIM + RESP)** on if you also use a light sensor on the bottom-right square.
8. Click **READY FOR PARTICIPANT**.

### Step 6. Start recording, then start the task

1. In LabRecorder, click Record. Pick a filename with PID, session, and date.
2. Participant clicks **BEGIN** and finishes the session.
3. At the end screen, click **DOWNLOAD DATA** (saves the Excel file).
4. Stop LabRecorder.
5. Stop the bridge terminal (Ctrl+C) and the game server terminal when you are done.

---

## What you should have at the end

1. LabRecorder `.xdf` (EEG + markers)
2. Game `.xlsx` (Trials, Events, Meta)
3. Optional backup: `logs/markers.csv` from the bridge

---

## After the session (Python)

### Look at the `.xdf`

```bash
pip install mne pyxdf
```

```python
import mne

raw = mne.io.read_raw_xdf("your_recording.xdf", preload=True)
print(raw)
raw.plot()
print(raw.annotations)
```

### Build one table of stim + response events

```bash
cd /Users/sharm/echoes-of-sekhet
source .venv-eeg/bin/activate
python3 scripts/compact_eeg_events.py \
  --xdf your_recording.xdf \
  --xlsx your_game_export.xlsx \
  -o compact_events.csv
```

`compact_events.csv` has one row per stimulus, with the response paired when it exists, plus accuracy fields from the Excel file when the join works.

---

## Marker codes (short list)

| Code | Meaning |
|------|---------|
| 10 | Stim onset (scored) |
| 11 | Stim onset (observe only) |
| 20 | Response MATCH |
| 21 | Response NO MATCH |

LSL text looks like: `10:STIM_ONSET:b1:t12:n3:scored`

Photodiode on screen (if used): long flash = stim, double short flash = response.

---

## If something fails

| Problem | Fix |
|---------|-----|
| Marker status not connected | Bridge not running, or URL not `ws://127.0.0.1:8765` |
| No `GLYPHMIND_Markers` in LabRecorder | Restart bridge, click Refresh |
| No EEG stream | Amp power/USB, restart LSL Connector |
| Port busy | Game must be 4173, bridge must be 8765 |
| Markers in game Events but missing in `.xdf` | LabRecorder was not recording, or marker stream was not selected |

---

## Checklist

- [ ] actiCHamp on, impedances OK
- [ ] BrainVision LSL Connector running
- [ ] Bridge running on port 8765
- [ ] LabRecorder sees EEG + `GLYPHMIND_Markers`
- [ ] Game at `http://127.0.0.1:4173`
- [ ] Title screen shows bridge connected
- [ ] LabRecorder Record started before BEGIN
- [ ] DOWNLOAD DATA clicked at the end
- [ ] LabRecorder stopped and `.xdf` saved
- [ ] Excel file moved to the study folder

For task instructions (what to say to the participant, block order, tDCS fields), see [GLYPHMIND_Game_Run_Protocol.md](./GLYPHMIND_Game_Run_Protocol.md).

For photodiode wiring and extra detail, see [ACTICHAMP_EEG_GUIDE.md](./ACTICHAMP_EEG_GUIDE.md).
