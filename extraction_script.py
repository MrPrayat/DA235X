from openai import OpenAI
import io
import requests
import fitz
import csv
import base64
import json
from pdf2image import convert_from_bytes
from PIL import Image


client = OpenAI()

def is_text_pdf(url: str) -> bool:
    """
    Determines whether a PDF, fetched from the provided URL, is text-based or image-based.
    Returns True if the PDF is image-based (i.e., contains no non-whitespace text), 
    and False if any text is found or an error occurs.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException as error:
        print(f"Error fetching PDF: {error}")
        return False

    pdf_data = io.BytesIO(response.content)
    try:
        doc = fitz.open("pdf", stream=pdf_data)
    except Exception as error:
        print(f"Error opening PDF: {error}")
        return False

    for page in doc:
        if page.get_text().strip():
            return False
    return True

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

def call_openai_image_json(image: Image.Image, prompt: str, model: str = "gpt-4o-mini") -> str:
    """
    Calls the OpenAI chat completions API with a text prompt and image input.
    The prompt instructs the model to extract structured information from the image.
    Returns the response content (expected to be JSON).
    """
    base64_image = encode_image(image)
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
        temperature=0  # use low temperature for deterministic output
    )
    return response.choices[0].message.content

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

    prompt_text = (
        "This is a page from a Swedish housing inspection report. "
        "Extract the following fields if they are clearly present in the image. "
        "If a field is missing or unreadable, set its value to null.\n\n"
        "Return the result in exactly this JSON format:\n"
        "```json\n"
        "{\n"
        "  \"CadastralDesignation\": null,\n"
        "  \"PostalAddress\": null,\n"
        "  \"WaterLeakage\": null,\n"
        "  \"InspectionCompany\": null,\n"
        "  \"InspectionDate\": null,\n"
        "  \"ExpirationDate\": null,\n"
        "  \"BuildingDescription\": null,\n"
        "  \"EnergyData\": null,\n"
        "  \"LastRenovation\": null,\n"
        "  \"RadonLevels\": null\n"
        "}\n"
        "```\n"
        "Only return the JSON object. Do not include commentary or headers."
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
            print(f"⚠️ Page {i+1}: Could not parse JSON. Raw output:\n{raw}")

    # Merge all the results (prioritizing first non-null value for each field)
    merged = {}
    keys = [
        "CadastralDesignation", "PostalAddress", "WaterLeakage", "InspectionCompany",
        "InspectionDate", "ExpirationDate", "BuildingDescription", "EnergyData",
        "LastRenovation", "RadonLevels"
    ]
    for key in keys:
        merged[key] = None
        for result in all_results:
            if key in result and result[key] not in [None, "", "null"]:
                merged[key] = result[key]
                break  # take first valid value

    return merged


def run_pdf_test():
    """
    Tests a specified number of PDF URLs for being text-based or image-based and attempts data extraction.
    The function opens the CSV file "inspection_urls.csv" which should contain 'id' and 'url' columns.
    For each URL, it checks if the PDF is text-based. If image-based, it tries to extract structured data.
    The results for each test are printed to the console.
    """
    test_amount = 3  # Set the number of tests to run

    with open("inspection_urls.csv", mode="r", encoding="utf-8-sig") as csvfile:
        reader = csv.DictReader(csvfile)
        for index, row in enumerate(reader):
            if index >= test_amount:
                break
            url = row["url"]
            print(f"\n---\nID {row['id']} – Checking: {url}")
            image_based = is_text_pdf(url)
            print(f"Is text-based: {not image_based}")
            if not image_based:
                extracted = extract_fields_from_pdf_multipage(url)
                print(f"Extracted for ID {row['id']}:\n{json.dumps(extracted, indent=2)}")
            else:
                print("Skipping text-based PDF.")


def main():
    print("Main function started.")
    # Run PDF test on sample CSV URLs
    run_pdf_test()

    # Uncomment below to test the simple image description extraction function
    # image_description = extract_image_description()
    # print("Image description:", image_description)

if __name__ == "__main__":
    main()
