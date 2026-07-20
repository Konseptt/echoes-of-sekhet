/**
 * Shared GLYPHMIND sequence + stimulus constants (mirrors index.html).
 */
export const TOTAL_TRIALS = 70;
export const MATCH_COUNT = 30;
export const NON_MATCH_PAINTING_COUNT = TOTAL_TRIALS - MATCH_COUNT;

export const GLYPHS = [
  { ch: "\u{13080}", id: "D010", name: "Eye (D10)", u: "U+13080" },
  { ch: "\u{1308B}", id: "D021", name: "Mouth (D21)", u: "U+1308B" },
  { ch: "\u{1309D}", id: "D036", name: "Hand (D36)", u: "U+1309D" },
  { ch: "\u{13153}", id: "G017", name: "Owl (G17)", u: "U+13153" },
  { ch: "\u{13184}", id: "H006", name: "Feather (H6)", u: "U+13184" },
  { ch: "\u{13191}", id: "I009", name: "Horned viper (I9)", u: "U+13191" },
  { ch: "\u{13193}", id: "I010", name: "Cobra (I10)", u: "U+13193" },
  { ch: "\u{13216}", id: "N035", name: "Water (N35)", u: "U+13216" },
  { ch: "\u{131FC}", id: "N014", name: "Star (N14)", u: "U+131FC" },
  { ch: "\u{133CF}", id: "X001", name: "Loaf (X1)", u: "U+133CF" },
  { ch: "\u{131F3}", id: "N005", name: "Sun (N5)", u: "U+131F3" },
  { ch: "\u{132BD}", id: "R011", name: "Djed pillar (R11)", u: "U+132BD" },
];

export const N_GLYPHS = GLYPHS.length;

export const GLYPH_ID_TO_INDEX = Object.fromEntries(GLYPHS.map((g, i) => [g.id, i]));
export const GLYPH_INDEX_TO_ID = GLYPHS.map((g) => g.id);

export function hashSeed(seed) {
  const s = String(seed || "glyphmind");
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0 || 0x6d2b79f5;
}

export function rngFromSeed(seed) {
  let a = hashSeed(seed);
  return function () {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t ^= t + Math.imul(t ^ (t >>> 7), 61 | t);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function randInt(n, rng = Math.random) {
  return Math.floor(rng() * n);
}

export function randPick(arr, rng = Math.random) {
  return arr[randInt(arr.length, rng)];
}

export function shuffle(arr, rng = Math.random) {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = randInt(i + 1, rng);
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

export function scoredCountForN(N) {
  return TOTAL_TRIALS - N;
}

export function scoredNonMatchCountForN(N) {
  return scoredCountForN(N) - MATCH_COUNT;
}

export function pickNonMatchGlyph(refGlyph, rng = Math.random) {
  const pool = [];
  for (let g = 0; g < N_GLYPHS; g++) if (g !== refGlyph) pool.push(g);
  return randPick(pool, rng);
}

/** Longest run of consecutive `true` in a boolean array. */
export function maxConsecutiveTrue(flags) {
  let max = 0;
  let run = 0;
  for (const f of flags) {
    if (f) {
      run++;
      if (run > max) max = run;
    } else run = 0;
  }
  return max;
}

/** Longest run of the same glyph index in a sequence. */
export function maxConsecutiveSameGlyph(seq) {
  if (!seq.length) return 0;
  let max = 1;
  let run = 1;
  for (let i = 1; i < seq.length; i++) {
    if (seq[i] === seq[i - 1]) {
      run++;
      if (run > max) max = run;
    } else run = 1;
  }
  return max;
}

/** Observe-phase glyphs: distinct when N > 1 (N is only 1 or 3 in this app). */
export function pickObserveGlyphs(N, rng = Math.random) {
  if (N <= 1) return [randInt(N_GLYPHS, rng)];
  const pool = shuffle(
    Array.from({ length: N_GLYPHS }, (_, i) => i),
    rng,
  );
  return pool.slice(0, N);
}

/**
 * Place exactly MATCH_COUNT match flags among scored trials, spreading matches
 * so we avoid long 1-back streaks (e.g. six identical glyphs in a row).
 */
export function buildIsMatchFlags(scoredN, rng = Math.random) {
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
        if (placed >= MATCH_COUNT) break;
        isMatch[j] = true;
        if (maxConsecutiveTrue(isMatch) > maxConsecutive) {
          isMatch[j] = false;
        } else {
          placed++;
        }
      }
      if (placed === MATCH_COUNT && maxConsecutiveTrue(isMatch) <= maxConsecutive) {
        return isMatch;
      }
    }
  }
  const isMatch = new Array(scoredN).fill(false);
  const matchable = shuffle(
    Array.from({ length: scoredN }, (_, j) => j),
    rng,
  );
  for (let i = 0; i < MATCH_COUNT; i++) isMatch[matchable[i]] = true;
  return isMatch;
}

export const MAX_CONSECUTIVE_SAME_GLYPH = 5;
export const SEQUENCE_SEED_VERSION = "v2";

/** New blocks use spread match placement; legacy `gm-...` seeds replay the old algorithm. */
export function sequenceSeedUsesSpreadAlgorithm(seed) {
  const parts = String(seed || "").split("-");
  return parts[0] === "gm" && parts[1] === SEQUENCE_SEED_VERSION;
}

export function countScoredMatches(sequence, N) {
  let matches = 0;
  for (let i = N; i < TOTAL_TRIALS; i++) {
    if (sequence[i] !== undefined && sequence[i - N] !== undefined && sequence[i] === sequence[i - N]) {
      matches++;
    }
  }
  return matches;
}

export function countNonMatchPaintings(sequence, N) {
  return TOTAL_TRIALS - countScoredMatches(sequence, N);
}

export function genSeqBlockLegacy(N, seed) {
  const rng = rngFromSeed(seed);
  for (let tryNum = 0; tryNum < 16; tryNum++) {
    const seq = new Array(TOTAL_TRIALS);
    const scoredN = scoredCountForN(N);
    for (let i = 0; i < N; i++) seq[i] = randInt(N_GLYPHS, rng);
    const isMatch = new Array(scoredN).fill(false);
    const matchable = Array.from({ length: scoredN }, (_, j) => j);
    shuffle(matchable, rng);
    for (let i = 0; i < MATCH_COUNT; i++) isMatch[matchable[i]] = true;
    for (let j = 0; j < scoredN; j++) {
      const i = N + j;
      const ref = seq[i - N];
      seq[i] = isMatch[j] ? ref : pickNonMatchGlyph(ref, rng);
    }
    for (let k = 0; k < 32; k++) {
      if (countScoredMatches(seq, N) === MATCH_COUNT) break;
      for (let j = 0; j < scoredN; j++) {
        const i = N + j;
        const ref = seq[i - N];
        if (isMatch[j]) seq[i] = ref;
        else seq[i] = pickNonMatchGlyph(ref, rng);
      }
    }
    const allAssigned = seq.every((v) => Number.isInteger(v) && v >= 0 && v < N_GLYPHS);
    if (countScoredMatches(seq, N) === MATCH_COUNT && allAssigned) {
      validateBlockSequence(N, seq);
      return seq;
    }
  }
  throw new Error(`Could not build a valid ${N}-back sequence`);
}

export function genSeqBlockSpread(N, seed) {
  const rng = rngFromSeed(seed);
  const observeGlyphs = pickObserveGlyphs(N, rng);
  for (let tryNum = 0; tryNum < 64; tryNum++) {
    const seq = new Array(TOTAL_TRIALS);
    const scoredN = scoredCountForN(N);
    for (let i = 0; i < N; i++) seq[i] = observeGlyphs[i];
    const isMatch = buildIsMatchFlags(scoredN, rng);
    for (let j = 0; j < scoredN; j++) {
      const i = N + j;
      const ref = seq[i - N];
      seq[i] = isMatch[j] ? ref : pickNonMatchGlyph(ref, rng);
    }
    for (let k = 0; k < 32; k++) {
      if (countScoredMatches(seq, N) === MATCH_COUNT) break;
      for (let j = 0; j < scoredN; j++) {
        const i = N + j;
        const ref = seq[i - N];
        if (isMatch[j]) seq[i] = ref;
        else seq[i] = pickNonMatchGlyph(ref, rng);
      }
    }
    const allAssigned = seq.every((v) => Number.isInteger(v) && v >= 0 && v < N_GLYPHS);
    const sameGlyphRun = maxConsecutiveSameGlyph(seq);
    if (
      countScoredMatches(seq, N) === MATCH_COUNT &&
      allAssigned &&
      sameGlyphRun <= MAX_CONSECUTIVE_SAME_GLYPH
    ) {
      validateBlockSequence(N, seq);
      return seq;
    }
  }
  throw new Error(`Could not build a valid ${N}-back sequence`);
}

export function genSeqBlock(N, seed) {
  if (sequenceSeedUsesSpreadAlgorithm(seed)) return genSeqBlockSpread(N, seed);
  return genSeqBlockLegacy(N, seed);
}

export function glyphIdForIndex(gi) {
  return GLYPH_INDEX_TO_ID[gi];
}

export function indexForGlyphId(id) {
  const idx = GLYPH_ID_TO_INDEX[id];
  if (idx === undefined) throw new Error(`Unknown Stimulus id: ${id}`);
  return idx;
}

export function validateBlockSequence(N, seq) {
  if (!Array.isArray(seq) || seq.length !== TOTAL_TRIALS) {
    throw new Error(`Block sequence must have ${TOTAL_TRIALS} paintings (got ${seq ? seq.length : 0})`);
  }
  if (countScoredMatches(seq, N) !== MATCH_COUNT) {
    throw new Error(`Block sequence must have ${MATCH_COUNT} scored N-back matches (got ${countScoredMatches(seq, N)})`);
  }
  if (N + scoredNonMatchCountForN(N) !== NON_MATCH_PAINTING_COUNT) {
    throw new Error(
      `Block must account for ${NON_MATCH_PAINTING_COUNT} non-match paintings (${N} observe + ${scoredNonMatchCountForN(N)} scored non-match)`,
    );
  }
}

export function expectedCresp(stimulusId, targetId) {
  return stimulusId === targetId ? 1 : 2;
}
