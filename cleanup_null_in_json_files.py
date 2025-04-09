import os
import json

EVAL_DIR = "evaluation"

def convert_nulls_to_false(data):
    if isinstance(data, dict):
        return {k: convert_nulls_to_false(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_nulls_to_false(v) for v in data]
    elif data is None:
        return False
    return data

def fix_evaluation_files():
    updated = 0
    for filename in os.listdir(EVAL_DIR):
        if not filename.endswith(".json") or not filename[:-5].isdigit():
            continue

        path = os.path.join(EVAL_DIR, filename)
        with open(path, "r", encoding="utf-8") as f:
            content = json.load(f)

        updated_model = convert_nulls_to_false(content["model_output"])
        updated_truth = convert_nulls_to_false(content["ground_truth"])

        content["model_output"] = updated_model
        content["ground_truth"] = updated_truth

        with open(path, "w", encoding="utf-8") as f:
            json.dump(content, f, indent=2, ensure_ascii=False)

        updated += 1

    print(f"✅ Updated {updated} JSON files in '{EVAL_DIR}'.")

if __name__ == "__main__":
    fix_evaluation_files()
