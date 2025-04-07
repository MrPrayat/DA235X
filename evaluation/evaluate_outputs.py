import os
import json
from collections import defaultdict

EVAL_FOLDER = "evaluation"

def load_eval_files():
    data = []
    for filename in os.listdir(EVAL_FOLDER):
        if filename.endswith(".json"):
            with open(os.path.join(EVAL_FOLDER, filename), encoding="utf-8") as f:
                sample = json.load(f)
                data.append(sample)
    return data

def evaluate_field_level(samples):
    results = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})

    for sample in samples:
        model = sample["model_output"]
        truth = sample["ground_truth"]

        for key in truth:
            pred = model.get(key)
            actual = truth.get(key)

            if actual is None:
                continue  # skip fields that are undefined

            if pred is None or pred == "":
                results[key]["fn"] += 1
            elif pred.strip() == actual.strip():
                results[key]["tp"] += 1
            else:
                results[key]["fp"] += 1
                results[key]["fn"] += 1

    return results

def print_metrics(results):
    print("\nField-Level Metrics:")
    for key, counts in results.items():
        tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

        print(f"🔹 {key}")
        print(f"   Precision: {precision:.2f} | Recall: {recall:.2f} | F1: {f1:.2f} (TP: {tp}, FP: {fp}, FN: {fn})")

def main():
    samples = load_eval_files()
    if not samples:
        print("No evaluation files found in 'evaluation/'")
        return

    results = evaluate_field_level(samples)
    print_metrics(results)

if __name__ == "__main__":
    main()
