import os
import csv
import json
import requests
from schema.schema import FIELDS, FIELD_DEFINITIONS
from utils.helpers import (
    call_openai_image_json,
    call_gemini_image_json,
    get_images_from_pdf,
    is_text_pdf,
    normalize_model_output,
    generate_default_ground_truth,
    call_openai_multipage,
    cost_usd,
    log_pdf_usage,
    log_batch_summary,
    load_image_pdf_ids
)
from utils.pricing import PRICES #ta bort om usd grejen fungerar
from collections import defaultdict
from datetime import datetime

# === Constants ===
MODEL_NAME = "gpt-4o"
EXTRACTION_STRATEGY = "multipage"

# === Variables ===
token_meter = defaultdict(lambda: {"prompt": 0, "completion": 0, "cached": 0})
batch_token_meter = {"prompt": 0, "completion": 0, "cached": 0}
num_pdfs_processed = 0
# === Batch metadata ===

start_time = datetime.now()
batch_id = start_time.strftime("batch_%Y-%m-%d_%H%M")
batch_pdf_dir = f"data/logs/per_pdf_costs/{batch_id}"
batch_pdf_csv = os.path.join(batch_pdf_dir, "per_pdf_costs.csv")
batch_summary_csv = "data/logs/batch_summaries.csv"

# Create folders
os.makedirs(batch_pdf_dir, exist_ok=True)

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
    global num_pdfs_processed
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException as error:
        print(f"Error fetching PDF: {error}")
        return {}

    pdf_bytes = response.content
    images = get_images_from_pdf(pdf_bytes, dpi=200)

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


    final_json, usage = call_openai_multipage(pdf_id, prompt_text, MODEL_NAME)

    try:
        final_json = json.loads(final_json)
    except json.JSONDecodeError:
        print(f"PDF with id {pdf_id}: Could not parse JSON. Raw output:\n{final_json}")

    # Update cumulative totals
    token_meter[pdf_id]["prompt"] += usage["prompt_tokens"]
    token_meter[pdf_id]["completion"] += usage["completion_tokens"]
    token_meter[pdf_id]["cached"] += usage["cached_tokens"]

    # Calculate step cost using Gemini
    step_tokens = {
        "prompt": usage["prompt_tokens"],
        "completion": usage["completion_tokens"],
        "cached": usage["cached_tokens"],
    }
    step_cost = cost_usd(step_tokens, model=MODEL_NAME)
    cumulative_cost = cost_usd(token_meter[pdf_id], model=MODEL_NAME)

    # Print total token usage and cost
    print("🧪 Final synthesis step completed!")
    print(f"   🧮 Synthesis cost: ${step_cost:.6f}")
    print(f"   📈 Final cumulative usage for {pdf_id}: {token_meter[pdf_id]}")
    print(f"   💰 Final total cost: ${cumulative_cost:.6f}")
    print("=" * 80)

    # Save usage data to CSV
    log_pdf_usage(
        csv_path=batch_pdf_csv,
        pdf_id=pdf_id,
        model=MODEL_NAME,
        extraction_strategy=EXTRACTION_STRATEGY,  # or "page-by-page", "field-by-field"
        prompt_tokens=token_meter[pdf_id]["prompt"],
        completion_tokens=token_meter[pdf_id]["completion"],
        cached_tokens=token_meter[pdf_id]["cached"],
        total_cost_usd=cumulative_cost,
        pages_extracted=len(images),
    )

    # Add total prompt, completion and cached tokens as well as total cost for the whole batch
    batch_token_meter["prompt"] += token_meter[pdf_id]["prompt"]
    batch_token_meter["completion"] += token_meter[pdf_id]["completion"]
    batch_token_meter["cached"] += token_meter[pdf_id]["cached"]
    num_pdfs_processed += 1

    return final_json


def process_single_pdf(pdf_id: str, url: str, skip: bool) -> bool:
    """
    Process a single PDF and return whether it was successfully processed.
    """
    if skip:
        # Skip if already evaluated for testing purposes
        evaluation_path = os.path.join("data/evaluation", f"{pdf_id}.json")
        if os.path.exists(evaluation_path):
            print(f"Already evaluated: {pdf_id} — Skipping.")
            return False

    print(f"\nExtracting fields from PDF ID: {pdf_id} with url: {url}")
    model_output = extract_fields_from_pdf_multipage(pdf_id, url)

    if model_output:
        normalized_output = normalize_model_output(model_output)
        save_evaluation_json(pdf_id, normalized_output)
        return True
    else:
        print(f"Extraction failed or empty for ID {pdf_id}")
        return False


def run_pdf_tests(test_amount: int, skip: bool, inspection_urls_path: str, reextract_already_extracted_only: bool) -> None:
    """
    Runs extraction on a set of image-based PDFs and saves evaluation-ready JSON files.
    """
    image_pdf_ids = load_image_pdf_ids() if reextract_already_extracted_only else []

    pdfs_read = 0
    with open(inspection_urls_path, mode="r", encoding="utf-8-sig") as csvfile:
        reader = csv.DictReader(csvfile)
        for _, row in enumerate(reader):
            if pdfs_read >= test_amount:
                break

            pdf_id = row["id"]
            url = row["url"]

            if image_pdf_ids and pdf_id not in image_pdf_ids:
                print(f"Skipping non-whitelisted PDF: {pdf_id}")
                continue

            if process_single_pdf(pdf_id, url, skip):
                pdfs_read += 1

    # Calculate final batch cost
    batch_total_cost = cost_usd(batch_token_meter, model=MODEL_NAME)

    # Save batch summary
    log_batch_summary(
        csv_path=batch_summary_csv,
        batch_id=batch_id,
        model=MODEL_NAME,
        extraction_strategy=EXTRACTION_STRATEGY,
        num_pdfs=num_pdfs_processed,
        prompt_tokens=batch_token_meter["prompt"],
        completion_tokens=batch_token_meter["completion"],
        cached_tokens=batch_token_meter["cached"],
        total_cost_usd=batch_total_cost,
    )

    # Final printout
    print("=" * 80)
    print(f"📦 Batch completed: {num_pdfs_processed} PDFs processed")
    print(f"🧮 Batch Total Prompt tokens: {batch_token_meter['prompt']}")
    print(f"🧮 Batch Total Completion tokens: {batch_token_meter['completion']}")
    print(f"🧮 Batch Total Cached tokens: {batch_token_meter['cached']}")
    print(f"💰 Batch Total Cost: ${batch_total_cost:.6f}")
    print("=" * 80)



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
