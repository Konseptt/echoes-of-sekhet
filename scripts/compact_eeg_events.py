#!/usr/bin/env python3
"""
Compact GLYPHMIND stim/response markers into one trial-aligned event table for EEG.

Pairs STIM_ONSET / STIM_OBSERVE with the following RESP_MATCH / RESP_NO_MATCH on the
same (block, trial), then writes a CSV ready for MNE Annotations / EEGLAB epoching.

Sources (any combination that yields markers):
  --markers   CSV from lsl_marker_bridge.py (--log)
  --xdf       LabRecorder .xdf (needs: pip install pyxdf)
  --xlsx      Game export (Events sheet preferred; Trials used for ACC/CRESP)

Photodiode optical codes (one sensor on bottom-right square → trigger channel):
  stim  = single ~120 ms white pulse
  resp  = two ~40 ms white pulses separated by ~40 ms black

Example:
  python3 scripts/compact_eeg_events.py \\
    --markers logs/markers.csv \\
    --xlsx Glyphmind_P001_S1.xlsx \\
    -o compact_events.csv

  python3 scripts/compact_eeg_events.py --xdf session.xdf --xlsx export.xlsx -o compact.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

STIM_CODES = {10, 11}
RESP_CODES = {20, 21}
STIM_LABELS = {"STIM_ONSET", "STIM_OBSERVE"}
RESP_LABELS = {"RESP_MATCH", "RESP_NO_MATCH"}

MARKER_RE = re.compile(r"^(\d+):([A-Z0-9_]+)(?::(.*))?$")


def parse_code_label(raw: str) -> tuple[int | None, str]:
    text = (raw or "").strip()
    m = MARKER_RE.match(text)
    if m:
        return int(m.group(1)), m.group(2)
    if text.isdigit():
        return int(text), ""
    return None, text


def parse_marker_fields(raw: str) -> dict:
    """Parse `10:STIM_ONSET:b1:t12:n3:scored` into structured fields."""
    text = (raw or "").strip()
    m = MARKER_RE.match(text)
    out: dict = {
        "code": None,
        "label": "",
        "block": None,
        "trial": None,
        "nback": None,
        "trialType": "",
    }
    if not m:
        code, label = parse_code_label(text)
        out["code"] = code
        out["label"] = label
        return out
    out["code"] = int(m.group(1))
    out["label"] = m.group(2)
    rest = m.group(3) or ""
    for part in rest.split(":") if rest else []:
        if part.startswith("b") and part[1:].isdigit():
            out["block"] = int(part[1:])
        elif part.startswith("t") and part[1:].isdigit():
            out["trial"] = int(part[1:])
        elif part.startswith("n") and part[1:].isdigit():
            out["nback"] = int(part[1:])
        elif part in ("practice", "scored", "warmup", "practice_warmup"):
            out["trialType"] = part
    return out


def load_markers_csv(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            code = row.get("code", "")
            label = row.get("label", "")
            try:
                code_i = int(code) if str(code).strip() != "" else None
            except ValueError:
                code_i, label = parse_code_label(str(code))
            rows.append(
                {
                    "source": "markers_csv",
                    "idx": i,
                    "code": code_i,
                    "label": label or "",
                    "time": row.get("received_iso") or row.get("wall_iso") or "",
                    "perf_ms": _float_or_none(row.get("perf_ms")),
                    "block": _int_or_none(row.get("block")),
                    "trial": _int_or_none(row.get("trial")),
                    "nback": _int_or_none(row.get("nback")),
                    "pid": row.get("pid", ""),
                    "session": row.get("session", ""),
                    "raw": row.get("raw_json", ""),
                }
            )
    return rows


def load_markers_xdf(path: Path) -> list[dict]:
    try:
        import pyxdf  # type: ignore
    except ImportError:
        print(
            "pyxdf required for --xdf. Install with: pip install pyxdf",
            file=sys.stderr,
        )
        raise SystemExit(2)

    streams, _ = pyxdf.load_xdf(str(path))
    marker_streams = [
        s
        for s in streams
        if s["info"]["type"][0] == "Markers"
        or "GLYPHMIND" in (s["info"]["name"][0] or "")
    ]
    if not marker_streams:
        print("No Markers / GLYPHMIND stream found in XDF.", file=sys.stderr)
        raise SystemExit(1)

    rows: list[dict] = []
    for stream in marker_streams:
        name = stream["info"]["name"][0]
        times = stream["time_stamps"]
        samples = stream["time_series"]
        for i, (t, sample) in enumerate(zip(times, samples)):
            raw = sample[0] if isinstance(sample, (list, tuple)) else sample
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="replace")
            code, label = parse_code_label(str(raw))
            fields = parse_marker_fields(str(raw))
            rows.append(
                {
                    "source": f"xdf:{name}",
                    "idx": i,
                    "code": fields.get("code", code),
                    "label": fields.get("label") or label,
                    "time": float(t),
                    "perf_ms": None,
                    "block": fields.get("block"),
                    "trial": fields.get("trial"),
                    "nback": fields.get("nback"),
                    "pid": "",
                    "session": "",
                    "raw": str(raw),
                    "trialType": fields.get("trialType") or "",
                }
            )
    return rows


def _load_workbook(path: Path):
    try:
        from openpyxl import load_workbook  # type: ignore
    except ImportError:
        print(
            "openpyxl required for --xlsx. Install with: pip install openpyxl",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return load_workbook(path, read_only=True, data_only=True)


def load_events_xlsx(path: Path) -> list[dict]:
    wb = _load_workbook(path)
    if "Events" not in wb.sheetnames:
        wb.close()
        return []
    ws = wb["Events"]
    headers = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
    header_map = {str(h): i for i, h in enumerate(headers) if h is not None}

    def cell(row, key, default=None):
        i = header_map.get(key)
        if i is None or i >= len(row):
            return default
        return row[i]

    rows: list[dict] = []
    for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True)):
        code = cell(row, "code")
        label = cell(row, "label") or ""
        try:
            code_i = int(code) if code is not None and str(code).strip() != "" else None
        except (TypeError, ValueError):
            code_i, label = parse_code_label(str(code))
        rows.append(
            {
                "source": "xlsx_events",
                "idx": i,
                "code": code_i,
                "label": str(label),
                "time": cell(row, "wallIso") or cell(row, "perfMs") or "",
                "perf_ms": _float_or_none(cell(row, "perfMs")),
                "block": _int_or_none(cell(row, "block")),
                "trial": _int_or_none(cell(row, "trial")),
                "nback": _int_or_none(cell(row, "nback")),
                "pid": cell(row, "pid") or "",
                "session": cell(row, "session") or "",
                "raw": "",
            }
        )
    wb.close()
    return rows


def load_trials_xlsx(path: Path) -> dict[tuple, dict]:
    """Map (block, trial) -> behavioural fields for joining ACC/CRESP/RT."""
    wb = _load_workbook(path)
    if "Trials" not in wb.sheetnames:
        wb.close()
        return {}
    ws = wb["Trials"]
    headers = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
    header_map = {str(h): i for i, h in enumerate(headers) if h is not None}

    def cell(row, key, default=None):
        i = header_map.get(key)
        if i is None or i >= len(row):
            return default
        return row[i]

    out: dict[tuple, dict] = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        block = _int_or_none(cell(row, "Block") or cell(row, "block"))
        trial = _int_or_none(cell(row, "Trial") or cell(row, "trial") or cell(row, "Paint"))
        if block is None or trial is None:
            continue
        out[(block, trial)] = {
            "Resp": cell(row, "Resp"),
            "CRESP": cell(row, "CRESP"),
            "ACC": cell(row, "ACC"),
            "RT": cell(row, "RT"),
            "RSI": cell(row, "RSI"),
            "trialType": cell(row, "trialType"),
            "N": cell(row, "N") or cell(row, "nback"),
        }
    wb.close()
    return out


def _int_or_none(v):
    if v is None or v == "":
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _float_or_none(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def is_stim(m: dict) -> bool:
    if m.get("code") in STIM_CODES:
        return True
    return str(m.get("label") or "") in STIM_LABELS


def is_resp(m: dict) -> bool:
    if m.get("code") in RESP_CODES:
        return True
    return str(m.get("label") or "") in RESP_LABELS


def enrich_from_raw_json(markers: list[dict]) -> None:
    for m in markers:
        raw = m.get("raw") or ""
        if not raw or not raw.startswith("{"):
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if m.get("block") is None:
            m["block"] = _int_or_none(payload.get("block"))
        if m.get("trial") is None:
            m["trial"] = _int_or_none(payload.get("trial"))
        if m.get("nback") is None:
            m["nback"] = _int_or_none(payload.get("nback"))
        m["photodiodePattern"] = payload.get("photodiodePattern", "")
        if m.get("perf_ms") is None:
            m["perf_ms"] = _float_or_none(payload.get("perfMs"))


def pair_stim_resp(markers: list[dict]) -> list[dict]:
    """Pair each stim with the next response that shares block+trial when possible."""
    stims = [m for m in markers if is_stim(m)]
    resps = [m for m in markers if is_resp(m)]
    used_resp = set()
    pairs: list[dict] = []

    for s in stims:
        match = None
        for ri, r in enumerate(resps):
            if ri in used_resp:
                continue
            same_key = (
                s.get("block") is not None
                and r.get("block") is not None
                and s.get("trial") is not None
                and r.get("trial") is not None
                and s["block"] == r["block"]
                and s["trial"] == r["trial"]
            )
            # Observe/warmup stims often have no response — skip pairing by key only.
            if same_key:
                match = (ri, r)
                break
        if match is None and s.get("code") == 10:
            # Fallback: next unused response after this stim in stream order.
            for ri, r in enumerate(resps):
                if ri in used_resp:
                    continue
                if r["idx"] > s["idx"] and (s.get("block") is None or r.get("block") == s.get("block")):
                    match = (ri, r)
                    break

        resp = None
        if match:
            used_resp.add(match[0])
            resp = match[1]

        rt_ms = None
        if resp and s.get("perf_ms") is not None and resp.get("perf_ms") is not None:
            rt_ms = round(resp["perf_ms"] - s["perf_ms"], 3)
        elif resp and isinstance(s.get("time"), float) and isinstance(resp.get("time"), float):
            rt_ms = round((resp["time"] - s["time"]) * 1000.0, 3)

        pairs.append(
            {
                "block": s.get("block"),
                "trial": s.get("trial"),
                "nback": s.get("nback") or (resp.get("nback") if resp else None),
                "stim_code": s.get("code"),
                "stim_label": s.get("label"),
                "stim_time": s.get("time"),
                "stim_perf_ms": s.get("perf_ms"),
                "stim_photodiode": s.get("photodiodePattern") or "stim_long_120",
                "resp_code": resp.get("code") if resp else "",
                "resp_label": resp.get("label") if resp else "",
                "resp_time": resp.get("time") if resp else "",
                "resp_perf_ms": resp.get("perf_ms") if resp else "",
                "resp_photodiode": (resp.get("photodiodePattern") if resp else "")
                or ("resp_double_40_40_40" if resp else ""),
                "rt_ms_markers": rt_ms if rt_ms is not None else "",
                "pid": s.get("pid") or (resp.get("pid") if resp else ""),
                "session": s.get("session") or (resp.get("session") if resp else ""),
                "marker_source": s.get("source"),
            }
        )
    return pairs


def join_trials(pairs: list[dict], trials: dict[tuple, dict]) -> None:
    for p in pairs:
        key = (p.get("block"), p.get("trial"))
        t = trials.get(key)
        if not t:
            p["Resp"] = ""
            p["CRESP"] = ""
            p["ACC"] = ""
            p["RT_behavioural"] = ""
            p["RSI"] = ""
            p["trialType"] = ""
            continue
        p["Resp"] = t.get("Resp", "")
        p["CRESP"] = t.get("CRESP", "")
        p["ACC"] = t.get("ACC", "")
        p["RT_behavioural"] = t.get("RT", "")
        p["RSI"] = t.get("RSI", "")
        p["trialType"] = t.get("trialType", "")
        if p.get("nback") in (None, ""):
            p["nback"] = t.get("N", "")


def write_csv(path: Path, pairs: list[dict]) -> None:
    fields = [
        "block",
        "trial",
        "nback",
        "trialType",
        "stim_code",
        "stim_label",
        "stim_time",
        "stim_perf_ms",
        "stim_photodiode",
        "resp_code",
        "resp_label",
        "resp_time",
        "resp_perf_ms",
        "resp_photodiode",
        "rt_ms_markers",
        "RT_behavioural",
        "RSI",
        "Resp",
        "CRESP",
        "ACC",
        "pid",
        "session",
        "marker_source",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for p in pairs:
            w.writerow(p)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Compact stim+response markers into one EEG-ready event table"
    )
    ap.add_argument("--markers", type=Path, help="CSV from lsl_marker_bridge.py --log")
    ap.add_argument("--xdf", type=Path, help="LabRecorder .xdf with GLYPHMIND_Markers")
    ap.add_argument("--xlsx", type=Path, help="Game behavioural export (.xlsx)")
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("compact_events.csv"),
        help="Output CSV path (default: compact_events.csv)",
    )
    args = ap.parse_args()

    markers: list[dict] = []
    # Prefer a single clock source. XDF shares LabRecorder time with EEG.
    if args.xdf and args.markers:
        print(
            "[compact] both --xdf and --markers given; using --xdf for times "
            "(avoids double-counting). CSV kept only if XDF missing.",
            file=sys.stderr,
        )
        markers = load_markers_xdf(args.xdf)
    elif args.xdf:
        markers = load_markers_xdf(args.xdf)
    elif args.markers:
        markers = load_markers_csv(args.markers)

    if args.xlsx and not markers:
        markers.extend(load_events_xlsx(args.xlsx))

    if not markers and args.xlsx:
        markers = load_events_xlsx(args.xlsx)

    if not markers:
        print(
            "No markers loaded. Provide --markers, --xdf, and/or --xlsx with Events.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    enrich_from_raw_json(markers)
    # Stable stream order for fallback pairing
    markers.sort(key=lambda m: (m.get("idx", 0), str(m.get("time", ""))))

    pairs = pair_stim_resp(markers)
    trials: dict[tuple, dict] = {}
    if args.xlsx:
        trials = load_trials_xlsx(args.xlsx)
        join_trials(pairs, trials)

    write_csv(args.output, pairs)
    n_resp = sum(1 for p in pairs if p.get("resp_code") not in ("", None))
    print(
        f"[compact] wrote {len(pairs)} stim rows "
        f"({n_resp} with response) → {args.output}"
    )
    print(
        "[compact] Photodiode on EEG trigger: long pulse=stim, double pulse=response. "
        "Use stim_time / resp_time (XDF) or stim_perf_ms / resp_perf_ms for alignment."
    )


if __name__ == "__main__":
    main()
