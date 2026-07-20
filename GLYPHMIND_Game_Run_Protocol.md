# GLYPHMIND Game Task Run Protocol

How research staff run the GLYPHMIND N-back task in the BSVG/tDCS study. This covers the computer task only. Consent, screening, tDCS setup, safety checks, and debrief still follow the approved IRB protocol.

## 1. What the task is

The participant walks a first-person corridor. Each painting shows one hieroglyph.

- **1-back:** compare the current painting to the previous one.
- **3-back:** compare the current painting to the one three steps back.
- **MATCH:** left click (desktop).
- **NO MATCH:** right click (desktop).

Each **scored** block has **70 paintings**. The first **N** are watch-only and count toward those 70. The rest are scored. Each block is built with **30** true N-back matches among all 70 paintings.

Before each scored block, the participant runs a **20-painting practice** at the same N-back level. Practice is not exported. Warm-up accuracy is shown on screen only.

In the export, a full two-block session has **140 rows** (70 per block). Use `trialType === "scored"` and answered `Resp` values for primary analysis. Watch-only rows use `trialType = warmup` and blank `Resp`.

## 2. Before the participant arrives

1. Confirm participant ID, session number (1, 2, or 3), stimulation condition, and task phase (pre, during, or post) from the study record.
2. Open the GLYPHMIND folder. Check that `index.html`, `lib/`, and `fonts/` are present.
3. Load the task in Chrome, Firefox, Safari, or Edge. If `file://` fails, use a local server:

   ```bash
   python3 -m http.server 8765 --bind 127.0.0.1
   ```

   Then open `http://127.0.0.1:8765/index.html`.

4. Optional smoke test: `node scripts/verify-logic.mjs` (expect `All checks passed.`).
5. Clear the download folder or confirm the last participant's file was moved.
6. Do not type the participant's name into the game. Use the assigned ID only.

## 3. Title screen setup

1. **Block order:** `1-BACK -> 3-BACK` or `3-BACK -> 1-BACK` per counterbalancing.
2. **Participant ID:** deidentified ID only.
3. **Session:** click `1`, `2`, or `3` (stored in the export as `"1"`, `"2"`, or `"3"`).
4. **Stimulation:** ANODAL, CATHODAL, or SHAM. Stored as `anodal`, `cathodal`, or `sham`. Confirm the lit button matches randomization (default is anodal).
5. Click **READY FOR PARTICIPANT**. The participant screen shows ID and session only.

## 4. What to tell the participant

Read or paraphrase:

"You will walk down a hallway. Each painting shows one symbol. Remember the symbols and decide whether the new symbol matches one from earlier in the same block.

In a 1-back block, compare to the previous painting. In a 3-back block, compare to the painting three back. Same symbol: left click for MATCH. Different symbol: right click for NO MATCH.

The first painting in a 1-back block is watch-only. The first three in a 3-back block are watch-only. Just look and remember; do not click yet.

Before each main block you will get a short practice run. You can miss answers in practice and still continue.

Use the mouse to answer during the main blocks: left click MATCH, right click NO MATCH. Keyboard keys do not count as answers. Questions before we start?"

**Current build:** desktop mouse only. On-screen touch buttons are not implemented yet.

## 5. Running the task

### Session 1

1. Participant clicks **BEGIN**.
2. Short cutscene (click or key to advance).
3. Tutorial slides (walking, N-back rule, controls, practice warm-up). Final slide says practice does not require perfect accuracy.
4. Block 1 practice (20 paintings).
5. Block 1 scored corridor (70 paintings).
6. Break screen: **ROUND 1 COMPLETE**. Click **CONTINUE**.
7. Block 2 practice warm-up (gate header **ROUND 2**).
8. Block 2 scored corridor (70 paintings).
9. Session complete screen. Click **DOWNLOAD DATA** before closing the browser.

### Sessions 2 and 3

Same block structure. No cutscene or tutorial slides. Optional short return gate, then block 1 practice.

### During a block

- HUD shows painting number, N-back level, **OBSERVE** on watch-only trials, and running accuracy on scored trials.
- **Esc** opens pause: Resume, Controls, Accessibility, Restart block, Back to title.
- No export button in pause. If the tab reloads, use the recovery banner **DOWNLOAD DATA**. Do not dismiss without saving.
- Pause between paintings when you can. Pause time is excluded from RT on the active painting.

### Restart block

Drops warmup and scored rows for the **current** block only, generates a new sequence seed, and replays that block. Note restarts in session paperwork.

## 6. Export and QC

1. After block 2, click **DOWNLOAD DATA** on the session complete screen.
2. Check the download folder. Auto filename pattern:

   `BSVG_STANDARD_SESSION{1|2|3}_{participantID}.xlsx`

   Example: `BSVG_STANDARD_SESSION2_01.xlsx`

3. Rename per lab convention if needed.
4. Open the workbook or run:

   ```bash
   node scripts/audit-export.mjs path/to/file.xlsx --strict
   ```

5. Complete session checks:
   - **140** Trials rows total.
   - **70** rows per block (`warmup` + `scored`).
   - **30** scored rows with `isMatch = 1` per block (Meta QC).
   - `rows_scored_pending = 0` on Meta.
   - Both `block1_sequenceSeed` and `block2_sequenceSeed` present.

6. Log irregularities: early stop, restart, reload, discomfort, partial export.

## 7. After the participant

Follow IRB protocol for tDCS removal, scheduling, debrief, and filing. Move the `.xlsx` to the study data folder. Keep consent forms separate from data files.

## 8. Troubleshooting

| Problem | What to try |
|---------|-------------|
| Blank page | Confirm `lib/` and `fonts/` are present; try a local server |
| Box glyphs | Confirm `fonts/` folder; reload |
| Export fails | Confirm `lib/xlsx.full.min.js`; do not close browser until download finishes |
| Reload mid-session | Use recovery banner download; do not dismiss without saving |
| Confused participant | Pause; restate 1-back vs 3-back and left vs right click |

## 9. Shipped behavior (staff reference)

1. **20-trial practice** before each scored block. Not exported.
2. **Watch-only paintings** take no click. First N in each scored block.
3. **Mouse only** on desktop for MATCH / NO MATCH. F, Space, and J do not answer trials.
4. **Block 1 break:** ROUND 1 COMPLETE. **Block 2 practice gate:** ROUND 2. **Block 2 scored:** FINAL ROUND.
5. **70 paintings** logged per scored block. Observe trials are inside those 70.
6. **Download** only at session complete. **TITLE SCREEN** starts the next participant (PID field clears).
7. **Condition** in export: `anodal`, `cathodal`, or `sham`. Verify the button before BEGIN.
8. **Audio:** no cutscene music. Corridor SFX unless participant mutes in Accessibility.

tDCS electrode placement and stimulation parameters are not covered here. Use the approved stimulation protocol.
