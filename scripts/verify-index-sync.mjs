/**
 * Drift guard: the browser sequence generator in index.html is a hand-maintained
 * copy of scripts/glyphmind-core.mjs (ES imports can't run over file://, which the
 * README's double-click distribution requires). Nothing forced the two copies to
 * agree — this does. It extracts index.html's genSeqBlock chain, runs it and the
 * core module on the same seeds, and fails if any produced sequence differs.
 *
 * Run: node scripts/verify-index-sync.mjs
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import vm from "node:vm";
import * as core from "./glyphmind-core.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const html = readFileSync(join(here, "..", "index.html"), "utf8");

// Symbols index.html's genSeqBlock chain depends on, in dependency order.
// makeSequenceSeed is intentionally omitted: it touches window.crypto and is only
// the empty-seed fallback, never hit here because every seed we test is non-empty.
const SYMBOLS = [
  "TOTAL_TRIALS", "MATCH_COUNT", "NON_MATCH_PAINTING_COUNT",
  "GLYPHS", "N_GLYPHS", "MAX_CONSECUTIVE_SAME_GLYPH",
  "scoredCountForN", "matchCountForBlock", "scoredNonMatchCountForN",
  "hashSeed", "rngFromSeed", "randInt", "randPick", "shuffle",
  "countScoredMatches", "pickNonMatchGlyph",
  "maxConsecutiveTrue", "maxConsecutiveSameGlyph",
  "pickObserveGlyphs", "buildIsMatchFlags",
  "validateBlockSequence", "sequenceSeedUsesSpreadAlgorithm",
  "genSeqBlockLegacy", "genSeqBlockSpread", "genSeqBlock",
];

// ponytail: naive brace/bracket balance, no JS parser. Assumes no string literal in
// these defs holds an unbalanced { } [ ( ). True today. If a future edit adds one,
// swap this for acorn instead of hand-patching — it's the one place both copies meet.
function grab(name) {
  const re = new RegExp(`(?:^|\\n)\\s*(function\\s+${name}\\s*\\(|const\\s+${name}\\s*=)`);
  const m = re.exec(html);
  if (!m) throw new Error(`symbol not found in index.html: ${name}`);
  const start = m.index + m[0].indexOf(m[1]);
  const isFn = m[1].startsWith("function");
  if (isFn) {
    const bodyStart = html.indexOf("{", start);
    let depth = 0;
    for (let j = bodyStart; j < html.length; j++) {
      const c = html[j];
      if (c === "{") depth++;
      else if (c === "}" && --depth === 0) return html.slice(start, j + 1);
    }
  } else {
    let depth = 0;
    for (let j = start; j < html.length; j++) {
      const c = html[j];
      if (c === "{" || c === "[" || c === "(") depth++;
      else if (c === "}" || c === "]" || c === ")") depth--;
      else if (c === ";" && depth === 0) return html.slice(start, j + 1);
    }
  }
  throw new Error(`unterminated def for ${name}`);
}

const source = SYMBOLS.map(grab).join("\n\n") +
  "\n\nmodule.exports = { genSeqBlock, genSeqBlockLegacy, genSeqBlockSpread };";
const sandbox = { module: { exports: {} }, Math, Number, Array, Uint32Array, Object, String, Error };
vm.runInNewContext(source, sandbox, { filename: "index.html:extracted" });
const idx = sandbox.module.exports;

// Seeds: legacy (no gm-v2 prefix) hits genSeqBlockLegacy; gm-v2 prefix hits Spread.
const seeds = [];
for (let i = 0; i < 40; i++) seeds.push(`legacy-${i}`, `gm-v2-b0-n1-${i.toString(36)}`);

let checked = 0;
for (const N of [1, 3]) {
  for (const seed of seeds) {
    const a = core.genSeqBlock(N, seed);
    const b = idx.genSeqBlock(N, seed);
    if (a.length !== 70 || b.length !== 70)
      throw new Error(`length != 70 for N=${N} seed=${seed}: core=${a.length} idx=${b.length}`);
    const at = JSON.stringify(a), bt = JSON.stringify(b);
    if (at !== bt) {
      const d = a.findIndex((v, k) => v !== b[k]);
      console.error(`DRIFT: index.html and glyphmind-core.mjs disagree.`);
      console.error(`  N=${N} seed=${seed} first diff at trial ${d}: core=${a[d]} index=${b[d]}`);
      console.error(`  core : ${at}`);
      console.error(`  index: ${bt}`);
      process.exit(1);
    }
    checked++;
  }
}
console.log(`in sync: ${checked} sequences identical across N={1,3}, ${seeds.length} seeds each.`);
