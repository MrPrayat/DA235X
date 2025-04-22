import json
import glob

eval_files = glob.glob("data/evaluation/*.json")
issues = []

for file in eval_files:
    with open(file, "r", encoding="utf-8") as f:
        data = json.load(f)
        gt = data["ground_truth"]
        pred = data["model_output"]
        
        if gt["InspectionDate"] and pred["InspectionDate"]:
            if gt["InspectionDate"].lower() != pred["InspectionDate"].lower():
                issues.append((file, "InspectionDate", gt["InspectionDate"], pred["InspectionDate"]))
        
        if gt["CadastralDesignation"] and pred["CadastralDesignation"]:
            if gt["CadastralDesignation"].lower() != pred["CadastralDesignation"].lower():
                issues.append((file, "CadastralDesignation", gt["CadastralDesignation"], pred["CadastralDesignation"]))

print("Mismatches found:")
for issue in issues:
    print(issue)
