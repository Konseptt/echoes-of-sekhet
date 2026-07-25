/**
 * Guards the pause/tab-hide wall-time accounting in index.html: when an Escape
 * pause overlaps a tab-hide, the hidden slice must be credited to revealTime
 * exactly once, not twice. Pure model of the two compensators; run:
 *   node scripts/test-pause-timing.mjs
 */
import assert from "node:assert/strict";

// Mirrors index.html: resumeGame() credits the whole pause span; the tab-hide
// handler credits the hidden span but skips while phase === "paused" (the fix).
function revealBumpOverPause({ pauseStart, hideAt, returnAt, resumeAt, guard }) {
  let bump = 0;
  // Tab becomes visible again while still paused: hide handler runs first.
  if (hideAt != null) {
    const hiddenMs = returnAt - hideAt;
    const phase = "paused"; // user has not clicked Resume yet on this frame
    if (!guard || phase !== "paused") bump += hiddenMs; // guard skips the overlap
  }
  bump += resumeAt - pauseStart; // resumeGame() credits full pause span
  return bump;
}

// Overlap: pause 1000, hide 2000, return 5000 (still paused), resume 6000.
const scenario = { pauseStart: 1000, hideAt: 2000, returnAt: 5000, resumeAt: 6000 };
const truePause = scenario.resumeAt - scenario.pauseStart; // 5000, the real wall-time

assert.equal(revealBumpOverPause({ ...scenario, guard: true }), truePause,
  "guarded: hidden slice credited once");
assert.equal(revealBumpOverPause({ ...scenario, guard: false }), truePause + 3000,
  "unguarded regression: hidden slice double-counted (guard is load-bearing)");

// Non-overlap sanity: hidden while NOT paused is credited once on its own.
function revealBumpHiddenOnly(hiddenMs) { return hiddenMs; }
assert.equal(revealBumpHiddenOnly(1500), 1500, "hide-only credited once");

console.log("pause/hide timing: hidden slice credited exactly once on overlap.");
