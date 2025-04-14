import os
import json
from collections import defaultdict
import pandas as pd
import datetime

EVAL_FOLDER = "evaluation"

def log_run_to_csv(results, run_name, notes="", log_file="evaluation_log.csv"):
    """
    Logs the evaluation results to a CSV file.
    """
    # Calculate summary stats
    total_tp = sum(c['tp'] for c in results.values())
    total_fp = sum(c['fp'] for c in results.values())
    total_fn = sum(c['fn'] for c in results.values())
    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    accuracy = total_tp / (total_tp + total_fp + total_fn) if (total_tp + total_fp + total_fn) > 0 else 0

    new_row = {
        "timestamp": datetime.datetime.now().isoformat(),
        "run_name": run_name,
        "notes": notes,
        "true_positives": total_tp,
        "false_positives": total_fp,
        "false_negatives": total_fn,
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4)
    }

    # Append to CSV
    try:
        df = pd.read_csv(log_file)
    except FileNotFoundError:
        df = pd.DataFrame()

    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(log_file, index=False)
    print(f"✅ Logged run to {log_file}")


def update_counts(key, pred, actual, results):
    if actual is None:
        return
    if pred is None:
        results[key]["fn"] += 1
    elif pred == actual:
        results[key]["tp"] += 1
    else:
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


#samples = load_eval_files()
# Sample below loads the latest 2 files in the evaluation folder
# This is useful for testing and debugging
# For another set of files, you can change the key in the sorted function
samples = sorted(load_eval_files(), key=lambda s: s["pdf_id"], reverse=True)[:2]
results = evaluate_field_level(samples)
table = build_results_table(results)

# Show dataframe as table
print("\nEvaluation Results:\n")
print(table.to_string(index=False))
print("\n\n")
print("Evaluation Summary:\n")
print(f"Total Samples: {len(samples)}")
print(f"Total Fields Evaluated: {len(results)}")
print(f"Total True Positives: {sum(counts['tp'] for counts in results.values())}")
print(f"Total False Positives: {sum(counts['fp'] for counts in results.values())}")
print(f"Total False Negatives: {sum(counts['fn'] for counts in results.values())}")
# We don’t count TN because we never penalize or reward the model for not guessing fields that were never annotated.
# This is standard practice in NER, form extraction, and key-value document understanding.
print(f"Total Accuracy: {table['Accuracy'].mean():.2f}")
print(f"Total Precision: {table['Precision'].mean():.2f}")
print(f"Total Recall: {table['Recall'].mean():.2f}")
print(f"Total F1 Score: {table['F1 Score'].mean():.2f}")

log_run_to_csv(results, run_name="no_appendix", notes="Clean run with no appendix")
