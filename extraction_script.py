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


client = OpenAI()

def is_text_pdf(url: str) -> bool:
    """
    Determines whether a PDF, fetched from the provided URL, is text-based or image-based.
    Returns True if the PDF is text-based (i.e., contains no non-whitespace text), 
    and False if no text is found or an error occurs.
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
            return True
    return False

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
    prompt = (
        "You are given a list of partial JSON outputs extracted from different pages of a housing inspection report.\n"
        "Each JSON may contain correct or incorrect values, or have missing fields.\n"
        "Your job is to reason through them and return a single, best-version JSON object.\n\n"
        "Definitions:\n"
        "- Use the most complete and accurate value for each field.\n"
        "- If a field is present in multiple JSONs, prefer the one that looks most correct.\n"
        "- If a field is missing in all, set it to null.\n"
        "- Return exactly the following format, with no comments:\n\n"
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
        "  \"RenovationNeeds\": null\n"
        "  \"HeatingSystem\": null\n"
        "  \"VentilationType\": null\n"
        "}\n"
        "```\n"
        "Here is the list of page-level JSONs:\n\n"
        f"{json.dumps(page_results, indent=2, ensure_ascii=False)}\n\n"
        "Now return the final merged JSON object:"
    )
    # # Uncomment the following lines to debug the prompt and page results
    # print("Synthesizing from page-level results:")
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

    prompt_text = (
        "You are analyzing a page from a Swedish housing inspection report. "
        "Extract the following fields if they are clearly visible. "
        "If a field is missing or unreadable, set its value to null.\n\n"
        "Field definitions:\n"
        "- \"CadastralDesignation\": The full legal property name (*fastighetsbeteckning*), including områdesnamn, blocknummer, and enhetsnummer. Example: \"Törnevalla Skäckelstad 2:7\".\n"
        "- \"PostalAddress\": The full postal address, typically including street name, postal code, and city. Do not confuse this with the fastighetsbeteckning.\n"
        "- \"WaterLeakage\": Any mention of water damage, smygläckage, or moisture issues. Include the full sentence or summary.\n"
        "- \"InspectionCompany\": The company name that performed the inspection (e.g., Anticimex).\n"
        "- \"InspectionDate\": The date the inspection was performed, in format YYYY-MM-DD.\n"
        "- \"ExpirationDate\": The date until which the inspection report is valid (giltighetstid), in format YYYY-MM-DD.\n"
        "- \"BuildingDescription\": A general description of the building’s structure, type, or age.\n"
        "- \"EnergyData\": Information related to energy performance or usage, if available.\n"
        "- \"LastRenovation\": Date or description of the most recent renovation.\n"
        "- \"RadonLevels\": Reported radon level or a statement about radon presence, if mentioned.\n"
        "- \"RenovationNeeds\": Clear indication that renovation is required or recommended.\n"
        "- \"HeatingSystem\": Described heating system (e.g. fjärrvärme).\n"
        "- \"VentilationType\": Described ventilation type (e.g. självdrag).\n\n"
        "Return the extracted values in **exactly** the following JSON format. If a field is missing, set it to null. Do not include any explanation, headers, or commentary.\n"
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
        "  \"RenovationNeeds\": null\n"
        "  \"HeatingSystem\": null\n"
        "  \"VentilationType\": null\n"
        "}\n"
        "```"
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
    The function opens the CSV file "inspection_urls.csv" which should contain 'id' and 'url' columns.
    For each URL, it checks if the PDF is text-based. If image-based, it tries to extract structured data.
    The results for each test are printed to the console.
    """
    test_amount = 1  # Set the number of tests to run

    with open("inspection_urls.csv", mode="r", encoding="utf-8-sig") as csvfile:
        reader = csv.DictReader(csvfile)
        for index, row in enumerate(reader):
            if index >= test_amount:
                break
            url = row["url"]
            print(f"\n---\nID {row['id']} – Checking: {url}")
            text_based = is_text_pdf(url)
            print(f"Is text-based: {text_based}")
            if not text_based:
                extracted = extract_fields_from_pdf_multipage(url)
                print(f"Extracted for ID {row['id']}:\n{json.dumps(extracted, indent=2, ensure_ascii=False)}")
            else:
                print("Skipping text-based PDF.")


def main():
    print("Main function started.")
    # Run PDF test on sample CSV URLs
    run_pdf_test()


if __name__ == "__main__":
    main()
