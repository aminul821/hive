"""
validate_against_real.py
------------------------
Checks the synthetic training data in train_model.py against a REAL hive
sensor dataset, and reports how the trained model behaves on real rows.

This does not retrain anything. Its job is to answer the question a judge
will ask: "your model is trained on data you made up — why should I
believe it?"

Usage:
    python validate_against_real.py path/to/real_data.csv

    # tell it which columns are which, if the names differ
    python validate_against_real.py data.csv \
        --temp temperature --humidity humidity --weight weight

Where to get a real CSV (see REFERENCES.md for details):
  * Kaggle HOBOS   https://www.kaggle.com/datasets/se18m502/bee-hive-metrics
  * Senger et al.  https://zenodo.org/records/10407693   (daily aggregates)
  * UFC Brazil     https://zenodo.org/records/20399470   (tropical climate)

What it reports:
  1. Do the synthetic ranges overlap the real ones? If the generator
     produces 18-42 C and real hives sit at 32-36 C, the model spent most
     of its training on conditions that do not occur.
  2. Where do real values fall inside the synthetic distribution? Real
     data clustered in one tail means the model is well-trained on rare
     cases and poorly trained on common ones.
  3. What does the trained model predict on real rows? Useful for the
     slide; it is NOT an accuracy figure, because these datasets carry no
     matching risk label.

Be careful what you claim from this. It shows your generator is
plausible. It does not show the model is accurate on real hives -- that
needs labelled Indian data, which does not publicly exist.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "models"

# Mirrors the generator in train_model.py. Keep in sync if you change it.
# The clip bounds the generator actually produces after calibration.
# Coverage is checked against these, not against the healthy band -- the
# generator deliberately includes failure states outside normal range.
SYNTHETIC = {
    "temperature": (18, 45),
    "humidity":    (20, 99),
    "weight":      (10, 60),
    "activity":    (10, 100),
}

# Column names these datasets actually use, so --temp etc. are usually
# unnecessary. Matched case-insensitively as substrings.
GUESSES = {
    "temperature": ["temperature", "temp_c", "temp", "t_i", "hive_temp",
                    "inner_temp", "temperatura"],
    "humidity":    ["humidity", "hum", "rh", "relative_humidity", "umidade"],
    "weight":      ["weight", "scale", "mass", "kg", "peso"],
    "activity":    ["activity", "bee_activity", "flow", "count"],
}


# Columns measuring the OUTSIDE environment, not the hive interior.
# Matching these by accident silently ruins the comparison: ambient
# humidity and brood-nest humidity are different physical quantities.
EXTERNAL_MARKERS = ("ext_", "external", "outside", "outdoor", "ambient",
                    "_out", "weather")


def find_column(df: pd.DataFrame, field: str, override: str | None):
    """
    Pick the column for a field, preferring an exact name match and
    avoiding external/ambient sensors.

    Substring matching alone is not enough. A file with both `humidity`
    and `ext_humidity` will hand you whichever happens to come first in
    column order -- which is how a real run picked outdoor humidity and
    reported a meaningless 86% overlap.
    """
    if override:
        if override not in df.columns:
            sys.exit(f"Column '{override}' not in the CSV. "
                     f"Available: {list(df.columns)[:20]}")
        return override

    lowered = {c.lower(): c for c in df.columns}
    internal = {low: orig for low, orig in lowered.items()
                if not any(m in low for m in EXTERNAL_MARKERS)}

    # 1. exact match on an internal column
    for guess in GUESSES[field]:
        if guess in internal:
            return internal[guess]
    # 2. substring match on an internal column
    for guess in GUESSES[field]:
        for low, orig in internal.items():
            if guess in low:
                return orig
    # 3. only then fall back to external columns, and say so
    for guess in GUESSES[field]:
        for low, orig in lowered.items():
            if guess in low:
                print(f"  NOTE: only an external sensor was found for "
                      f"{field} ('{orig}'). Interior readings would be "
                      f"the right comparison.")
                return orig
    return None


def describe(name: str, values: np.ndarray) -> dict:
    values = values[~np.isnan(values)]
    if len(values) == 0:
        return {}
    return {
        "n": len(values),
        "min": float(np.min(values)),
        "p05": float(np.percentile(values, 5)),
        "median": float(np.median(values)),
        "p95": float(np.percentile(values, 95)),
        "max": float(np.max(values)),
        "mean": float(np.mean(values)),
        "std": float(np.std(values)),
    }


def overlap_pct(real: np.ndarray, lo: float, hi: float) -> float:
    """What share of real readings fall inside the synthetic range?"""
    real = real[~np.isnan(real)]
    if len(real) == 0:
        return 0.0
    return float(np.mean((real >= lo) & (real <= hi)) * 100)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", help="path to the real dataset")
    ap.add_argument("--temp", help="temperature column name")
    ap.add_argument("--humidity", help="humidity column name")
    ap.add_argument("--weight", help="weight column name")
    ap.add_argument("--activity", help="activity column name (usually absent)")
    ap.add_argument("--rows", type=int, default=200000,
                    help="cap rows read, for large files")
    args = ap.parse_args()

    path = Path(args.csv)
    if not path.exists():
        sys.exit(f"File not found: {path}")

    print(f"Reading {path.name} ...")
    try:
        df = pd.read_csv(path, nrows=args.rows)
    except Exception as exc:                             # noqa: BLE001
        sys.exit(f"Could not read the CSV: {exc}")

    print(f"  {len(df):,} rows, {len(df.columns)} columns\n")

    cols = {}
    for field, override in [("temperature", args.temp),
                            ("humidity", args.humidity),
                            ("weight", args.weight),
                            ("activity", args.activity)]:
        cols[field] = find_column(df, field, override)

    print("Column mapping")
    for field, col in cols.items():
        print(f"  {field:12} -> {col if col else '(not found)'}")
    if not any(cols[f] for f in ("temperature", "humidity", "weight")):
        print(f"\nNo usable columns found. Columns present: {list(df.columns)}")
        print("Pass them explicitly, e.g. --temp temp_c --weight scale_kg")
        return 1
    print()

    # ---------------------------------------------------------------
    # 1. Distribution comparison
    # ---------------------------------------------------------------
    print("=" * 66)
    print("  SYNTHETIC RANGE vs REAL DATA")
    print("=" * 66)

    verdicts = []
    for field in ("temperature", "humidity", "weight"):
        col = cols[field]
        if not col:
            continue

        real = pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float)
        stats = describe(field, real)
        if not stats:
            print(f"\n{field}: no numeric values in '{col}'")
            continue

        lo, hi = SYNTHETIC[field]
        inside = overlap_pct(real, lo, hi)
        verdicts.append((field, inside))

        print(f"\n{field.upper()}   (real column: {col})")
        print(f"  synthetic range   {lo} to {hi}")
        print(f"  real range        {stats['min']:.1f} to {stats['max']:.1f}"
              f"   (5th-95th pct: {stats['p05']:.1f} to {stats['p95']:.1f})")
        print(f"  real median       {stats['median']:.1f}"
              f"     mean {stats['mean']:.1f} +/- {stats['std']:.1f}")
        print(f"  real values inside the synthetic range: {inside:.1f}%")

        if inside >= 90:
            print("  -> Good. The generator covers what real hives do.")
        elif inside >= 60:
            print("  -> Partial. Widen or shift the synthetic range in "
                  "train_model.py.")
        else:
            print("  -> Poor. Most real readings fall outside what the "
                  "model was trained on.")

        # Is the real data concentrated in a corner of the synthetic span,
        # or outside it altogether?
        span = hi - lo
        median = stats["median"]
        if span > 0:
            if median < lo:
                print(f"     Real median ({median:.1f}) is BELOW the "
                      f"synthetic minimum ({lo}). The model never saw "
                      f"typical conditions during training.")
            elif median > hi:
                print(f"     Real median ({median:.1f}) is ABOVE the "
                      f"synthetic maximum ({hi}). The model never saw "
                      f"typical conditions during training.")
            else:
                pos = (median - lo) / span
                if pos < 0.25:
                    print(f"     Real median sits in the lowest quarter of "
                          f"the synthetic span -- most training samples are "
                          f"higher than reality.")
                elif pos > 0.75:
                    print(f"     Real median sits in the highest quarter of "
                          f"the synthetic span -- most training samples are "
                          f"lower than reality.")

    # ---------------------------------------------------------------
    # 2. Model behaviour on real rows
    # ---------------------------------------------------------------
    print("\n" + "=" * 66)
    print("  TRAINED MODEL ON REAL ROWS")
    print("=" * 66)

    risk_path = MODEL_DIR / "hive_risk_model.pkl"
    if not risk_path.exists():
        print(f"\n  {risk_path} not found. Run: python train_model.py")
        return 0

    try:
        import joblib
        risk_model = joblib.load(risk_path)
    except Exception as exc:                             # noqa: BLE001
        print(f"\n  Could not load the model: {exc}")
        return 0

    needed = ("temperature", "humidity", "weight")
    if not all(cols[f] for f in needed):
        missing = [f for f in needed if not cols[f]]
        print(f"\n  Skipped: this CSV has no {', '.join(missing)} column.")
        return 0

    frame = pd.DataFrame({
        f: pd.to_numeric(df[cols[f]], errors="coerce") for f in needed
    })
    # No real dataset here carries a bee-activity field. Holding it at the
    # synthetic midpoint keeps the other three comparable, and is stated
    # openly rather than quietly imputed.
    activity_col = cols["activity"]
    if activity_col:
        frame["activity"] = pd.to_numeric(df[activity_col], errors="coerce")
        activity_note = f"from column '{activity_col}'"
    else:
        frame["activity"] = float(np.mean(SYNTHETIC["activity"]))
        activity_note = ("held at the synthetic midpoint -- this dataset "
                         "has no activity measurement")

    frame = frame.dropna()
    if frame.empty:
        print("\n  No complete rows after dropping missing values.")
        return 0

    if len(frame) > 20000:
        frame = frame.sample(20000, random_state=42)

    print(f"\n  rows scored : {len(frame):,}")
    print(f"  activity    : {activity_note}")

    try:
        preds = risk_model.predict(frame[["temperature", "humidity",
                                          "weight", "activity"]])
    except Exception as exc:                             # noqa: BLE001
        print(f"  Prediction failed: {exc}")
        return 0

    labels, counts = np.unique(preds, return_counts=True)
    print("\n  predicted risk distribution on real hives:")
    for label, count in sorted(zip(labels, counts),
                               key=lambda x: -x[1]):
        share = count / len(preds) * 100
        bar = "#" * int(share / 2)
        print(f"    {str(label):8} {share:5.1f}%  {bar}")

    print("\n  This is a sanity check, not an accuracy score. These")
    print("  datasets carry no risk label matching our definition, so")
    print("  there is nothing to score against. What it tells you: if")
    print("  90% of real hives come back HIGH risk, the thresholds in")
    print("  train_model.py are miscalibrated for real conditions.")

    # ---------------------------------------------------------------
    print("\n" + "=" * 66)
    print("  WHAT YOU CAN HONESTLY CLAIM")
    print("=" * 66)
    if verdicts:
        worst = min(v for _, v in verdicts)
        fields = ", ".join(f for f, _ in verdicts)
        if worst >= 90:
            print(f"\n  \"Our synthetic generator's ranges for {fields} cover")
            print(f"   {worst:.0f}%+ of readings in a real multi-colony dataset.\"")
        else:
            print(f"\n  Not yet a clean claim: the weakest field covers only")
            print(f"  {worst:.0f}% of real readings. Adjust the ranges in")
            print(f"  train_model.py, retrain, and run this again.")
    print("\n  Do NOT claim accuracy on real hives. You have no labels.")
    print("  Cite the dataset in your README -- see REFERENCES.md.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
