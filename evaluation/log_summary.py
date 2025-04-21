"""
evaluation/log_summary.py
Summarise the evaluation_log.csv produced by evaluate_outputs.py
"""

import argparse
import datetime as dt
import os
import sys
import pandas as pd

# ---------- CONFIG --------------------------------------------------------- #
DEFAULT_LOG_PATH = os.path.join("data", "logs", "evaluation_log.csv")
# -------------------------------------------------------------------------- #


def load_log(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        sys.exit(f"❌  No log file found at {path}")
    df = pd.read_csv(path, parse_dates=["timestamp"])
    # in case older logs lack some cols, add them with NaN/0
    needed = ["accuracy", "precision", "recall", "f1_score"]
    for col in needed:
        if col not in df.columns:
            df[col] = float("nan")
    return df.sort_values("timestamp")


def pretty_percent(x):
    return f"{x*100:5.1f} %"


def print_recent(df: pd.DataFrame, n: int = 10):
    recent = df.tail(n)[
        ["timestamp", "run_name", "accuracy", "precision", "recall", "f1_score"]
    ].copy()

    recent["timestamp"] = recent["timestamp"].dt.strftime("%Y‑%m‑%d %H:%M")
    for col in ["accuracy", "precision", "recall", "f1_score"]:
        recent[col] = recent[col].apply(pretty_percent)

    print("\n🕑  Recent runs")
    print(recent.to_string(index=False))


def print_best(df: pd.DataFrame):
    best = df.loc[df["f1_score"].idxmax()]
    print(
        f"\n🏆  Best run so far:  {best['run_name']}  "
        f"({best['timestamp']:%Y‑%m‑%d %H:%M})  –  "
        f"F1 {pretty_percent(best['f1_score'])},  "
        f"P {pretty_percent(best['precision'])},  "
        f"R {pretty_percent(best['recall'])}"
    )


def print_rolling(df: pd.DataFrame, window: int = 5):
    """Print rolling‑window averages for numeric score columns only."""
    numeric_cols = ["accuracy", "precision", "recall", "f1_score"]
    rolling = (
        df.set_index("timestamp")[numeric_cols]      # keep only numbers
          .rolling(f"{window}D")
          .mean()
          .tail(1)
    )
    if rolling.empty:
        return
    r = rolling.iloc[0]
    print(
        f"\n📈  Rolling {window}‑day avg – "
        f"F1 {pretty_percent(r['f1_score'])},  "
        f"P {pretty_percent(r['precision'])},  "
        f"R {pretty_percent(r['recall'])}"
    )



def main():
    parser = argparse.ArgumentParser(description="Summarise evaluation runs")
    parser.add_argument("--log", default=DEFAULT_LOG_PATH, help="CSV log path")
    parser.add_argument("--last", type=int, default=10, help="Show last‑N runs")
    parser.add_argument("--window", type=int, default=5, help="Rolling days")
    parser.add_argument("--plot", action="store_true", help="Show F1 chart")
    args = parser.parse_args()

    df = load_log(args.log)
    print_recent(df, args.last)
    print_best(df)
    print_rolling(df, args.window)

    if args.plot:
        try:
            import matplotlib.pyplot as plt

            plt.figure(figsize=(8, 3))
            plt.plot(df["timestamp"], df["f1_score"], marker="o")
            plt.title("F1‑score over time")
            plt.ylabel("F1")
            plt.xlabel("Run timestamp")
            plt.tight_layout()
            plt.show()
        except ImportError:
            print("📉  (matplotlib not installed – skipping plot)")


if __name__ == "__main__":
    main()
