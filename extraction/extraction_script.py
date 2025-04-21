import os
import csv
import json
import random
import time
import requests


from schema.schema import FIELDS, FIELD_DEFINITIONS
from utils.helpers import (
    call_openai_image_json,
    get_images_from_pdf,
    is_text_pdf,
    is_appendix_page_gpt,
    normalize_model_output,
    generate_default_ground_truth,
    synthesize_final_json,
)


def save_evaluation_json(pdf_id: str, model_output: dict, output_folder="data/evaluation"):
    """
    Saves model_output to a JSON file in the data/evaluation/ directory with ground_truth set to null.
    """
    os.makedirs(output_folder, exist_ok=True)
    out_path = os.path.join(output_folder, f"{pdf_id}.json")

    # If file exists, load and preserve any existing ground_truth
    if os.path.exists(out_path):
        with open(out_path, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
        existing_gt = existing_data.get("ground_truth", generate_default_ground_truth(model_output))
    else:
        existing_gt = generate_default_ground_truth(model_output)


    evaluation_data = {
        "pdf_id": pdf_id,
        "model_output": model_output,
        "ground_truth": existing_gt
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(evaluation_data, f, indent=2, ensure_ascii=False)

    print(f"Saved evaluation file: {out_path}")


def extract_fields_from_pdf_multipage(pdf_id: str, url: str) -> dict:
    """
    Extracts structured data from all pages of an image-based PDF:
      1. Convert each page to image.
      2. Query GPT-4o for field extraction per page.
      3. Combine page-level JSON outputs into one.
    Returns a merged dictionary with the best guess for each field.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException as error:
        print(f"Error fetching PDF: {error}")
        return {}

    pdf_bytes = response.content
    images = get_images_from_pdf(pdf_bytes, dpi=200)
    if not images:
        print("No images extracted from PDF.")
        return {}
    elif len(images) < 5:
        print(f"Skipping PDF with ID {pdf_id}: too short ({len(images)} pages).")
        return {}

    field_lines = [f'- "{key}": {FIELD_DEFINITIONS[key]}' for key in FIELDS]
    json_template = "{\n" + ",\n".join([f'  "{key}": null' for key in FIELDS]) + "\n}"

    prompt_text = (
        "You are analyzing a page from a Swedish housing inspection report. "
        "Extract the following fields if they are clearly visible. "
+       "If a field is not mentioned or not applicable, set it to false."

        "Field definitions:\n"
        + "\n".join(field_lines) + "\n\n"

        "Instructions:\n"
        "- Return the extracted values in **exactly** the JSON format shown below.\n"
        "- For all fields, use false if the information is not present or readable.\n\n"

        "- For InspectionDate:\n"
        "  • Only extract the **year and month**, in the format YYYY-MM.\n\n"

        "- For MoistureDamage:\n"
        "    • Use the object format with fixed keys:\n"
        "        - mentions_garage, mentions_källare, mentions_roof, mentions_balcony, mentions_bjälklag, mentions_facade.\n"
        "    • Each value must be true if water damage or moisture issues are clearly mentioned in that location, else false.\n\n"


        "- For RenovationNeeds:\n"
        "   • Only use the following fixed keys: 'roof', 'garage', 'facade', 'balcony', 'källare', 'bjälklag'.\n"
        "   • Set each value to true only if there is a **clear and direct statement** indicating the need for renovation in that area.\n"
        "   • Use true for phrases like 'slitage', 'dåligt skick', 'bör åtgärdas', or specific plans/timelines for future renovation.\n"
        "   • If the area is mentioned but no issue is present, or if it is not mentioned at all, set to false.\n\n"


        "- For AsbestosPresence:\n"
        "  • 'presence': true if asbestos is mentioned, false if unmentioned.\n"
        "  • 'Measured': true if there is explicit mention of measurement or testing.\n\n"

        "- For SummaryInsights:\n"
        "  • Write a short free-text summary of 1–3 clearly stated renovation actions.\n"
        "  • Use plain Swedish, max 1–2 sentences.\n"
        "  • Only include this if specific, actionable renovations are mentioned.\n"
        "  • Set to null if nothing actionable is described.\n"

        "Return exactly the following JSON format:\n"
        "```json\n" + json_template + "\n```"
    )

    all_results = []

    for i, page_img in enumerate(images):
        print(f"Checking if page {i+1} is an appendix...")
        if is_appendix_page_gpt(page_img):
            print(f"Page {i+1} flagged as appendix. Skipping the rest of PDF {pdf_id}.")
            break
    
        print(f"Processing page {i+1}/{len(images)}...")
        raw = call_openai_image_json(page_img, prompt_text)

        if raw.startswith("```json"):
            raw = raw.strip("```json").strip("```").strip()

        try:
            parsed = json.loads(raw)
            all_results.append(parsed)
        except json.JSONDecodeError:
            print(f"Page {i+1}: Could not parse JSON. Raw output:\n{raw}")
            all_results.append({"error": "Could not parse", "raw_output": raw})

    # ✅ NEW: Save per-page logs to disk
    os.makedirs("data/page_logs", exist_ok=True)
    with open(f"data/page_logs/{pdf_id}_pages.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    return synthesize_final_json(all_results)


def run_pdf_tests(test_amount: int, skip: bool, inspection_urls_path: str) -> None:
    """
    Runs extraction on a set of image-based PDFs and saves evaluation-ready JSON files.
    """
    pdfs_read = 0
    with open(inspection_urls_path, mode="r", encoding="utf-8-sig") as csvfile:
        reader = csv.DictReader(csvfile)
        for _, row in enumerate(reader):
            if pdfs_read >= test_amount:
                break

            pdf_id = row["id"]
            url = row["url"]

            if is_text_pdf(url):
                print(f"Skipping text-based PDF: {pdf_id}")
                continue

            if skip:
                # Skip if already evaluated for testing purposes
                evaluation_path = os.path.join("data/evaluation", f"{pdf_id}.json")
                if os.path.exists(evaluation_path):
                    print(f"Already evaluated: {pdf_id} — Skipping.")
                    continue

            print(f"\nExtracting fields from PDF ID: {pdf_id} with url: {url}")
            model_output = extract_fields_from_pdf_multipage(pdf_id, url)

            if model_output:
                normalized_output = normalize_model_output(model_output)
                save_evaluation_json(pdf_id, normalized_output)
                pdfs_read += 1
            else:
                print(f"Extraction failed or empty for ID {pdf_id}")


def extract_specific_pdfs(pdf_ids: list[str], inspection_urls_path: str) -> None:
    """
    Re-runs extraction only for specific PDF IDs (regardless of existing files).
    """
    with open(inspection_urls_path, mode="r", encoding="utf-8-sig") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            pdf_id = row["id"]
            if pdf_id not in pdf_ids:
                continue

            url = row["url"]
            print(f"\nRe-extracting PDF ID: {pdf_id} with url: {url}")
            model_output = extract_fields_from_pdf_multipage(pdf_id, url)

            if model_output:
                normalized_output = normalize_model_output(model_output)
                save_evaluation_json(pdf_id, normalized_output)
            else:
                print(f"❌ Extraction failed or was skipped for ID {pdf_id}")
