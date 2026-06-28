"""
Trains a CatBoost regressor to predict "pct_change_next" (the percent
change in an item's price between this timestamp and the next one) from
the features built by build_features.py.

WHY PERCENT CHANGE, NOT RAW PRICE:
    Currencies in this dataset span roughly 0.01 to 600+ chaos. A model
    trained to predict the raw next-period price would be dominated by
    high-value items and would mostly just learn "predict something
    close to lag_1" - low error on paper, but not a useful signal.
    Percent change is scale-independent: a 5% move means the same thing
    whether the item is worth 0.01 chaos or 600 chaos.

TRAIN/TEST SPLIT - READ THIS BEFORE CHANGING ANYTHING:
    With only a handful of distinct collection timestamps so far, a
    random row-wise split would put rows from the same item's same short
    price trajectory into both train and test, since consecutive rows
    for one item are highly correlated. That leaks information and makes
    results look better than they really are.

    Instead, we split BY TIME: every item's earliest timestamps go into
    training, and the single most recent timestamp (across all items)
    goes into the test set. This mirrors how the model would actually
    be used - predicting forward in time - and is the only split that
    gives an honest read on real performance with this little history.

HONEST CAVEAT: with this few timestamps, the test set is one single time
period repeated across items - not a robust estimate of real-world
accuracy, just a sanity check that the pipeline and model work end to
end. Treat all metrics here as provisional until more history exists.
"""

from pathlib import Path

import pandas as pd
from catboost import CatBoostRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

DATA_PATH = Path(__file__).resolve().parent / "data" / "training_data.csv"
MODEL_PATH = Path(__file__).resolve().parent / "data" / "catboost_model.cbm"

FEATURE_COLS = [
    "lag_1",
    "lag_2",
    "lag_3",
    "rolling_mean_3",
    "rolling_std_3",
    "pct_change_prev",
]
LABEL_COL = "pct_change_next"


def load_training_data() -> pd.DataFrame:
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"{DATA_PATH} not found. Run build_features.py first to generate it."
        )
    df = pd.read_csv(DATA_PATH, parse_dates=["collected_at"])
    return df


def time_based_split(df: pd.DataFrame):
    """
    Train on every timestamp except the most recent one; test on the
    most recent timestamp only. See the module docstring for why this
    split (not a random one) is the honest choice given how little
    history exists right now.
    """
    most_recent_ts = df["collected_at"].max()

    train_df = df[df["collected_at"] < most_recent_ts]
    test_df = df[df["collected_at"] == most_recent_ts]

    print(
        f"Train: {len(train_df)} rows (timestamps before {most_recent_ts}) | "
        f"Test: {len(test_df)} rows (timestamp == {most_recent_ts})"
    )

    if test_df.empty or train_df.empty:
        raise ValueError(
            "Time-based split produced an empty train or test set - "
            "not enough distinct timestamps yet to hold one out."
        )

    return train_df, test_df


def train_catboost(train_df: pd.DataFrame) -> CatBoostRegressor:
    X_train = train_df[FEATURE_COLS]
    y_train = train_df[LABEL_COL]

    model = CatBoostRegressor(
        iterations=200,
        depth=4,
        learning_rate=0.05,
        loss_function="RMSE",
        verbose=False,
        random_seed=42,
    )
    model.fit(X_train, y_train)
    return model


def evaluate(model: CatBoostRegressor, test_df: pd.DataFrame):
    X_test = test_df[FEATURE_COLS]
    y_test = test_df[LABEL_COL]

    y_pred = model.predict(X_test)

    mae = mean_absolute_error(y_test, y_pred)
    rmse = mean_squared_error(y_test, y_pred) ** 0.5
    r2 = r2_score(y_test, y_pred)

    # A naive baseline - "predict no change at all" (pct_change_next = 0)
    # - is the honest bar to beat. If our model doesn't beat this, it's
    # not adding real value over just assuming nothing changes.
    naive_pred = pd.Series(0.0, index=y_test.index)
    naive_mae = mean_absolute_error(y_test, naive_pred)

    print("\n--- Regression metrics (test set) ---")
    print(f"MAE:  {mae:.4f}  (naive 'no change' baseline MAE: {naive_mae:.4f})")
    print(f"RMSE: {rmse:.4f}")
    print(f"R^2:  {r2:.4f}")

    if mae < naive_mae:
        print("Model beats the naive baseline.")
    else:
        print(
            "Model does NOT beat the naive 'predict no change' baseline yet - "
            "expected with this little history; revisit once more data accumulates."
        )

    print("\n--- Sample predictions vs actual ---")
    sample = test_df[["item_name", "chaos_value"]].copy()
    sample["actual_pct_change"] = y_test.values
    sample["predicted_pct_change"] = y_pred
    print(sample.head(10).to_string(index=False))


def print_feature_importance(model: CatBoostRegressor):
    importances = model.get_feature_importance()
    print("\n--- Feature importance (CatBoost's built-in metric) ---")
    for name, importance in sorted(
        zip(FEATURE_COLS, importances), key=lambda x: -x[1]
    ):
        print(f"  {name}: {importance:.2f}")


def main():
    df = load_training_data()
    print(f"Loaded {len(df)} total training rows.")

    train_df, test_df = time_based_split(df)

    model = train_catboost(train_df)
    evaluate(model, test_df)
    print_feature_importance(model)

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(MODEL_PATH))
    print(f"\nModel saved to {MODEL_PATH}")


if __name__ == "__main__":
    main()