/**
 * Validate a GLYPHMIND .xlsx export (Trials + Meta sheets).
 *
 * Usage:
 *   node scripts/audit-export.mjs path/to/export.xlsx
 *   node scripts/audit-export.mjs path/to/export.xlsx --strict
 *
 * --strict  fail if any scored row is missing Resp (partial / mid-block export)
 */
import { readFileSync, existsSync } from "fs";
import { createRequire } from "module";
import path from "path";
import { fileURLToPath } from "url";
import {
  TOTAL_TRIALS,
  MATCH_COUNT,
  NON_MATCH_PAINTING_COUNT,
  GLYPHS,
  genSeqBlock,
  glyphIdForIndex,
  scoredCountForN,
} from "./glyphmind-core.mjs";

const PRACTICE_TRIALS = 20;

function scoredCountForTrials(N, totalTrials) {
  return totalTrials - N;
}

function matchCountForBlock(N, totalTrials = TOTAL_TRIALS) {
  const scored = scoredCountForTrials(N, totalTrials);
  const fullScored = scoredCountForN(N);
  if (scored <= 0 || fullScored <= 0) return 0;
  return Math.max(1, Math.min(scored, Math.round((MATCH_COUNT * scored) / fullScored)));
}

function isSessionTrialType(trialType) {
  return trialType !== "practice" && trialType !== "practice_warmup";
}

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const XLSX = require(path.join(__dirname, "../lib/xlsx.full.min.js"));

const REQUIRED_TRIAL_COLUMNS = [
  "block",
  "nback",
  "trialType",
  "trial",
  "CRESP",
  "Resp",
  "ACC",
  "RT",
  "RSI",
];

function nbackFromRow(row) {
  if (row.nback !== undefined && row.nback !== "") return asInt(row.nback);
  return asInt(row.N);
}

function blank(v) {
  return v === "" || v === null || typeof v === "undefined";
}

function asInt(v) {
  if (blank(v)) return null;
  const n = Number(v);
  return Number.isFinite(n) ? Math.trunc(n) : null;
}

function asStr(v) {
  return blank(v) ? "" : String(v).trim();
}

function hasResp(v) {
  const n = asInt(v);
  return n === 1 || n === 2;
}

function parseMetaSheet(sheet) {
  const rows = XLSX.utils.sheet_to_json(sheet, { header: 1, defval: "" });
  const meta = {};
  for (let i = 0; i < rows.length; i++) {
    const key = asStr(rows[i][0]);
    if (!key || key === "key") continue;
    meta[key] = rows[i][1];
  }
  return meta;
}

function parseTrialsSheet(sheet) {
  const rows = XLSX.utils.sheet_to_json(sheet, { defval: "" });
  return rows.filter((row) => !Object.values(row).every(blank));
}

function groupByBlock(trials) {
  const blocks = new Map();
  for (const row of trials) {
    const block = asInt(row.block);
    if (block == null) continue;
    if (!blocks.has(block)) blocks.set(block, []);
    blocks.get(block).push(row);
  }
  return [...blocks.entries()].sort((a, b) => a[0] - b[0]);
}

function trialNum(row) {
  const n = asInt(row.trial);
  if (n != null) return n;
  return asInt(row.painting);
}

function glyphIndexFromRow(row) {
  const ch = asStr(row.StimulusChar);
  if (ch) {
    const idx = GLYPHS.findIndex((g) => g.ch === ch);
    if (idx >= 0) return idx;
  }
  const trig = asInt(row.TriggerCondition);
  if (trig != null && trig >= 1) return trig - 1;
  return null;
}

function sequenceFromRows(rows) {
  const sorted = [...rows].sort((a, b) => trialNum(a) - trialNum(b));
  return sorted.map((row) => glyphIndexFromRow(row));
}

function auditBlock(blockNum, rows, meta, issues, options) {
  const prefix = `block ${blockNum}`;

  if (rows.length !== TOTAL_TRIALS) {
    issues.push(`${prefix}: expected ${TOTAL_TRIALS} rows, got ${rows.length}`);
    return;
  }

  const trials = rows.map((r) => trialNum(r));
  const trialSet = new Set(trials);
  if (trialSet.size !== TOTAL_TRIALS) {
    issues.push(`${prefix}: trial numbers are not unique 1..${TOTAL_TRIALS}`);
  }
  for (let p = 1; p <= TOTAL_TRIALS; p++) {
    if (!trialSet.has(p)) issues.push(`${prefix}: missing trial ${p}`);
  }

  const N = nbackFromRow(rows[0]);
  if (N == null || N < 1) {
    issues.push(`${prefix}: invalid nback`);
    return;
  }
  if (rows.some((r) => nbackFromRow(r) !== N)) {
    issues.push(`${prefix}: inconsistent nback across rows`);
  }

  const seed =
    asStr(meta[`block${blockNum}_sequenceSeed`]) || asStr(rows[0].sequenceSeed);
  if (!seed) issues.push(`${prefix}: missing sequenceSeed (Meta block${blockNum}_sequenceSeed)`);

  const warmupRows = rows.filter((r) => asStr(r.trialType) === "warmup");
  const scoredRows = rows.filter((r) => asStr(r.trialType) === "scored");
  const otherTypes = rows.filter(
    (r) => !["warmup", "scored", "practice", "practice_warmup"].includes(asStr(r.trialType)),
  );

  if (otherTypes.length) issues.push(`${prefix}: invalid trialType values`);
  if (warmupRows.length !== N) {
    issues.push(`${prefix}: expected ${N} warmup rows, got ${warmupRows.length}`);
  }
  if (scoredRows.length !== scoredCountForN(N)) {
    issues.push(
      `${prefix}: expected ${scoredCountForN(N)} scored rows, got ${scoredRows.length}`,
    );
  }

  const matchLogged = rows.filter((r) => asInt(r.CRESP) === 1).length;
  const nonMatchLogged = rows.filter((r) => asInt(r.CRESP) !== 1).length;
  if (matchLogged !== MATCH_COUNT) {
    issues.push(`${prefix}: expected ${MATCH_COUNT} CRESP=1 rows, got ${matchLogged}`);
  }
  if (nonMatchLogged !== NON_MATCH_PAINTING_COUNT) {
    issues.push(
      `${prefix}: expected ${NON_MATCH_PAINTING_COUNT} non-match rows (CRESP!=1), got ${nonMatchLogged}`,
    );
  }

  const metaSeed = asStr(meta[`block${blockNum}_sequenceSeed`]);
  if (metaSeed && seed && metaSeed !== seed) {
    issues.push(`${prefix}: Meta sequenceSeed mismatch (${metaSeed} vs ${seed})`);
  }
  const metaMatch = asInt(meta[`block${blockNum}_matchPaintings_logged`]);
  const metaNonMatch = asInt(meta[`block${blockNum}_nonMatchPaintings_logged`]);
  if (metaMatch != null && metaMatch !== matchLogged) {
    issues.push(`${prefix}: Meta match count mismatch (${metaMatch} vs ${matchLogged})`);
  }
  if (metaNonMatch != null && metaNonMatch !== nonMatchLogged) {
    issues.push(`${prefix}: Meta non-match count mismatch (${metaNonMatch} vs ${nonMatchLogged})`);
  }

  let pendingScored = 0;

  for (const row of rows) {
    const trial = trialNum(row);
    const trialType = asStr(row.trialType);

    const stimIdx = glyphIndexFromRow(row);

    const rsi = asInt(row.RSI);
    if (rsi != null && rsi < 0) {
      issues.push(`${prefix} trial ${trial}: negative RSI (${rsi})`);
    }

    if (trialType === "warmup") {
      if (!blank(row.CRESP) || !blank(row.Resp) || !blank(row.ACC) || !blank(row.RT)) {
        issues.push(`${prefix} trial ${trial}: warmup must leave CRESP/Resp/ACC/RT blank`);
      }
      if (!blank(row.isMatch)) {
        issues.push(`${prefix} trial ${trial}: warmup must leave isMatch blank`);
      }
      continue;
    }

    if (trialType !== "scored") continue;

    const targetIdx =
      trial > N
        ? glyphIndexFromRow(rows.find((r) => trialNum(r) === trial - N) || {})
        : null;
    const cresp =
      stimIdx != null && targetIdx != null && stimIdx === targetIdx ? 1 : 2;
    const loggedCresp = asInt(row.CRESP);

    if (loggedCresp !== cresp) {
      issues.push(`${prefix} trial ${trial}: CRESP ${loggedCresp} != expected ${cresp}`);
    }

    const expectedIsMatch = cresp === 1 ? 1 : 0;
    const loggedIsMatch = asInt(row.isMatch);
    if (loggedIsMatch != null && loggedIsMatch !== expectedIsMatch) {
      issues.push(`${prefix} trial ${trial}: isMatch ${loggedIsMatch} != expected ${expectedIsMatch}`);
    }

    if (trial <= N) {
      issues.push(`${prefix} trial ${trial}: scored row inside warmup range`);
    }

    const nbackTrial = trial - N;
    const nbackRow = rows.find((r) => trialNum(r) === nbackTrial);
    if (nbackRow && glyphIndexFromRow(nbackRow) !== targetIdx) {
      issues.push(
        `${prefix} trial ${trial}: n-back stimulus mismatch at trial ${nbackTrial}`,
      );
    }

    if (hasResp(row.Resp)) {
      const resp = asInt(row.Resp);
      const acc = asInt(row.ACC);
      const rt = asInt(row.RT);

      if (acc !== (resp === cresp ? 1 : 0)) {
        issues.push(`${prefix} trial ${trial}: ACC ${acc} inconsistent with Resp/CRESP`);
      }
      if (rt == null || rt <= 0) {
        issues.push(`${prefix} trial ${trial}: answered scored row needs RT > 0`);
      }
    } else {
      pendingScored++;
      if (options.strict) {
        issues.push(`${prefix} trial ${trial}: scored row missing Resp (--strict)`);
      }
    }
  }

  if (seed) {
    try {
      const expectedSeq = genSeqBlock(N, seed);
      const loggedSeq = sequenceFromRows(rows);
      for (let i = 0; i < TOTAL_TRIALS; i++) {
        const expectedId = glyphIdForIndex(expectedSeq[i]);
        const loggedId = glyphIdForIndex(loggedSeq[i]);
        if (expectedId !== loggedId) {
          issues.push(
            `${prefix}: sequenceSeed replay mismatch at trial ${i + 1} (${loggedId} vs ${expectedId})`,
          );
          break;
        }
      }
    } catch (err) {
      issues.push(`${prefix}: sequenceSeed replay failed (${err.message})`);
    }
  }

  return { N, seed, pendingScored, matchLogged, nonMatchLogged, kind: "session" };
}

function auditPracticeBlock(blockNum, rows, issues, options) {
  const prefix = `block ${blockNum} practice`;

  if (rows.length !== PRACTICE_TRIALS) {
    issues.push(`${prefix}: expected ${PRACTICE_TRIALS} rows, got ${rows.length}`);
    return;
  }

  const N = nbackFromRow(rows[0]);
  if (N == null || N < 1) {
    issues.push(`${prefix}: invalid nback`);
    return;
  }
  if (rows.some((r) => nbackFromRow(r) !== N)) {
    issues.push(`${prefix}: inconsistent nback across rows`);
  }

  const warmupRows = rows.filter((r) => asStr(r.trialType) === "practice_warmup");
  const scoredRows = rows.filter((r) => asStr(r.trialType) === "practice");
  const badTypes = rows.filter(
    (r) => !["practice", "practice_warmup"].includes(asStr(r.trialType)),
  );
  if (badTypes.length) issues.push(`${prefix}: invalid trialType values`);
  if (warmupRows.length !== N) {
    issues.push(`${prefix}: expected ${N} practice_warmup rows, got ${warmupRows.length}`);
  }
  const expectedScored = scoredCountForTrials(N, PRACTICE_TRIALS);
  if (scoredRows.length !== expectedScored) {
    issues.push(
      `${prefix}: expected ${expectedScored} practice rows, got ${scoredRows.length}`,
    );
  }

  const matchTarget = matchCountForBlock(N, PRACTICE_TRIALS);
  const matchLogged = rows.filter((r) => asInt(r.isMatchPainting) === 1).length;
  const nonMatchLogged = rows.filter((r) => asInt(r.isMatchPainting) === 0).length;
  const nonMatchTarget = PRACTICE_TRIALS - matchTarget;
  if (matchLogged !== matchTarget) {
    issues.push(`${prefix}: expected ${matchTarget} isMatchPainting=1 rows, got ${matchLogged}`);
  }
  if (nonMatchLogged !== nonMatchTarget) {
    issues.push(
      `${prefix}: expected ${nonMatchTarget} isMatchPainting=0 rows, got ${nonMatchLogged}`,
    );
  }

  let pendingScored = 0;
  if (options.strict) {
    for (const row of scoredRows) {
      if (!hasResp(row.Resp)) pendingScored++;
    }
    if (pendingScored) {
      issues.push(`${prefix}: ${pendingScored} practice scored row(s) missing Resp (--strict)`);
    }
  }

  for (const row of scoredRows) {
    if (hasResp(row.Resp) && asInt(row.ACC) !== (asInt(row.CRESP) === asInt(row.Resp) ? 1 : 0)) {
      issues.push(`${prefix} trial ${trialNum(row)}: ACC does not match CRESP/Resp`);
    }
  }

  return { N, seed: asStr(rows[0].sequenceSeed), pendingScored, matchLogged, nonMatchLogged, kind: "practice" };
}

/**
 * @param {object[]} trials
 * @param {Record<string, unknown>} meta
 * @param {{ strict?: boolean }} options
 */
export function auditExportData(trials, meta = {}, options = {}) {
  const issues = [];

  if (!trials.length) {
    issues.push("Trials sheet is empty");
    return { ok: false, issues, blocks: [] };
  }

  const missingCols = REQUIRED_TRIAL_COLUMNS.filter((col) => {
    if (col === "nback") {
      return !Object.prototype.hasOwnProperty.call(trials[0], "nback") &&
        !Object.prototype.hasOwnProperty.call(trials[0], "N");
    }
    return !Object.prototype.hasOwnProperty.call(trials[0], col);
  });
  if (missingCols.length) {
    issues.push(`Trials sheet missing columns: ${missingCols.join(", ")}`);
  }

  const metaRowsTotal = asInt(meta.rows_total);
  if (metaRowsTotal != null && metaRowsTotal !== trials.length) {
    issues.push(`Meta rows_total (${metaRowsTotal}) != Trials row count (${trials.length})`);
  }

  const blockGroups = groupByBlock(trials);
  const blockSummaries = [];

  for (const [blockNum, rows] of blockGroups) {
    const sessionRows = rows.filter((r) => isSessionTrialType(asStr(r.trialType)));
    const practiceRows = rows.filter((r) => {
      const tt = asStr(r.trialType);
      return tt === "practice" || tt === "practice_warmup";
    });
    if (practiceRows.length) {
      issues.push(`block ${blockNum}: unexpected practice rows in export (${practiceRows.length})`);
    }
    if (sessionRows.length) {
      blockSummaries.push(auditBlock(blockNum, sessionRows, meta, issues, options));
    }
  }

  const metaPaintings = asInt(meta.paintingsPerBlock);
  if (metaPaintings != null && metaPaintings !== TOTAL_TRIALS) {
    issues.push(`Meta paintingsPerBlock (${metaPaintings}) != ${TOTAL_TRIALS}`);
  }

  return {
    ok: issues.length === 0,
    issues,
    blocks: blockSummaries.filter(Boolean),
    trialCount: trials.length,
    blockCount: blockGroups.length,
  };
}

export function auditWorkbook(wb, options = {}) {
  if (!wb.Sheets?.Trials) {
    return { ok: false, issues: ["Workbook missing Trials sheet"], blocks: [] };
  }
  const trials = parseTrialsSheet(wb.Sheets.Trials);
  const meta = wb.Sheets.Meta ? parseMetaSheet(wb.Sheets.Meta) : {};
  return auditExportData(trials, meta, options);
}

export function auditXlsxFile(filePath, options = {}) {
  if (!existsSync(filePath)) {
    return { ok: false, issues: [`File not found: ${filePath}`], blocks: [] };
  }
  const wb = XLSX.read(readFileSync(filePath), { type: "buffer" });
  const result = auditWorkbook(wb, options);
  result.file = path.resolve(filePath);
  return result;
}

function printReport(result) {
  const label = result.file || "in-memory export";
  console.log(`Audit: ${label}`);
  console.log(`  Trials: ${result.trialCount ?? 0} rows across ${result.blockCount ?? 0} block(s)`);
  if (result.blocks?.length) {
    for (const b of result.blocks) {
      if (!b) continue;
      const pendingNote = b.pendingScored ? `, ${b.pendingScored} pending scored` : "";
      console.log(
        `  Block: N=${b.N}, seed=${b.seed || "?"}, matches=${b.matchLogged}, nonmatches=${b.nonMatchLogged}${pendingNote}`,
      );
    }
  }
  if (result.ok) {
    console.log("\nAll export checks passed.");
    return 0;
  }
  console.error(`\n${result.issues.length} issue(s):`);
  for (const issue of result.issues) console.error(`  - ${issue}`);
  return 1;
}

const args = process.argv.slice(2);
const strict = args.includes("--strict");
const fileArg = args.find((a) => !a.startsWith("--"));

const isMain =
  process.argv[1] &&
  path.resolve(process.argv[1]) === path.resolve(fileURLToPath(import.meta.url));

if (isMain) {
  if (!fileArg) {
    console.error("Usage: node scripts/audit-export.mjs path/to/export.xlsx [--strict]");
    process.exit(2);
  }
  process.exit(printReport(auditXlsxFile(fileArg, { strict })));
}
