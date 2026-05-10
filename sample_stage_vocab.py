#!/usr/bin/env python3
"""sample_stage_vocab.py — Sample vocabulary packets from stage CSV files.

Given a folder of stage CSVs (stage_00 … stage_30), randomly sample
vocabulary packets for a selected stage across four passage-length modes.
Each packet contains three buckets: support, focus, and stretch.
"""

import argparse
import json
import math
import random
import sys
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Stage metadata
# ---------------------------------------------------------------------------

STAGES = [
    {"id": "stage_00", "start": 1,     "end": 250,   "label": "Pre-A1"},
    {"id": "stage_01", "start": 251,   "end": 400,   "label": "A1-"},
    {"id": "stage_02", "start": 401,   "end": 575,   "label": "A1-"},
    {"id": "stage_03", "start": 576,   "end": 800,   "label": "A1"},
    {"id": "stage_04", "start": 801,   "end": 1075,  "label": "A1+"},
    {"id": "stage_05", "start": 1076,  "end": 1400,  "label": "A1+"},
    {"id": "stage_06", "start": 1401,  "end": 1800,  "label": "A2-"},
    {"id": "stage_07", "start": 1801,  "end": 2250,  "label": "A2-"},
    {"id": "stage_08", "start": 2251,  "end": 2750,  "label": "A2"},
    {"id": "stage_09", "start": 2751,  "end": 3300,  "label": "A2+"},
    {"id": "stage_10", "start": 3301,  "end": 3900,  "label": "A2+"},
    {"id": "stage_11", "start": 3901,  "end": 4600,  "label": "B1-"},
    {"id": "stage_12", "start": 4601,  "end": 5400,  "label": "B1-"},
    {"id": "stage_13", "start": 5401,  "end": 6300,  "label": "B1"},
    {"id": "stage_14", "start": 6301,  "end": 7300,  "label": "B1+"},
    {"id": "stage_15", "start": 7301,  "end": 8400,  "label": "B1+"},
    {"id": "stage_16", "start": 8401,  "end": 9600,  "label": "B2-"},
    {"id": "stage_17", "start": 9601,  "end": 10900, "label": "B2-"},
    {"id": "stage_18", "start": 10901, "end": 12300, "label": "B2"},
    {"id": "stage_19", "start": 12301, "end": 13800, "label": "B2+"},
    {"id": "stage_20", "start": 13801, "end": 15400, "label": "B2+"},
    {"id": "stage_21", "start": 15401, "end": 17100, "label": "C1-"},
    {"id": "stage_22", "start": 17101, "end": 18900, "label": "C1-"},
    {"id": "stage_23", "start": 18901, "end": 20800, "label": "C1"},
    {"id": "stage_24", "start": 20801, "end": 22800, "label": "C1+"},
    {"id": "stage_25", "start": 22801, "end": 24900, "label": "C1+"},
    {"id": "stage_26", "start": 24901, "end": 27000, "label": "C2-"},
    {"id": "stage_27", "start": 27001, "end": 29100, "label": "C2-"},
    {"id": "stage_28", "start": 29101, "end": 31100, "label": "C2"},
    {"id": "stage_29", "start": 31101, "end": 33100, "label": "C2+"},
    {"id": "stage_30", "start": 33101, "end": 35000, "label": "C2+"},
]

STAGE_IDS = [s["id"] for s in STAGES]
STAGE_MAP = {s["id"]: s for s in STAGES}

# ---------------------------------------------------------------------------
# Stage groups
# ---------------------------------------------------------------------------

GROUP_RANGES = {
    "group_early":     (0, 5),
    "group_lower_mid": (6, 10),
    "group_mid":       (11, 20),
    "group_advanced":  (21, 30),
}

MODES = ["short", "medium", "long", "very_long"]

WORD_COL_CANDIDATES = ["word", "lemma", "form", "surface_form", "raw_form"]

# ---------------------------------------------------------------------------
# Passage length targets  (min, max) in words
# ---------------------------------------------------------------------------

PASSAGE_TARGETS = {
    "group_early": {
        "short": (50, 70),   "medium": (80, 110),
        "long": (120, 160),  "very_long": (170, 220),
    },
    "group_lower_mid": {
        "short": (60, 90),   "medium": (100, 140),
        "long": (150, 210),  "very_long": (220, 300),
    },
    "group_mid": {
        "short": (80, 120),  "medium": (130, 180),
        "long": (190, 260),  "very_long": (270, 360),
    },
    "group_advanced": {
        "short": (100, 150), "medium": (160, 220),
        "long": (230, 320),  "very_long": (330, 450),
    },
}

# ---------------------------------------------------------------------------
# Sampling counts per group and mode
# ---------------------------------------------------------------------------

SAMPLING_COUNTS = {
    "group_early": {
        "short":     {"support": 45,  "focus": 4,  "stretch": 0},
        "medium":    {"support": 70,  "focus": 5,  "stretch": 1},
        "long":      {"support": 100, "focus": 6,  "stretch": 1},
        "very_long": {"support": 140, "focus": 8,  "stretch": 2},
    },
    "group_lower_mid": {
        "short":     {"support": 55,  "focus": 4,  "stretch": 1},
        "medium":    {"support": 85,  "focus": 5,  "stretch": 2},
        "long":      {"support": 120, "focus": 6,  "stretch": 2},
        "very_long": {"support": 170, "focus": 8,  "stretch": 3},
    },
    "group_mid": {
        "short":     {"support": 70,  "focus": 5,  "stretch": 1},
        "medium":    {"support": 105, "focus": 6,  "stretch": 2},
        "long":      {"support": 150, "focus": 8,  "stretch": 3},
        "very_long": {"support": 210, "focus": 10, "stretch": 4},
    },
    "group_advanced": {
        "short":     {"support": 85,  "focus": 5,  "stretch": 1},
        "medium":    {"support": 125, "focus": 7,  "stretch": 2},
        "long":      {"support": 180, "focus": 9,  "stretch": 3},
        "very_long": {"support": 250, "focus": 12, "stretch": 5},
    },
}


# ---------------------------------------------------------------------------
# Helpers — stage group lookup
# ---------------------------------------------------------------------------

def get_stage_group(stage_id):
    """Return the group name for a given stage id."""
    idx = STAGE_IDS.index(stage_id)
    for group, (lo, hi) in GROUP_RANGES.items():
        if lo <= idx <= hi:
            return group
    raise ValueError(f"Stage {stage_id} does not belong to any group")


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def find_stage_file(input_dir, stage_id):
    """Locate the CSV for *stage_id* under *input_dir*.

    Tries ``stage_XX.csv`` first, then ``stage_XX_*.csv`` (glob).
    Returns the Path on success, None if nothing matches.
    """
    exact = input_dir / f"{stage_id}.csv"
    if exact.exists():
        return exact
    matches = sorted(input_dir.glob(f"{stage_id}_*.csv"))
    return matches[0] if matches else None


# ---------------------------------------------------------------------------
# CSV loading
# ---------------------------------------------------------------------------

def detect_word_column(columns):
    """Return the first column name that matches a known word-like name."""
    for candidate in WORD_COL_CANDIDATES:
        if candidate in columns:
            return candidate
    return None


def load_stage_csv(path, encoding, delimiter):
    """Read a stage CSV and return ``(DataFrame, word_column_name)``.

    Validates that *rank* and at least one word-like column exist.
    """
    df = pd.read_csv(path, encoding=encoding, delimiter=delimiter)
    df.columns = [c.strip() for c in df.columns]

    word_col = detect_word_column(df.columns.tolist())
    if word_col is None:
        raise ValueError(
            f"{path.name}: no word column found — expected one of "
            f"{WORD_COL_CANDIDATES}, got {list(df.columns)}"
        )

    if "rank" not in df.columns:
        raise ValueError(f"{path.name}: missing required 'rank' column")

    df["rank"] = pd.to_numeric(df["rank"], errors="coerce")
    df = df.dropna(subset=["rank"])
    df["rank"] = df["rank"].astype(int)
    return df, word_col


# ---------------------------------------------------------------------------
# Pool construction
# ---------------------------------------------------------------------------

def build_pools(stage_id, input_dir, encoding, delimiter):
    """Construct the three sampling pools for *stage_id*.

    Returns
    -------
    cumulative_pool : DataFrame
        All rows from stage_00 through the selected stage (inclusive).
    focus_pool : DataFrame
        Rows belonging only to the selected stage.
    stretch_pool : DataFrame
        Rows from the next stage (empty DataFrame if none exists).
    word_col : str
        Detected word-column name.
    files_used : list[str]
        Basenames of every CSV that was loaded.
    warnings : list[str]
        Non-fatal issues encountered during loading.
    """
    stage_idx = STAGE_IDS.index(stage_id)
    warnings = []
    files_used = []
    word_col = None

    # --- cumulative pool: stage_00 … selected stage (inclusive) ------------
    frames = []
    for i in range(stage_idx + 1):
        sid = STAGE_IDS[i]
        path = find_stage_file(input_dir, sid)
        if path is None:
            warnings.append(f"Missing file for {sid}")
            continue
        df, wc = load_stage_csv(path, encoding, delimiter)
        df["_source_stage"] = sid
        frames.append(df)
        files_used.append(path.name)
        if word_col is None:
            word_col = wc

    if not frames:
        raise FileNotFoundError(
            "No stage files could be loaded for the cumulative pool"
        )

    cumulative_pool = pd.concat(frames, ignore_index=True)

    # --- focus pool: selected stage only -----------------------------------
    focus_pool = cumulative_pool[
        cumulative_pool["_source_stage"] == stage_id
    ].copy()

    # --- stretch pool: next stage ------------------------------------------
    stretch_pool = pd.DataFrame()
    if stage_idx + 1 < len(STAGE_IDS):
        next_id = STAGE_IDS[stage_idx + 1]
        next_path = find_stage_file(input_dir, next_id)
        if next_path is not None:
            stretch_pool, _ = load_stage_csv(next_path, encoding, delimiter)
            stretch_pool["_source_stage"] = next_id
            files_used.append(next_path.name)
        else:
            warnings.append(f"Missing file for stretch stage {next_id}")

    return cumulative_pool, focus_pool, stretch_pool, word_col, files_used, warnings


# ---------------------------------------------------------------------------
# Weighted sampling
# ---------------------------------------------------------------------------

def weighted_sample(df, n, weight_fn, exclude_ranks=None):
    """Sample up to *n* rows from *df* without replacement.

    *weight_fn* maps a rank (int) to a non-negative float weight.
    Rows whose rank appears in *exclude_ranks* are dropped first.
    """
    if df.empty or n <= 0 or "rank" not in df.columns:
        return df.iloc[:0]
    pool = df.copy()
    if exclude_ranks:
        pool = pool[~pool["rank"].isin(exclude_ranks)]
    if pool.empty:
        return pool.iloc[:0]

    n = min(n, len(pool))
    indices = pool.index.tolist()
    weights = [weight_fn(pool.loc[i, "rank"]) for i in indices]

    chosen = []
    for _ in range(n):
        total = sum(weights)
        if total <= 0:
            pick_pos = random.randrange(len(indices))
        else:
            pick_pos = random.choices(range(len(indices)), weights=weights, k=1)[0]
        chosen.append(indices[pick_pos])
        del indices[pick_pos]
        del weights[pick_pos]

    return pool.loc[chosen]


def support_weight(rank):
    """Bias toward more frequent (lower-rank) forms: ``1 / sqrt(rank)``."""
    return 1.0 / math.sqrt(max(rank, 1))


def make_focus_weight(stage_start, stage_end):
    """Return a weight function that mildly favours the lower-rank half."""
    midpoint = (stage_start + stage_end) / 2.0

    def _weight(rank):
        return 2.0 if rank <= midpoint else 1.0

    return _weight


def stretch_weight(rank):
    """Mild bias toward lower rank within the stretch stage."""
    return 1.0 / math.sqrt(max(rank, 1))


# ---------------------------------------------------------------------------
# Core sampling
# ---------------------------------------------------------------------------

def sample_packet(cumulative_pool, focus_pool, stretch_pool, counts, stage_meta):
    """Sample one vocabulary packet.

    Returns ``(combined_df, actual_counts_dict)``.
    """
    used_ranks = set()
    actual = {"support": 0, "focus": 0, "stretch": 0}
    buckets = []

    def _collect(df, bucket_name):
        if df.empty:
            return
        df = df.copy()
        df["source_bucket"] = bucket_name
        used_ranks.update(df["rank"].tolist())
        actual[bucket_name] = len(df)
        buckets.append(df)

    focus_wt = make_focus_weight(stage_meta["start"], stage_meta["end"])

    # 1) Focus — sample from the selected stage
    _collect(
        weighted_sample(focus_pool, counts["focus"], focus_wt, exclude_ranks=used_ranks),
        "focus",
    )

    # 2) Stretch — sample from the next stage
    _collect(
        weighted_sample(stretch_pool, counts["stretch"], stretch_weight, exclude_ranks=used_ranks),
        "stretch",
    )

    # 3) Support — sample from cumulative pool, excluding already-picked rows
    _collect(
        weighted_sample(cumulative_pool, counts["support"], support_weight, exclude_ranks=used_ranks),
        "support",
    )

    combined = pd.concat(buckets, ignore_index=True) if buckets else pd.DataFrame()
    return combined, actual


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def format_output(df, word_col, stage_id, mode, target_min, target_max):
    """Reshape the sampled DataFrame into the required output schema."""
    out = pd.DataFrame()
    out["word"] = df[word_col].values
    out["rank"] = df["rank"].values
    out["source_bucket"] = df["source_bucket"].values
    out["selected_stage"] = stage_id
    out["source_stage"] = df["_source_stage"].values
    out["display_label"] = out["source_stage"].map(lambda s: STAGE_MAP[s]["label"])
    out["mode"] = mode
    out["target_min_words"] = target_min
    out["target_max_words"] = target_max

    # Preserve any extra columns from the original CSVs
    reserved = {
        "rank", word_col, "source_bucket", "_source_stage",
        "selected_stage", "source_stage", "display_label",
        "mode", "target_min_words", "target_max_words", "word",
    }
    for col in df.columns:
        if col not in reserved:
            out[col] = df[col].values

    return out.sort_values("rank").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Summary JSON
# ---------------------------------------------------------------------------

def build_summary(stage_id, group, seed, files_used, mode_results, warnings):
    """Assemble the per-stage summary dictionary."""
    meta = STAGE_MAP[stage_id]
    summary = {
        "selected_stage": stage_id,
        "display_label": meta["label"],
        "rank_range": [meta["start"], meta["end"]],
        "stage_group": group,
        "seed": seed,
        "input_files": sorted(set(files_used)),
        "modes": {},
        "warnings": warnings,
    }
    for mode in MODES:
        info = mode_results[mode]
        summary["modes"][mode] = {
            "target_word_range": list(info["target"]),
            "requested_counts": info["requested"],
            "actual_counts": info["actual"],
        }
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Sample vocabulary packets for a selected CEFR stage.",
    )
    parser.add_argument(
        "--input-dir", required=True, type=Path,
        help="Folder containing stage CSV files (stage_00 … stage_30)",
    )
    parser.add_argument(
        "--stage", required=True,
        help="Selected stage, e.g. stage_08",
    )
    parser.add_argument(
        "--output-dir", required=True, type=Path,
        help="Destination folder for output files",
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Random seed for reproducibility",
    )
    parser.add_argument(
        "--encoding", default="utf-8",
        help="CSV file encoding (default: utf-8)",
    )
    parser.add_argument(
        "--delimiter", default=",",
        help="CSV delimiter (default: comma)",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv=None):
    args = parse_args(argv)

    # --- validate stage ----------------------------------------------------
    if args.stage not in STAGE_IDS:
        print(f"Error: '{args.stage}' is not a valid stage.", file=sys.stderr)
        print(f"Valid stages: {', '.join(STAGE_IDS)}", file=sys.stderr)
        sys.exit(1)

    # --- validate input directory ------------------------------------------
    if not args.input_dir.is_dir():
        print(
            f"Error: input directory '{args.input_dir}' does not exist.",
            file=sys.stderr,
        )
        sys.exit(1)

    # --- seed --------------------------------------------------------------
    seed = args.seed if args.seed is not None else random.randrange(2**32)
    random.seed(seed)

    # --- create output directory -------------------------------------------
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # --- build pools -------------------------------------------------------
    cumulative_pool, focus_pool, stretch_pool, word_col, files_used, warnings = (
        build_pools(args.stage, args.input_dir, args.encoding, args.delimiter)
    )

    group = get_stage_group(args.stage)
    stage_meta = STAGE_MAP[args.stage]

    print(f"Stage:        {args.stage} ({stage_meta['label']})")
    print(f"Group:        {group}")
    print(f"Seed:         {seed}")
    print(f"Word column:  {word_col}")
    print(f"Support pool: {len(cumulative_pool)} rows")
    print(f"Focus pool:   {len(focus_pool)} rows")
    print(f"Stretch pool: {len(stretch_pool)} rows")
    print()

    # --- sample each mode --------------------------------------------------
    mode_results = {}

    for mode in MODES:
        counts = SAMPLING_COUNTS[group][mode]
        target = PASSAGE_TARGETS[group][mode]

        sampled, actual = sample_packet(
            cumulative_pool, focus_pool, stretch_pool, counts, stage_meta,
        )

        # warn on pool exhaustion
        for bucket in ("focus", "stretch", "support"):
            if actual[bucket] < counts[bucket]:
                msg = (
                    f"{mode}: requested {counts[bucket]} {bucket} "
                    f"but only {actual[bucket]} available"
                )
                warnings.append(msg)
                print(f"  WARNING: {msg}")

        out_df = format_output(
            sampled, word_col, args.stage, mode, target[0], target[1],
        )

        out_path = args.output_dir / f"{args.stage}_{mode}.csv"
        out_df.to_csv(out_path, index=False, encoding=args.encoding)

        total = len(out_df)
        print(
            f"  {mode:10s}  ->  {out_path.name}  "
            f"({actual['support']}s + {actual['focus']}f + {actual['stretch']}st "
            f"= {total} rows,  target {target[0]}-{target[1]} words)"
        )

        mode_results[mode] = {
            "target": target,
            "requested": counts,
            "actual": actual,
        }

    # --- write summary JSON ------------------------------------------------
    summary = build_summary(
        args.stage, group, seed, files_used, mode_results, warnings,
    )
    summary_path = args.output_dir / f"{args.stage}_summary.json"
    with open(summary_path, "w", encoding=args.encoding) as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"\n  Summary -> {summary_path.name}")
    if warnings:
        print(f"\n  {len(warnings)} warning(s) — see summary JSON for details.")


if __name__ == "__main__":
    main()
