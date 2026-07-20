/**
 * Offline checks for sequence + session helpers (mirrors index.html logic).
 * Run: node scripts/verify-logic.mjs
 */
import {
  TOTAL_TRIALS,
  MATCH_COUNT,
  NON_MATCH_PAINTING_COUNT,
  N_GLYPHS,
  genSeqBlock,
  genSeqBlockSpread,
  maxConsecutiveSameGlyph,
  sequenceSeedUsesSpreadAlgorithm,
  validateBlockSequence,
  countScoredMatches,
  countNonMatchPaintings,
  scoredCountForN,
  scoredNonMatchCountForN,
  glyphIdForIndex,
  GLYPHS,
  MAX_CONSECUTIVE_SAME_GLYPH,
} from "./glyphmind-core.mjs";
import { auditExportData } from "./audit-export.mjs";

function glyphLogFields(gi) {
  const g = GLYPHS[gi];
  return { StimulusName: g.name, StimulusChar: g.ch };
}

function makeRecorder() {
  return {
    trials: [],
    block: 1,
    recordWarmup(o) {
      const trialNum = o.trialIdx + 1;
      this.trials.push({
        trialType: "warmup",
        block: this.block,
        N: o.n,
        trial: trialNum,
        sequenceSeed: o.sequenceSeed,
        CRESP: "",
        Resp: "",
        ACC: "",
        isMatch: "",
        RT: "",
        RSI: 0,
        ...glyphLogFields(o.glyphIdx),
      });
    },
    record(o) {
      const trialNum = o.trialIdx + 1;
      const match = o.glyphIdx === o.nbackGlyphIdx;
      const cresp = match ? 1 : 2;
      const hasResponse = o.resp === 1 || o.resp === 2;
      const row = {
        trialType: "scored",
        block: this.block,
        N: o.n,
        trial: trialNum,
        sequenceSeed: o.sequenceSeed,
        CRESP: cresp,
        Resp: hasResponse ? o.resp : "",
        ACC: hasResponse ? (o.resp === cresp ? 1 : 0) : "",
        isMatch: match ? 1 : 0,
        RT: hasResponse ? Math.round(o.rt || 0) : "",
        RSI: 100,
        ...glyphLogFields(o.glyphIdx),
      };
      const existingIdx = this.trials.findIndex((t) => {
        return t.block === this.block && t.trialType === "scored" && t.trial === trialNum;
      });
      if (existingIdx >= 0) this.trials[existingIdx] = row;
      else this.trials.push(row);
    },
    scoredTrials(block) {
      return this.trials.filter((t) => t.trialType === "scored" && (block == null || t.block === block));
    },
    respondedScoredTrials(block) {
      return this.scoredTrials(block).filter((t) => t.Resp === 1 || t.Resp === 2);
    },
    accuracy(block) {
      const rows = this.respondedScoredTrials(block);
      if (!rows.length) return 0;
      return (rows.filter((t) => t.ACC === 1).length / rows.length) * 100;
    },
  };
}

function hasCompleteBlock(recorder, block) {
  const rows = recorder.trials.filter((t) => t.block === block);
  if (rows.length !== TOTAL_TRIALS) return false;
  const seen = new Set();
  for (const row of rows) {
    if (seen.has(row.trial)) return false;
    seen.add(row.trial);
    if (row.trialType === "scored" && row.Resp !== 1 && row.Resp !== 2) return false;
  }
  return seen.size === TOTAL_TRIALS;
}

function simulateBlock(recorder, N, seed) {
  const seq = genSeqBlock(N, seed);
  for (let i = 0; i < N; i++) {
    recorder.recordWarmup({ trialIdx: i, n: N, glyphIdx: seq[i], sequenceSeed: seed });
  }

  const firstScored = N;
  recorder.record({
    trialIdx: firstScored,
    n: N,
    glyphIdx: seq[firstScored],
    nbackGlyphIdx: seq[firstScored - N],
    sequenceSeed: seed,
  });
  ok(recorder.scoredTrials(recorder.block).length === 1, `N=${N} pending scored row is logged`);
  ok(recorder.respondedScoredTrials(recorder.block).length === 0, `N=${N} pending row is not answered`);
  ok(!hasCompleteBlock(recorder, recorder.block), `N=${N} pending row does not complete block`);

  for (let i = firstScored; i < TOTAL_TRIALS; i++) {
    if (i !== firstScored) {
      recorder.record({
        trialIdx: i,
        n: N,
        glyphIdx: seq[i],
        nbackGlyphIdx: seq[i - N],
        sequenceSeed: seed,
      });
    }
    const resp = seq[i] === seq[i - N] ? 1 : 2;
    recorder.record({
      trialIdx: i,
      n: N,
      glyphIdx: seq[i],
      nbackGlyphIdx: seq[i - N],
      resp,
      rt: 500 + i,
      sequenceSeed: seed,
    });
  }

  const blockRows = recorder.trials.filter((t) => t.block === recorder.block);
  ok(blockRows.length === TOTAL_TRIALS, `N=${N} one row per trial after updates`);
  ok(recorder.scoredTrials(recorder.block).length === scoredCountForN(N), `N=${N} scored row count`);
  ok(recorder.respondedScoredTrials(recorder.block).length === scoredCountForN(N), `N=${N} answered row count`);
  ok(hasCompleteBlock(recorder, recorder.block), `N=${N} complete block recognized`);
  ok(recorder.accuracy(recorder.block) === 100, `N=${N} accuracy ignores pending and counts answered`);
  ok(blockRows.filter((t) => t.CRESP === 1).length === MATCH_COUNT, `N=${N} logged matches`);
  ok(
    blockRows.filter((t) => t.CRESP !== 1).length === NON_MATCH_PAINTING_COUNT,
    `N=${N} logged nonmatches`,
  );
}

let failed = 0;
function ok(cond, msg) {
  if (!cond) {
    console.error("FAIL:", msg);
    failed++;
  }
}

for (const N of [1, 3]) {
  for (let t = 0; t < 2000; t++) {
    const legacySeed = `verify-n${N}-${t}`;
    const seq = genSeqBlock(N, legacySeed);
    ok(seq.length === 70, `N=${N} length`);
    ok(countScoredMatches(seq, N) === 30, `N=${N} matches t=${t}`);
    ok(countNonMatchPaintings(seq, N) === 40, `N=${N} nonmatches t=${t}`);
    ok(scoredNonMatchCountForN(N) + N === NON_MATCH_PAINTING_COUNT, `N=${N} nonmatch accounting`);
    ok(scoredCountForN(N) + N === 70, `N=${N} observe+scored`);
    ok(
      JSON.stringify(seq) === JSON.stringify(genSeqBlock(N, legacySeed)),
      `N=${N} deterministic legacy replay t=${t}`,
    );
    ok(!sequenceSeedUsesSpreadAlgorithm(legacySeed), `N=${N} legacy seed tagged t=${t}`);

    const v2Seed = `gm-v2-verify-n${N}-${t}`;
    const spread = genSeqBlock(N, v2Seed);
    ok(sequenceSeedUsesSpreadAlgorithm(v2Seed), `N=${N} v2 seed tagged t=${t}`);
    ok(
      JSON.stringify(spread) === JSON.stringify(genSeqBlockSpread(N, v2Seed)),
      `N=${N} deterministic v2 replay t=${t}`,
    );
    ok(
      maxConsecutiveSameGlyph(spread) <= MAX_CONSECUTIVE_SAME_GLYPH,
      `N=${N} v2 max same-glyph run t=${t}`,
    );
  }
  console.log(`N=${N}: 2000 legacy + v2 sequences OK`);
}

const replayA = genSeqBlock(3, "fixed-seed-a");
const replayB = genSeqBlock(3, "fixed-seed-b");
ok(JSON.stringify(replayA) !== JSON.stringify(replayB), "different seeds should usually differ");

const recorder = makeRecorder();
simulateBlock(recorder, 1, "record-n1");
recorder.block = 2;
simulateBlock(recorder, 3, "record-n3");
ok(hasCompleteBlock(recorder, 1) && hasCompleteBlock(recorder, 2), "two complete blocks recognized");
ok(recorder.trials.length === 140, "two blocks log 140 rows");

const auditMeta = {
  rows_total: recorder.trials.length,
  paintingsPerBlock: TOTAL_TRIALS,
  block1_sequenceSeed: "record-n1",
  block1_matchPaintings_logged: MATCH_COUNT,
  block1_nonMatchPaintings_logged: NON_MATCH_PAINTING_COUNT,
  block2_sequenceSeed: "record-n3",
  block2_matchPaintings_logged: MATCH_COUNT,
  block2_nonMatchPaintings_logged: NON_MATCH_PAINTING_COUNT,
};
const audit = auditExportData(recorder.trials, auditMeta, { strict: true });
ok(audit.ok, "simulated export passes audit-export checks");
if (!audit.ok) {
  for (const issue of audit.issues) console.error("  audit:", issue);
}

console.log(failed ? `\n${failed} failure(s)` : "\nAll checks passed.");
process.exit(failed ? 1 : 0);
