from openai import OpenAI
from openai import RateLimitError
import io
import requests
import fitz
import csv
import base64
import json
import time
import random
import os
from pdf2image import convert_from_bytes
from PIL import Image
from schema import FIELDS, FIELD_DEFINITIONS


client = OpenAI()


def normalize_model_output(output):
    """
    Ensures model_output always contains all expected fields with proper nested structure.
    """
    def normalize_field(value, template):
        if isinstance(template, dict):
            return {k: value.get(k) if isinstance(value, dict) and k in value else None for k in template}
        return value if value is not None else None

    normalized = {}
    for field in FIELDS:
        template = json.loads(json.dumps(generate_default_ground_truth({field: FIELD_DEFINITIONS.get(field)}).get(field)))
        normalized[field] = normalize_field(output.get(field), template)

    return normalized


def generate_default_ground_truth(model_output):
    """
    Creates a ground truth dictionary with the same structure as the model_output,
    but with all values set to null.
    """
    def nullify(value):
        if isinstance(value, dict):
            return {k: None for k in value}
        return None

    return {field: nullify(model_output.get(field)) for field in FIELDS}


def save_evaluation_json(pdf_id: str, model_output: dict, output_folder="evaluation"):
    """
    Saves model_output to a JSON file in the evaluation/ directory with ground_truth set to null.
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


def is_text_pdf(url: str, min_chars=5000) -> bool:
    """
    Determines if a PDF is text-based by counting meaningful visible characters.
    Returns True only if enough visible text is found (e.g., 200+ characters total).
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        pdf_data = io.BytesIO(response.content)
        doc = fitz.open("pdf", stream=pdf_data)

        total_visible_chars = 0

        for page in doc:
            blocks = page.get_text("blocks")
            for block in blocks:
                text = block[4].strip()
                if len(text) >= 15:  # Only count substantial lines
                    total_visible_chars += len(text)

            # Early exit if already clearly text-based
            if total_visible_chars >= min_chars:
                return True

    except Exception as e:
        print(f"Error checking PDF: {e}")

    return False  # Default: treat as image-based if uncertain



def get_images_from_pdf(pdf_bytes, dpi=200):
    """
    Converts PDF bytes to a list of PIL Image objects using pdf2image.
    """
    POPPLER_PATH = r'C:/Program Files (x86)/poppler-24.08.0/Library/bin'
    return convert_from_bytes(pdf_bytes, dpi=dpi, poppler_path=POPPLER_PATH)

def encode_image(image: Image.Image) -> str:
    """
    Encodes a PIL Image object into a base64 string.
    """
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

def call_openai_image_json(image: Image.Image, prompt: str, model: str = "gpt-4o", retries=5, backoff=2) -> str:
    """
    Calls the OpenAI chat completions API with a text prompt and image input.
    The prompt instructs the model to extract structured information from the image.
    Returns the response content (expected to be JSON).
    Retrying if rate limit error occurs.
    """
    base64_image = encode_image(image)
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            },
                        },
                    ],
                }],
                temperature=0,
                top_p=0,
            )
            return response.choices[0].message.content

        except RateLimitError as e:
            wait_time = backoff * (2 ** attempt) + random.uniform(0, 1)
            print(f"Rate limit hit (attempt {attempt+1}/{retries}). Retrying in {wait_time:.1f}s...")
            time.sleep(wait_time)
        except Exception as e:
            print(f"GPT call failed with error: {e}")
            break

    return ""


def synthesize_final_json(page_results: list, model="gpt-4o", retries=5, backoff=2) -> dict:
    """
    Given a list of page-level JSONs, ask GPT-4o to synthesize them into one coherent JSON.
    Retries if rate-limited.
    """
    print("Synthesizing from page-level results...")

    field_lines = [f'- "{key}": {FIELD_DEFINITIONS[key]}' for key in FIELDS]
    json_template = "{\n" + ",\n".join([f'  "{key}": null' for key in FIELDS]) + "\n}"

    prompt = (
        "You are given a list of partial JSON outputs extracted from different pages of a housing inspection report.\n"
        "Each JSON may contain correct or incorrect values, or have missing fields.\n"
        "Your job is to reason through them and return a single, best-version JSON object.\n\n"
        "Instructions:\n"
        "- For all fields, use the most complete and accurate value.\n"
        "- If a field is missing in all pages, return a reasonable default.\n"
        "- **Always include 'SummaryInsights', even if no insights are found.**\n"
        "- Return in exactly the JSON format shown below.\n\n"
        "Field definitions:\n"
        + "\n".join(field_lines) +
        "\n\nReturn the final merged JSON:\n"
        "```json\n" + json_template + "\n```\n"
        f"Here is the list of page-level JSONs:\n\n"
        f"{json.dumps(page_results, indent=2, ensure_ascii=False)}\n\n"
        "Now return the final merged JSON object:"
    )

    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )

            output = response.choices[0].message.content
            if output.startswith("```json"):
                output = output.strip("```json").strip("```").strip()

            return json.loads(output)

        except RateLimitError as e:
            wait_time = backoff * (2 ** attempt) + random.uniform(0, 1)
            print(f"Rate limit hit in synthesis (attempt {attempt+1}/{retries}). Retrying in {wait_time:.1f}s...")
            time.sleep(wait_time)
        except json.JSONDecodeError:
            print("Could not decode JSON in final synthesis.")
            return {}
        except Exception as e:
            print(f"GPT call failed in synthesis step: {e}")
            break

    return {}



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

        "- For WaterLeakage:\n"
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
    os.makedirs("page_logs", exist_ok=True)
    with open(f"page_logs/{pdf_id}_pages.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    return synthesize_final_json(all_results)


def run_pdf_tests(test_amount: int, skip: bool) -> None:
    """
    Runs extraction on a set of image-based PDFs and saves evaluation-ready JSON files.
    """
    pdfs_read = 0
    with open("inspection_urls.csv", mode="r", encoding="utf-8-sig") as csvfile:
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
                evaluation_path = os.path.join("evaluation", f"{pdf_id}.json")
                if os.path.exists(evaluation_path):
                    print(f"Already evaluated: {pdf_id} — Skipping.")
                    pdfs_read += 1  # so that we can skip the test amount
                    continue

            print(f"\nExtracting fields from PDF ID: {pdf_id} with url: {url}")
            model_output = extract_fields_from_pdf_multipage(pdf_id, url)

            if model_output:
                normalized_output = normalize_model_output(model_output)
                save_evaluation_json(pdf_id, normalized_output)
                pdfs_read += 1
            else:
                print(f"Extraction failed or empty for ID {pdf_id}")


def main():
    print("Main function started.")
    # Run PDF test on sample CSV URLs with 
    # 1st arg being the amount of PDFs to process
    # 2nd arg being whether to skip already evaluated PDFs
    run_pdf_tests(8, False) 


if __name__ == "__main__":
    main()
