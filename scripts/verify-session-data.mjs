/**
 * Simulates full session logging (scored blocks only; practice not exported) and audits export shape.
 * Run: node scripts/verify-session-data.mjs
 */
import {
  TOTAL_TRIALS,
  MATCH_COUNT,
  NON_MATCH_PAINTING_COUNT,
  N_GLYPHS,
  GLYPHS,
  genSeqBlock,
  genSeqBlockSpread,
  glyphIdForIndex,
  sequenceSeedUsesSpreadAlgorithm,
  rngFromSeed,
  pickObserveGlyphs,
  pickNonMatchGlyph,
  shuffle,
  maxConsecutiveSameGlyph,
  maxConsecutiveTrue,
  MAX_CONSECUTIVE_SAME_GLYPH,
} from "./glyphmind-core.mjs";
import { auditExportData } from "./audit-export.mjs";

const PRACTICE_TRIALS = 20;
const TUTORIAL_TRIALS = 5;

function scoredCountForN(N, totalTrials = TOTAL_TRIALS) {
  return totalTrials - N;
}

function matchCountForBlock(N, totalTrials = TOTAL_TRIALS) {
  const scored = scoredCountForN(N, totalTrials);
  const fullScored = scoredCountForN(N, TOTAL_TRIALS);
  if (scored <= 0 || fullScored <= 0) return 0;
  return Math.max(1, Math.min(scored, Math.round((MATCH_COUNT * scored) / fullScored)));
}

function countScoredMatchesLen(sequence, N) {
  let matches = 0;
  for (let i = N; i < sequence.length; i++) {
    if (
      sequence[i] !== undefined &&
      sequence[i - N] !== undefined &&
      sequence[i] === sequence[i - N]
    ) {
      matches++;
    }
  }
  return matches;
}

function buildIsMatchFlagsLen(scoredN, rng, matchTarget) {
  const limits = [4, 5, 6, scoredN];
  for (const maxConsecutive of limits) {
    for (let inner = 0; inner < 48; inner++) {
      const order = shuffle(
        Array.from({ length: scoredN }, (_, j) => j),
        rng,
      );
      const isMatch = new Array(scoredN).fill(false);
      let placed = 0;
      for (const j of order) {
        if (placed >= matchTarget) break;
        isMatch[j] = true;
        if (maxConsecutiveTrue(isMatch) > maxConsecutive) isMatch[j] = false;
        else placed++;
      }
      if (placed === matchTarget && maxConsecutiveTrue(isMatch) <= maxConsecutive) return isMatch;
    }
  }
  const isMatch = new Array(scoredN).fill(false);
  const matchable = shuffle(
    Array.from({ length: scoredN }, (_, j) => j),
    rng,
  );
  for (let i = 0; i < matchTarget; i++) isMatch[matchable[i]] = true;
  return isMatch;
}

/** Mirrors index.html genSeqBlock(N, seed, totalTrials) for practice blocks. */
function genSeqBlockLen(N, seed, totalTrials) {
  if (!sequenceSeedUsesSpreadAlgorithm(seed)) {
    return genSeqBlock(N, seed);
  }
  const matchTarget = matchCountForBlock(N, totalTrials);
  const rng = rngFromSeed(seed);
  const observeGlyphs = pickObserveGlyphs(N, rng);
  for (let attempt = 0; attempt < 64; attempt++) {
    const seq = new Array(totalTrials).fill(-1);
    const scoredN = scoredCountForN(N, totalTrials);
    for (let i = 0; i < N; i++) seq[i] = observeGlyphs[i];
    const isMatch = buildIsMatchFlagsLen(scoredN, rng, matchTarget);
    for (let j = 0; j < scoredN; j++) {
      const pos = N + j;
      const ref = seq[pos - N];
      seq[pos] = isMatch[j] ? ref : pickNonMatchGlyph(ref, rng);
    }
    for (let pass = 0; pass < 32; pass++) {
      if (countScoredMatchesLen(seq, N) === matchTarget) break;
      for (let j = 0; j < scoredN; j++) {
        const pos = N + j;
        const ref = seq[pos - N];
        seq[pos] = isMatch[j] ? ref : pickNonMatchGlyph(ref, rng);
      }
    }
    const allAssigned = seq.every((v) => Number.isInteger(v) && v >= 0 && v < N_GLYPHS);
    if (
      countScoredMatchesLen(seq, N) === matchTarget &&
      allAssigned &&
      maxConsecutiveSameGlyph(seq) <= MAX_CONSECUTIVE_SAME_GLYPH
    ) {
      return seq;
    }
  }
  throw new Error(`Could not build ${N}-back / ${totalTrials} sequence`);
}

function glyphLogFields(gi) {
  const g = GLYPHS[gi];
  return { StimulusName: g.name, StimulusChar: g.ch };
}

function makeGameLogger() {
  let isPracticePhase = false;
  const logger = {
    block: 1,
    trials: [],
    trialType(kind) {
      if (isPracticePhase) return kind === "warmup" ? "practice_warmup" : "practice";
      return kind;
    },
    recordWarmup(opts) {
      if (isPracticePhase) return;
      const trialNum = opts.trialIdx + 1;
      const trialType = logger.trialType("warmup");
      const row = {
        trialType,
        trial: trialNum,
        block: logger.block,
        N: opts.n,
        sequenceSeed: opts.sequenceSeed,
        CRESP: "",
        Resp: "",
        ACC: "",
        isMatch: "",
        RT: "",
        RSI: Math.round(opts.rsi || 0),
        ...glyphLogFields(opts.glyphIdx),
      };
      upsert(row);
    },
    record(opts) {
      if (isPracticePhase) return;
      const i = opts.trialIdx;
      const trialNum = i + 1;
      const isMatch = opts.glyphIdx === opts.nbackGlyphIdx;
      const expectedResp = isMatch ? 1 : 2;
      const hasResponse = opts.resp === 1 || opts.resp === 2;
      const trialType = logger.trialType("scored");
      const row = {
        trialType,
        trial: trialNum,
        block: logger.block,
        N: opts.n,
        sequenceSeed: opts.sequenceSeed,
        CRESP: expectedResp,
        Resp: hasResponse ? opts.resp : "",
        ACC: hasResponse ? (expectedResp === opts.resp ? 1 : 0) : "",
        isMatch: isMatch ? 1 : 0,
        RT: hasResponse ? Math.round(opts.rt || 0) : "",
        RSI: Math.round(opts.rsi || 0),
        ...glyphLogFields(opts.glyphIdx),
      };
      upsert(row);
    },
  };

  function upsert(row) {
    const idx = logger.trials.findIndex(
      (t) => t.block === row.block && t.trialType === row.trialType && t.trial === row.trial,
    );
    if (idx >= 0) logger.trials[idx] = row;
    else logger.trials.push(row);
  }

  return {
    logger,
    setPractice(v) {
      isPracticePhase = v;
    },
  };
}

function simulateCorridor(sim, N, totalTrials, seed, block) {
  const { logger, setPractice } = sim;
  logger.block = block;
  const seq =
    totalTrials === TOTAL_TRIALS ? genSeqBlock(N, seed) : genSeqBlockLen(N, seed, totalTrials);
  let lastEventTime = 0;
  let respondedCount = 0;

  for (let idx = 0; idx < totalTrials; idx++) {
    const revealTime = 1000 + idx * 2000;
    const rsi = lastEventTime > 0 ? revealTime - lastEventTime : 0;

    if (idx < N) {
      logger.recordWarmup({
        trialIdx: idx,
        n: N,
        glyphIdx: seq[idx],
        rsi,
        sequenceSeed: seed,
      });
      lastEventTime = revealTime;
      continue;
    }

    logger.record({
      trialIdx: idx,
      n: N,
      glyphIdx: seq[idx],
      nbackGlyphIdx: seq[idx - N],
      rsi,
      sequenceSeed: seed,
    });

    const actualMatch = seq[idx] === seq[idx - N];
    const resp = actualMatch ? 1 : 2;
    const respTime = revealTime + 400;
    const rt = respTime - revealTime;

    // Match game.respond(): keep reveal RSI; only RT is response - reveal.
    logger.record({
      trialIdx: idx,
      n: N,
      glyphIdx: seq[idx],
      nbackGlyphIdx: seq[idx - N],
      resp,
      rt,
      rsi,
      sequenceSeed: seed,
    });

    lastEventTime = respTime;
    respondedCount++;
  }

  const expectedScored = totalTrials - N;
  return { seq, respondedCount, expectedScored };
}

function isSessionTrialRow(t) {
  return t.trialType !== "practice" && t.trialType !== "practice_warmup";
}

function hasCompleteBlock(trials, block) {
  const blockRows = trials.filter((t) => t.block === block && isSessionTrialRow(t));
  if (blockRows.length !== TOTAL_TRIALS) return false;
  const seen = new Set();
  for (const row of blockRows) {
    if (seen.has(row.trial)) return false;
    seen.add(row.trial);
    if (row.trialType === "scored" && row.Resp !== 1 && row.Resp !== 2) return false;
  }
  return seen.size === TOTAL_TRIALS;
}

function validateRowLogic(trials) {
  const issues = [];
  for (const row of trials) {
    const tt = row.trialType;
    if (tt === "scored" || tt === "practice") {
      if (row.Resp === 1 || row.Resp === 2) {
        if (row.ACC !== (row.Resp === row.CRESP ? 1 : 0)) {
          issues.push(`t${row.trial} b${row.block} ${tt}: ACC wrong`);
        }
        if (!(row.RT > 0)) {
          issues.push(`t${row.trial} b${row.block} ${tt}: answered row needs RT > 0`);
        }
      } else if (row.RT !== "" && row.RT != null) {
        issues.push(`t${row.trial} b${row.block} ${tt}: pending scored row must leave RT blank`);
      }
    }
    if ((tt === "warmup" || tt === "practice_warmup")) {
      if (row.CRESP !== "" && row.CRESP != null) {
        issues.push(`t${row.trial} ${tt}: warmup should leave CRESP blank`);
      }
      if (row.RT !== "" && row.RT != null) {
        issues.push(`t${row.trial} ${tt}: warmup must leave RT blank`);
      }
    }
    if (typeof row.RSI === "number" && row.RSI < 0) {
      issues.push(`t${row.trial} b${row.block}: negative RSI`);
    }
  }
  return issues;
}

/** Mirror index.html reveal/respond/pause timing for RT + RSI. */
function auditTimingModel() {
  const issues = [];
  let lastEventTime = 0;
  const N = 1;
  const trials = [];

  function reveal(idx, now) {
    const rsi = lastEventTime > 0 ? now - lastEventTime : 0;
    const panel = { idx, revealTime: now, rsi, responded: false };
    if (idx < N) {
      lastEventTime = now;
      trials.push({ trial: idx + 1, type: "warmup", RSI: Math.round(rsi), RT: "" });
      return panel;
    }
    trials.push({
      trial: idx + 1,
      type: "scored",
      RSI: Math.round(rsi),
      RT: "",
      revealTime: now,
      rsi,
    });
    return panel;
  }

  function respond(panel, respTime) {
    const rt = respTime - panel.revealTime;
    const row = trials.find((t) => t.trial === panel.idx + 1 && t.type === "scored");
    row.RT = Math.round(rt);
    row.RSI = Math.round(panel.rsi || 0);
    lastEventTime = respTime;
    panel.responded = true;
  }

  function pauseDuring(panel, pauseMs) {
    // resumeGame(): bump active revealTime + lastEventTime so RT excludes pause
    panel.revealTime += pauseMs;
    if (lastEventTime > 0) lastEventTime += pauseMs;
  }

  // Gate 1 observe at t=1000
  reveal(0, 1000);
  // Gate 2 scored reveal at t=3000 (RSI = 2000 from observe reveal)
  const p1 = reveal(1, 3000);
  // Pause 5000ms while awaiting response
  pauseDuring(p1, 5000);
  // Response at wall t=9000; adjusted reveal=8000 → RT=1000
  respond(p1, 9000);
  // Gate 3 reveal at t=11000; lastEvent was resp 9000 then +0 = 9000 → RSI=2000
  const p2 = reveal(2, 11000);
  respond(p2, 11450);

  if (trials[0].RSI !== 0) issues.push(`warmup RSI expected 0 got ${trials[0].RSI}`);
  if (trials[0].RT !== "") issues.push("warmup RT must be blank");
  if (trials[1].RSI !== 2000) issues.push(`scored1 RSI expected 2000 got ${trials[1].RSI}`);
  if (trials[1].RT !== 1000) issues.push(`scored1 RT expected 1000 (pause excluded) got ${trials[1].RT}`);
  if (trials[2].RSI !== 2000) issues.push(`scored2 RSI expected 2000 got ${trials[2].RSI}`);
  if (trials[2].RT !== 450) issues.push(`scored2 RT expected 450 got ${trials[2].RT}`);

  // Simulated corridor from verify-session-data: fixed 400ms RT, 2000ms spacing
  const sim = makeGameLogger();
  sim.setPractice(false);
  simulateCorridor(sim, 1, TOTAL_TRIALS, "gm-v2-timing-rt-rsi", 1);
  const rows = sim.logger.trials.filter((t) => t.block === 1);
  const warm = rows.filter((t) => t.trialType === "warmup");
  const scored = rows.filter((t) => t.trialType === "scored");
  if (warm.length !== 1) issues.push(`expected 1 warmup got ${warm.length}`);
  if (warm[0].RSI !== 0) issues.push(`first trial RSI expected 0 got ${warm[0].RSI}`);
  if (warm[0].RT !== "") issues.push("warmup RT not blank in sim");
  for (const row of scored) {
    if (row.RT !== 400) issues.push(`trial ${row.trial} RT expected 400 got ${row.RT}`);
    if (!(row.RSI >= 0)) issues.push(`trial ${row.trial} negative RSI`);
  }
  // After observe at 1000, first scored reveal 3000 → RSI 2000; after resp 3400 next reveal 5000 → RSI 1600
  const s2 = scored.find((t) => t.trial === 2);
  const s3 = scored.find((t) => t.trial === 3);
  if (!s2 || s2.RSI !== 2000) issues.push(`trial 2 RSI expected 2000 got ${s2 && s2.RSI}`);
  if (!s3 || s3.RSI !== 1600) issues.push(`trial 3 RSI expected 1600 got ${s3 && s3.RSI}`);

  return issues;
}

function countByType(trials, block, type) {
  return trials.filter((t) => t.block === block && t.trialType === type).length;
}

let failed = 0;
function ok(cond, msg) {
  if (!cond) {
    console.error("FAIL:", msg);
    failed++;
  }
}

const order13 = [1, 3];
const sim = makeGameLogger();

// Block 1: practice (not logged), scored 1-back
sim.setPractice(true);
const p1 = simulateCorridor(sim, order13[0], PRACTICE_TRIALS, "gm-v2-practice-b1", 1);
ok(p1.respondedCount === scoredCountForN(1, PRACTICE_TRIALS), "block1 practice scored count");
ok(countByType(sim.logger.trials, 1, "practice_warmup") === 0, "block1 practice not logged");
ok(countByType(sim.logger.trials, 1, "practice") === 0, "block1 practice answered not logged");

sim.setPractice(false);
const s1 = simulateCorridor(sim, order13[0], TOTAL_TRIALS, "gm-v2-scored-b1", 1);
ok(s1.respondedCount === scoredCountForN(1), "block1 scored count");
ok(hasCompleteBlock(sim.logger.trials, 1), "block1 session complete");

// Block 2: practice 3-back, scored 3-back
sim.logger.block = 2;
sim.setPractice(true);
const p2 = simulateCorridor(sim, order13[1], PRACTICE_TRIALS, "gm-v2-practice-b2", 2);
sim.setPractice(false);
const s2 = simulateCorridor(sim, order13[1], TOTAL_TRIALS, "gm-v2-scored-b2", 2);
ok(hasCompleteBlock(sim.logger.trials, 2), "block2 session complete");

const trials = sim.logger.trials;
ok(trials.length === 140, `full session row count (got ${trials.length})`);

ok(
  trials.filter((t) => t.trialType === "practice" || t.trialType === "practice_warmup").length === 0,
  "no practice rows in export",
);

const logicIssues = validateRowLogic(trials);
ok(logicIssues.length === 0, `row logic: ${logicIssues.join("; ")}`);

// Match counts per session block
for (const [block, N] of [[1, 1], [2, 3]]) {
  const sessionRows = trials.filter((t) => t.block === block && isSessionTrialRow(t));
  const matchLogged = sessionRows.filter((t) => t.CRESP === 1).length;
  ok(matchLogged === MATCH_COUNT, `block ${block} session matches ${matchLogged}`);
  const nonMatch = sessionRows.filter((t) => t.CRESP !== 1).length;
  ok(nonMatch === NON_MATCH_PAINTING_COUNT, `block ${block} session nonmatches ${nonMatch}`);
}

// Practice is not exported
for (const block of [1, 2]) {
  const practiceRows = trials.filter(
    (t) => t.block === block && (t.trialType === "practice" || t.trialType === "practice_warmup"),
  );
  ok(practiceRows.length === 0, `block ${block} has no practice rows`);
}

const audit = auditExportData(trials, {
  rows_total: trials.length,
  paintingsPerBlock: TOTAL_TRIALS,
  block1_sequenceSeed: "gm-v2-scored-b1",
  block2_sequenceSeed: "gm-v2-scored-b2",
}, { strict: true });

ok(audit.ok, `audit export: ${audit.issues.join("; ")}`);

const timingIssues = auditTimingModel();
ok(timingIssues.length === 0, `RT/RSI timing: ${timingIssues.join("; ")}`);

console.log(failed ? `\n${failed} check(s) failed.` : "\nAll session data checks passed.");
console.log(`  Rows: ${trials.length} (70 scored per block)`);
console.log(`  Block 1: ${countByType(trials, 1, "scored")} scored`);
console.log(`  Block 2: ${countByType(trials, 2, "scored")} scored`);
process.exit(failed ? 1 : 0);
