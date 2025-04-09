import json
import os
from schema import FIELDS

def generate_template(pdf_id: str, output_folder="evaluation"):
    """
    Generate a JSON template for the given PDF ID.
    The template contains fields for model output and ground truth."
    """
    os.makedirs(output_folder, exist_ok=True)

    template = {
        "pdf_id": pdf_id,
        "model_output": {field: None for field in FIELDS},
        "ground_truth": {field: None for field in FIELDS}
    }

    out_path = os.path.join(output_folder, f"{pdf_id}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(template, f, indent=2, ensure_ascii=False)

    print(f"✅ Created template for {pdf_id} at {out_path}")

# Example usage:
# generate_template("MYTESTPDF123")

def main():
    generate_template("pdf_id_template")
    print("Template generation complete.")


main()