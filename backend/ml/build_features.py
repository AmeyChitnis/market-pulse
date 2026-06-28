"""
Feature extraction: turns raw price_snapshots rows into a flat table of
(features, label) rows suitable for training a regressor.

This is intentionally a standalone script, not part of the FastAPI app -
it's run manually (or later, on a schedule) to regenerate the training
dataset as more history accumulates. It reads directly from the same
SQLite file the app writes to, but never writes back to it.

PREDICTION TARGET (v2 - regression):
    For each (item, timestamp) pair where enough prior history exists,
    predict the PERCENT CHANGE in price between this timestamp and the
    next one (a continuous value, e.g. +0.03 = +3%, -0.05 = -5%).

    Percent change, not raw next-period price, is the target on purpose:
    currencies in this dataset range from ~0.01 chaos to ~600+ chaos.
    A model trained on raw price would be dominated by high-value items
    and would mostly just learn "predict something close to lag_1" -
    technically low-error, but not actually useful. Percent change is
    scale-independent: a 5% move means the same thing whether the item
    is worth 0.01 chaos or 600 chaos.

    This target was chosen specifically because it doesn't require deep
    history per row - every (item, timestamp) pair with at least
    `MIN_HISTORY_POINTS` prior observations is usable, so the dataset
    grows roughly linearly with collection runs rather than needing
    months of backfill before producing a single usable row.

HONEST LIMITATION: with only a handful of collection runs banked so far,
the *output* of this script is correct but the *training set* is small.
Re-run this script periodically as more snapshots accumulate - the
training table simply grows on its own with no code changes needed.
"""

import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent / "market_pulse.db"
OUTPUT_PATH = Path(__file__).resolve().parent / "data" / "training_data.csv"

# How many prior observations an item needs before we compute features
# for it. Rolling/lag features need at least this many points to not be
# mostly NaN.
MIN_HISTORY_POINTS = 4


def load_snapshots(db_path: Path) -> pd.DataFrame:
    """Load all snapshots, joined with item names, as a flat DataFrame."""
    con = sqlite3.connect(db_path)
    query = """
        SELECT
            items.id AS item_id,
            items.name AS item_name,
            price_snapshots.chaos_value,
            price_snapshots.listing_count,
            price_snapshots.collected_at
        FROM price_snapshots
        JOIN items ON items.id = price_snapshots.item_id
        ORDER BY items.id, price_snapshots.collected_at
    """
    df = pd.read_sql_query(query, con)
    con.close()

    df["collected_at"] = pd.to_datetime(df["collected_at"])
    return df


def build_features_for_item(item_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute rolling/lag features and the next-period percent-change
    label for a single item's price history, already sorted by time.

    Returns one row per timestamp where enough history exists to compute
    features AND a next timestamp exists to compute the label from.
    """
    item_df = item_df.sort_values("collected_at").reset_index(drop=True)

    # Lag features: price N periods ago.
    item_df["lag_1"] = item_df["chaos_value"].shift(1)
    item_df["lag_2"] = item_df["chaos_value"].shift(2)
    item_df["lag_3"] = item_df["chaos_value"].shift(3)

    # Rolling features over the trailing window (excludes the current
    # row to avoid leaking the present into its own features).
    rolling = item_df["chaos_value"].shift(1).rolling(window=3, min_periods=3)
    item_df["rolling_mean_3"] = rolling.mean()
    item_df["rolling_std_3"] = rolling.std()

    # Percent change from the previous period - a feature in its own
    # right (recent momentum), distinct from the future label below.
    item_df["pct_change_prev"] = item_df["chaos_value"].pct_change()

    # LABEL: percent change to the *next* period - a continuous value,
    # not thresholded. This looks forward in time on purpose; it's what
    # we're trying to predict, not a feature. The most recent timestamp
    # has no "next" period, so this is genuinely NaN there (a plain
    # arithmetic NaN, not a boolean comparison result - dropna handles
    # it correctly without the threshold-comparison pitfall from v1).
    next_value = item_df["chaos_value"].shift(-1)
    item_df["pct_change_next"] = (next_value - item_df["chaos_value"]) / item_df["chaos_value"]

    # Drop rows missing required lookback (start of history) or lookahead
    # (most recent timestamp, which has no "next" period yet).
    feature_cols = ["lag_1", "lag_2", "lag_3", "rolling_mean_3", "rolling_std_3"]
    item_df = item_df.dropna(subset=feature_cols + ["pct_change_next"])

    return item_df


def build_training_table(df: pd.DataFrame) -> pd.DataFrame:
    """Apply build_features_for_item to every item and concatenate results."""
    results = []
    for item_id, item_df in df.groupby("item_id"):
        if len(item_df) < MIN_HISTORY_POINTS:
            continue  # not enough history for this item yet
        result = build_features_for_item(item_df)
        if not result.empty:
            results.append(result)

    if not results:
        return pd.DataFrame()

    return pd.concat(results, ignore_index=True)


def main():
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DB_PATH}. Run the FastAPI app at least "
            "once so the collector has written some snapshots."
        )

    raw = load_snapshots(DB_PATH)
    print(f"Loaded {len(raw)} raw snapshot rows across {raw['item_id'].nunique()} items.")

    training_table = build_training_table(raw)

    if training_table.empty:
        print(
            "No training rows produced yet - not enough history per item. "
            f"Need at least {MIN_HISTORY_POINTS} snapshots per item; keep "
            "the collector running and re-run this script later."
        )
        return

    output_cols = [
        "item_id",
        "item_name",
        "collected_at",
        "chaos_value",
        "lag_1",
        "lag_2",
        "lag_3",
        "rolling_mean_3",
        "rolling_std_3",
        "pct_change_prev",
        "pct_change_next",
    ]
    training_table = training_table[output_cols]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    training_table.to_csv(OUTPUT_PATH, index=False)

    print(f"Wrote {len(training_table)} training rows to {OUTPUT_PATH}")
    print(f"pct_change_next summary stats:\n{training_table['pct_change_next'].describe()}")


if __name__ == "__main__":
    main()