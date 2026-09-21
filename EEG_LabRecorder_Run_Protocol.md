# EEG + game: LabRecorder run protocol (simple path)

Use this when you want one recording that has **EEG and game markers** together.

You need one computer for the game, the marker bridge, BrainVision LSL Connector, and LabRecorder. Use two screens if you can: participant on one, researcher on the other.

This is not the BrainVision Recorder path. BrainVision Recorder does not read the LSL marker bridge by itself. Here LabRecorder saves both EEG and markers.

**Critical:** If BrainVision LSL Connector is not running, or you do not select the EEG stream in LabRecorder, the `.xdf` will contain **markers only**. That file cannot be plotted as EEG. Always confirm LabRecorder lists **both** an EEG stream and `GLYPHMIND_Markers` before you click Record.

---

## What each program does

| Program | Job |
|---------|-----|
| BrainVision LSL Connector | Puts actiCHamp EEG on LSL (**required for real EEG**) |
| `lsl_marker_bridge.py` | Takes markers from the game and puts them on LSL as `GLYPHMIND_Markers` |
| LabRecorder | Records selected LSL streams into one `.xdf` file |
| `live_eeg_viewer.py` | Live plot of EEG + markers during the session (does not record) |
| `plot_xdf.py` | After the session: open the `.xdf` and plot EEG (and attach markers) |
| Game in the browser | Shows the task and sends markers to the bridge |
| Game Excel download | Behavioral data (accuracy, RT, and so on) |
| `compact_eeg_events.py` | Builds a **stim/response event table** (CSV). This is **not** EEG. |

### What each file is (do not confuse these)

| File | Contents |
|------|----------|
| LabRecorder `.xdf` | Continuous **EEG samples** + markers (only if EEG was selected) |
| Game `.xlsx` | Behavioral trials / events / meta |
| `logs/markers.csv` | Optional marker backup from the bridge |
| `compact_events.csv` | One row per stimulus with times joined from XDF/Excel (**event times, not waveforms**) |

---

## One-time install

### A. Lab software

1. Install BrainVision LSL Connector for actiCHamp (from Brain Products).
2. Install LabRecorder: https://github.com/labstreaminglayer/App-LabRecorder

### B. Python tools (in this repo)

**macOS / Linux:**

```bash
cd /path/to/echoes-of-sekhet
python3 -m venv .venv-eeg
source .venv-eeg/bin/activate
pip install -r scripts/requirements-eeg.txt
pip install mne PyQt5
```

**Windows (PowerShell or cmd):**

```bat
cd C:\Users\Ranjan\Documents\echoes-of-sekhet
python -m venv .venv-eeg
.venv-eeg\Scripts\python.exe -m pip install -r scripts\requirements-eeg.txt
.venv-eeg\Scripts\python.exe -m pip install mne PyQt5
```

If PowerShell blocks `Activate.ps1` (`running scripts is disabled`), skip activate and call the venv Python directly:

```bat
.venv-eeg\Scripts\python.exe scripts\lsl_marker_bridge.py --log logs\markers.csv
```

Or allow scripts for this window only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv-eeg\Scripts\activate
```

Do the install once per machine. Later sessions only need the venv (or the direct `python.exe` path above).

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
2. Start **BrainVision LSL Connector**.
3. Confirm the EEG stream is running in the Connector UI.
4. **Do not skip this step.** Without it, LabRecorder can only save markers.

### Step 2. Marker bridge

**Windows:**

```bat
cd C:\Users\Ranjan\Documents\echoes-of-sekhet
mkdir logs 2>nul
.venv-eeg\Scripts\python.exe scripts\lsl_marker_bridge.py --log logs\markers.csv
```

**macOS / Linux:**

```bash
cd /path/to/echoes-of-sekhet
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

### Step 3. LabRecorder (must select BOTH streams)

1. Open LabRecorder.
2. Click **Refresh**.
3. You must see **at least two** streams:
   - An **EEG** stream (from BrainVision LSL Connector / actiCHamp)
   - **`GLYPHMIND_Markers`**
4. **Select both.** If only `GLYPHMIND_Markers` appears, stop: fix Step 1, then Refresh again.
5. Do not click Record yet. Wait until the title screen is ready (Step 5).

**Gate before Record:** if EEG is missing from the list, you will get a markers-only `.xdf` and cannot plot EEG later.

### Step 3b. Live EEG + markers (optional)

Confirms EEG is flowing *before* the participant starts. Bridge must already be running; Connector must be streaming.

**Windows:**

```bat
cd C:\Users\Ranjan\Documents\echoes-of-sekhet
.venv-eeg\Scripts\python.exe scripts\live_eeg_viewer.py --channels 0,1,2,3 --window 8
```

**macOS / Linux:**

```bash
cd /path/to/echoes-of-sekhet
source .venv-eeg/bin/activate
python3 scripts/live_eeg_viewer.py --channels 0,1,2,3 --window 8
```

A window opens with scrolling EEG. Red lines are game markers (after the game connects).

Useful options:

```bat
.venv-eeg\Scripts\python.exe scripts\live_eeg_viewer.py --eeg-name "actiCHamp"
```

If it cannot find EEG, it prints the streams it can see. Match `--eeg-name` or `--eeg-type` to your LSL Connector.

You can run the live viewer and LabRecorder at the same time. The viewer does not save a file.

### Step 4. Game server

**Windows:**

```bat
cd C:\Users\Ranjan\Documents\echoes-of-sekhet
python -m http.server 4173 --bind 127.0.0.1
```

**macOS / Linux:**

```bash
cd /path/to/echoes-of-sekhet
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

1. In LabRecorder, confirm EEG + `GLYPHMIND_Markers` are still selected.
2. Click **Record**. Pick a filename with PID, session, and date.
3. Participant clicks **BEGIN** and finishes the session.
4. At the end screen, click **DOWNLOAD DATA** (saves the Excel file).
5. Stop LabRecorder.
6. Stop the bridge terminal (Ctrl+C) and the game server terminal when you are done.

---

## What you should have at the end

1. LabRecorder `.xdf` with **EEG + markers** (verify in the next section)
2. Game `.xlsx` (Trials, Events, Meta)
3. Optional backup: `logs/markers.csv` from the bridge

---

## After the session

### 1. Verify the `.xdf` has EEG (do this every time)

`mne.io.read_raw_xdf` is not available in all MNE builds. Use the repo helper:

```bat
cd C:\Users\Ranjan\Documents\echoes-of-sekhet
.venv-eeg\Scripts\python.exe plot_xdf.py "C:\path\to\your_recording.xdf"
```

You want output like:

```
Streams found:
  actiCHamp-... | EEG | samples=...
  GLYPHMIND_Markers | Markers | samples=...
```

Then a plot window opens with channel traces.

**If you only see:**

```
Streams found:
  GLYPHMIND_Markers | Markers | samples=...
No EEG stream in this XDF. Markers-only recording ...
```

then that session has **no EEG samples**. Behavioral Excel and marker timing are still usable; continuous EEG is not. For the next participant, fix BrainVision LSL Connector + LabRecorder stream selection before Record.

### 2. Build a stim + response event table (not EEG)

```bat
cd C:\Users\Ranjan\Documents\echoes-of-sekhet
.venv-eeg\Scripts\python.exe scripts\compact_eeg_events.py ^
  --xdf "C:\path\to\your_recording.xdf" ^
  --xlsx "C:\path\to\your_game_export.xlsx" ^
  -o "C:\path\to\compact_events.csv"
```

`compact_events.csv` has one row per stimulus, with the response paired when it exists, plus accuracy fields from the Excel file when the join works.

Use `stim_time` / `resp_time` (from XDF) for EEG epoching, or `stim_perf_ms` / `resp_perf_ms` for game-clock alignment.

A full session with practice typically yields about **180** stim rows (2 × (20 practice + 70 scored)). That count alone does **not** prove EEG was recorded.

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
| No EEG stream in LabRecorder | Amp power/USB, start BrainVision LSL Connector, Refresh |
| `.xdf` is markers-only (`plot_xdf.py` finds no EEG) | Connector was off, or EEG stream was not selected in LabRecorder; cannot recover EEG for that file |
| `compact_events.csv` looks like text, not waveforms | Expected: that file is events only; plot the `.xdf` with `plot_xdf.py` |
| PowerShell: `Activate.ps1` disabled | Call `.venv-eeg\Scripts\python.exe` directly, or `Set-ExecutionPolicy -Scope Process Bypass` |
| Port busy | Game must be 4173, bridge must be 8765 |
| Markers in game Events but missing in `.xdf` | LabRecorder was not recording, or marker stream was not selected |

---

## Checklist

- [ ] actiCHamp on, impedances OK
- [ ] BrainVision LSL Connector running (EEG visible)
- [ ] Bridge running on port 8765
- [ ] LabRecorder lists **EEG** and **`GLYPHMIND_Markers`** (both selected)
- [ ] (Optional) `live_eeg_viewer.py` shows scrolling traces
- [ ] Game at `http://127.0.0.1:4173`
- [ ] Title screen shows bridge connected
- [ ] LabRecorder Record started before BEGIN
- [ ] DOWNLOAD DATA clicked at the end
- [ ] LabRecorder stopped and `.xdf` saved
- [ ] `plot_xdf.py` confirms EEG stream present (not markers-only)
- [ ] Excel file moved to the study folder

For task instructions (what to say to the participant, block order, tDCS fields), see [GLYPHMIND_Game_Run_Protocol.md](./GLYPHMIND_Game_Run_Protocol.md).

For photodiode wiring and extra detail, see [ACTICHAMP_EEG_GUIDE.md](./ACTICHAMP_EEG_GUIDE.md).
