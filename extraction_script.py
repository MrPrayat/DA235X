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
from pdf2image import convert_from_bytes
from PIL import Image
from schema import FIELDS, FIELD_DEFINITIONS


client = OpenAI()

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


def synthesize_final_json(page_results: list) -> dict:
    """
    Given a list of page-level JSONs, ask GPT-4o-mini to synthesize them into one coherent JSON.
    """
    print("Synthesizing from page-level results:")

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

    # # Uncomment the following lines to debug the prompt and page results
    # print(json.dumps(page_results, indent=2, ensure_ascii=False))

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    output = response.choices[0].message.content
    if output.startswith("```json"):
        output = output.strip("```json").strip("```").strip()

    try:
        return json.loads(output)
    except json.JSONDecodeError as e:
        print("JSON decode failed in final synthesis. Output:\n", output)
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
        + "\n".join(field_lines) +
        "\n\nReturn the extracted values in **exactly** the following JSON format. "
        "If a field is missing, set it to null. Do not include any explanation, headers, or commentary.\n"
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



def run_pdf_test():
    """
    Tests a specified number of PDF URLs for being text-based or image-based and attempts data extraction.
    Determines whether a PDF is text-based by checking for a significant amount of visible text.
    Returns True if the PDF contains meaningful, visible text; False otherwise.
    """
    test_amount = 50  # Set the number of tests to run

    with open("inspection_urls.csv", mode="r", encoding="utf-8-sig") as csvfile:
        reader = csv.DictReader(csvfile)
        for index, row in enumerate(reader):
            if index >= test_amount:
                break
            url = row["url"]
            # print(f"\n---\nID {row['id']} – Checking: {url}")
            text_based = is_text_pdf(url)
            # print(f"Is text-based: {text_based}")
            if not text_based:
                # extracted = extract_fields_from_pdf_multipage(url)
                # print(f"Extracted for ID {row['id']}:\n{json.dumps(extracted, indent=2, ensure_ascii=False)}")
                print(f"ID: {row['id']}, URL: {url}")
            else:
                continue
                # print("Skipping text-based PDF.")


def main():
    print("Main function started.")
    # Run PDF test on sample CSV URLs
    run_pdf_test()


if __name__ == "__main__":
    main()
