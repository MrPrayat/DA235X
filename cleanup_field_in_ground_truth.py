import os
import json

folder = "evaluation"

for filename in os.listdir(folder):
    if filename.endswith(".json"):
        path = os.path.join(folder, filename)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        if "ground_truth" in data and "SummaryInsights" in data["ground_truth"]:
            del data["ground_truth"]["SummaryInsights"]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"🧼 Cleaned {filename}")
