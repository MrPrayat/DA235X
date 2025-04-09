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
        existing_gt = existing_data.get("ground_truth", {field: None for field in FIELDS})  # Python None will become "null" in JSON once ewe use json.dump later on to populate the json files
    else:
        existing_gt = {field: None for field in FIELDS}

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

def call_openai_image_json(image: Image.Image, prompt: str, model: str = "gpt-4o-mini", retries=5, backoff=2) -> str:
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


def synthesize_final_json(page_results: list, model="gpt-4o-mini", retries=5, backoff=2) -> dict:
    """
    Given a list of page-level JSONs, ask GPT-4o-mini to synthesize them into one coherent JSON.
    Retries if rate-limited.
    """
    print("Synthesizing from page-level results...")

    field_lines = [f'- "{key}": {FIELD_DEFINITIONS[key]}' for key in FIELDS]
    json_template = "{\n" + ",\n".join([f'  "{key}": null' for key in FIELDS]) + "\n}"

    prompt = (
        "You are given a list of partial JSON outputs extracted from different pages of a housing inspection report.\n"
        "Each JSON may contain correct or incorrect values, or have missing fields.\n"
        "Your job is to reason through them and return a single, best-version JSON object.\n\n"
        "Definitions:\n"
        "- Use the most complete and accurate value for each field.\n"
        "- If a field is present in multiple JSONs, prefer the one that looks most correct.\n"
        "- If a field is missing in all, set it to null.\n\n"
        "Field definitions:\n"
        + "\n".join(field_lines) +
        "\n\nReturn the final output in the following format:\n"
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



def extract_fields_from_pdf_multipage(url: str) -> dict:
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
        "If a field is missing or unreadable, set its value to null.\n\n"

        "Field definitions:\n"
        + "\n".join(field_lines) + "\n\n"

        "Instructions:\n"
        "- Return the extracted values in **exactly** the JSON format shown below.\n"
        "- For all fields, use null if the information is not present or readable.\n"

        "- For InspectionDate:\n"
        "  • Only return the year and month in format YYYY-MM (e.g., '2023-11').\n"
        "  • If multiple dates are mentioned, prefer the **earliest inspection date**.\n\n"

        "- For WaterLeakage:\n"
        "  • Use an object with exactly these keys:\n"
        "    - mentions_garage, mentions_källare, mentions_roof, mentions_balcony, mentions_bjälklag, mentions_fasad\n"
        "  • Set each to true/false/null based on whether water-related issues are clearly mentioned for that location.\n\n"

        "- For RenovationNeeds:\n"
        "  • Use an object with exactly these keys:\n"
        "    - roof, garage, facade, balcony, källare, bjälklag\n"
        "  • Set the value to true if renovation is clearly and explicitly needed.\n"
        "  • Set to null if the area is not mentioned or no issue is found.\n\n"

        "- For AsbestosPresence and RadonPresence:\n"
        "  • 'presence': true if the material is mentioned at all, false if explicitly ruled out, null if not mentioned.\n"
        "  • 'Measured': true if a test or numeric measurement is mentioned, otherwise false or null.\n"
        "  • RadonPresence also includes 'level': include the numeric radon value if mentioned, else set to null.\n\n"

        "Return the result in exactly the following JSON format:\n"
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

    # Merge all the results (prioritizing first non-null value for each field)
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

            if skip:
                # Skip if already evaluated for testing purposes
                evaluation_path = os.path.join("evaluation", f"{pdf_id}.json")
                if os.path.exists(evaluation_path):
                    print(f"Already evaluated: {pdf_id} — Skipping.")
                    continue

            if is_text_pdf(url):
                print(f"Skipping text-based PDF: {pdf_id}")
                continue

            print(f"\nExtracting fields from PDF ID: {pdf_id} with url: {url}")
            model_output = extract_fields_from_pdf_multipage(url)

            if model_output:
                save_evaluation_json(pdf_id, model_output)
                pdfs_read += 1
            else:
                print(f"Extraction failed or empty for ID {pdf_id}")


def main():
    print("Main function started.")
    # Run PDF test on sample CSV URLs
    run_pdf_tests(4, False) #amounts of image-based PDFs to process


if __name__ == "__main__":
    main()
