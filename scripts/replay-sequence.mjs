/**
 * Replay and print a block sequence from sequenceSeed (same as index.html export).
 *
 * Usage:
 *   node scripts/replay-sequence.mjs --n 1 --seed "gm-mpvgyegf-b1-n1-1g4934c-1tkpxbo"
 */
import { TOTAL_TRIALS, genSeqBlock, glyphIdForIndex } from "./glyphmind-core.mjs";

function usage() {
  console.error(`Usage: node scripts/replay-sequence.mjs --n <1|3> --seed "<sequenceSeed>"`);
  process.exit(1);
}

function parseArgs(argv) {
  let N = null;
  let seed = null;
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--n" || a === "-n") N = Number(argv[++i]);
    else if (a === "--seed" || a === "-s") seed = argv[++i];
    else if (a === "--help" || a === "-h") usage();
  }
  return { N, seed };
}

const { N, seed } = parseArgs(process.argv.slice(2));
if (!Number.isInteger(N) || (N !== 1 && N !== 3)) usage();
if (!seed) usage();

const seq = genSeqBlock(N, seed);
for (let i = 0; i < TOTAL_TRIALS; i++) {
  console.log(`p${i + 1}\t${glyphIdForIndex(seq[i])}`);
}
