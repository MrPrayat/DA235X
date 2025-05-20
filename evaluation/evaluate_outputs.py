import os
import json
from collections import defaultdict
import pandas as pd
import datetime

EVAL_FOLDER = "data/evaluation"
UNAMBIGUOUS_FIELDS = {"CadastralDesignation", "InspectionDate"}

def compute_summary_stats(results_dict):
    """
    Given a results dict with field-level TP/FP/FN,
    compute global accuracy, precision, recall, and F1 score.
    """
    total_tp = sum(c['tp'] for c in results_dict.values())
    total_fp = sum(c['fp'] for c in results_dict.values())
    total_fn = sum(c['fn'] for c in results_dict.values())

    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    accuracy = total_tp / (total_tp + total_fp + total_fn) if (total_tp + total_fp + total_fn) > 0 else 0

    return {
        "tp": total_tp,
        "fp": total_fp,
        "fn": total_fn,
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4)
    }


def log_run_to_csv(results, run_name, notes="", log_file="data/logs/evaluation_log.csv"):
    """
    Logs the evaluation results to a CSV file.
    """
    print("⚙️  Writing log to:", os.path.abspath(log_file))
    summary = compute_summary_stats(results)

    new_row = {
        "timestamp": datetime.datetime.now().isoformat(),
        "run_name": run_name,
        "notes": notes,
        "true_positives": summary["tp"],
        "false_positives": summary["fp"],
        "false_negatives": summary["fn"],
        "accuracy": summary["accuracy"],
        "precision": summary["precision"],
        "recall": summary["recall"],
        "f1_score": summary["f1_score"]
    }

    # Append to CSV
    try:
        df = pd.read_csv(log_file)
    except FileNotFoundError:
        df = pd.DataFrame()

    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(log_file, index=False)
    print(f"✅ Logged run to {log_file}")


def norm(x):
    """
    Normalize the input by stripping whitespace and converting to lowercase.
    This is useful for string comparisons.
    """
    return x.strip().lower() if isinstance(x, str) else x


def update_counts(key, pred, actual, results):
    """
    Updated for Booli's evaluation logic:
    - Null prediction is only a false negative.
    - Wrong (non-null) prediction is only a false positive (no double-counting).
    - Only applies to string fields, not booleans!
    """

    if actual is None:
        # Do not penalize, skip: No ground truth, can't say anything
        return

    # Handle for string-valued fields
    if key.lower() in UNAMBIGUOUS_FIELDS:
        if pred is None:
            results[key]["fn"] += 1
        elif norm(pred) == norm(actual):
            results[key]["tp"] += 1
        else:
            # Wrong, non-null prediction: only FP
            results[key]["fp"] += 1
        return  # Done with string fields

    # Existing boolean/other field logic
    if pred is None:
        results[key]["fn"] += 1
    elif norm(pred) == norm(actual):
        results[key]["tp"] += 1
    else:
        pred_norm = norm(pred)
        actual_norm = norm(actual)

        if pred_norm == True and actual_norm == False:
            results[key]["fp"] += 1
        elif pred_norm == False and actual_norm == True:
            results[key]["fn"] += 1
        else:
            # For booleans, default: both (should rarely happen, but for legacy)
            results[key]["fp"] += 1
            results[key]["fn"] += 1



def evaluate_field_level(samples):
    results = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    for sample in samples:
        model = sample["model_output"]
        truth = sample["ground_truth"]

        for key in truth:
            if key == "SummaryInsights":  # Skip because interesting for Booli but fuzzy to evaluate
                continue

            pred = model.get(key)
            actual = truth.get(key)

            if isinstance(actual, dict) and isinstance(pred, dict):
                for subkey in actual:
                    sub_pred = pred.get(subkey)
                    sub_actual = actual.get(subkey)

                    sub_field = f"{key}.{subkey}"
                    update_counts(sub_field, sub_pred, sub_actual, results)
                    update_counts(key, sub_pred, sub_actual, results)  # Aggregate
            else:
                update_counts(key, pred, actual, results)
    return results


def build_results_table(results):
    rows = []
    for key, counts in results.items():
        tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
        total = tp + fp + fn
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        accuracy = tp / total if total > 0 else 0

        rows.append({
            "Field": key,
            "Accuracy": round(accuracy, 2),
            "Precision": round(precision, 2),
            "Recall": round(recall, 2),
            "F1 Score": round(f1, 2),
            "TP": tp,
            "FP": fp,
            "FN": fn
        })

    return pd.DataFrame(rows).sort_values(by="F1 Score", ascending=False)


def load_eval_files():
    data = []
    for filename in os.listdir(EVAL_FOLDER):
        if filename.endswith(".json"):
            with open(os.path.join(EVAL_FOLDER, filename), encoding="utf-8") as f:
                sample = json.load(f)
                data.append(sample)
    return data


def main():
    samples = load_eval_files()
    results = evaluate_field_level(samples)

    if not results:
        print("⚠️ No evaluation results found — make sure evaluation JSONs exist and are formatted correctly.")
        return

    table = build_results_table(results)

    # Full results as before
    print("\nEvaluation Results (All Fields):\n")
    print(table.to_string(index=False))

    summary = compute_summary_stats(results)
    print("\n\nEvaluation Summary (All Fields):\n")
    print(f"Total Samples: {len(samples)}")
    print(f"Total Fields Evaluated: {len(results)}")
    print(f"Total True Positives: {summary['tp']}")
    print(f"Total False Positives: {summary['fp']}")
    print(f"Total False Negatives: {summary['fn']}")
    print(f"Total Accuracy: {summary['accuracy']:.2f}")
    print(f"Total Precision: {summary['precision']:.2f}")
    print(f"Total Recall: {summary['recall']:.2f}")
    print(f"Total F1 Score: {summary['f1_score']:.2f}")

    # --- Unambiguous fields only ---
    unambiguous_table = table[table["Field"].isin(UNAMBIGUOUS_FIELDS)]
    print("\nEvaluation Results (Unambiguous Fields Only):\n")
    print(unambiguous_table.to_string(index=False))

    # Summarize unambiguous fields
    tp_u = unambiguous_table["TP"].sum()
    fp_u = unambiguous_table["FP"].sum()
    fn_u = unambiguous_table["FN"].sum()
    precision_u = tp_u / (tp_u + fp_u) if (tp_u + fp_u) else 0
    recall_u    = tp_u / (tp_u + fn_u) if (tp_u + fn_u) else 0
    f1_u        = (2 * precision_u * recall_u) / (precision_u + recall_u) if (precision_u + recall_u) else 0
    accuracy_u  = tp_u / (tp_u + fp_u + fn_u) if (tp_u + fp_u + fn_u) else 0

    print("\n\nEvaluation Summary (Unambiguous Fields Only):\n")
    print(f"Total True Positives: {tp_u}")
    print(f"Total False Positives: {fp_u}")
    print(f"Total False Negatives: {fn_u}")
    print(f"Total Accuracy: {accuracy_u:.2f}")
    print(f"Total Precision: {precision_u:.2f}")
    print(f"Total Recall: {recall_u:.2f}")
    print(f"Total F1 Score: {f1_u:.2f}")

    log_run_to_csv(results, run_name="gemini_2.5_flash_43_pdfs_v1", notes="TEST Unambiguous fields only, no double counting for string fields.")


if __name__ == "__main__":
    main()
