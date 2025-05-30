from openai import OpenAI, RateLimitError
import base64
import io
import time
import random
import requests
import fitz
import json
import csv
import os
from pdf2image import convert_from_bytes
from PIL import Image
from schema.schema import FIELDS, FIELD_DEFINITIONS
from utils.pricing import PRICES
from datetime import datetime


# === GPT Helpers ===
client = OpenAI()

def call_openai_image_json(image: Image.Image, prompt: str, model: str, retries=5, backoff=2) -> tuple[str, dict]:
    """
    Calls the OpenAI chat completions API with a text prompt and image input.
    The prompt instructs the model to extract structured information from the image.
    Returns the response content (expected to be JSON) and usage information.
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
            output = response.choices[0].message.content
            usage = response.usage
            return output, usage

        except RateLimitError as e:
            wait_time = backoff * (2 ** attempt) + random.uniform(0, 1)
            print(f"Rate limit hit (attempt {attempt+1}/{retries}). Retrying in {wait_time:.1f}s...")
            time.sleep(wait_time)
        except Exception as e:
            print(f"GPT call failed with error: {e}")
            break

    return "", None


def synthesize_final_json(page_results: list, model: str, retries=5, backoff=2) -> tuple[dict, dict]:
    """
    Given a list of page-level JSONs, ask GPT-4o to synthesize them into one coherent JSON.
    Retries if rate-limited.
    Returns a tuple of (result_json, usage_info).
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
            usage = response.usage
            if output.startswith("```json"):
                output = output.strip("```json").strip("```").strip()

            return json.loads(output), usage

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


# === Image Utilities ===
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


def is_text_pdf(url: str, min_chars=3500) -> bool:
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


def is_appendix_page_gpt(image: Image.Image, model: str) -> tuple[bool, dict]:
    appendix_filter_prompt = (
        "You're reviewing a page from a Swedish housing inspection report. "
        "Your task is to determine whether this page is an *appendix* or *general conditions section*, typically found at the end of the document.\n"
        "Note that if it says the technical report itself is an appendix to another report then that is fine if that is explicitly mentioned."
        "We are only interested in removing the appendix that belongs to the technical report.\n"
        "We are interested in the inspection report regardless of it being an appendix to something else or not\n\n"

        "✅ Pages that **ARE** appendices include those labeled or titled with:\n"
        "- 'Bilaga'\n"
        "- 'Villkor'\n"
        "- 'Allmänna villkor'\n"
        "- 'Appendix'\n"
        "- 'Försäkringsvillkor'\n\n"

        "❌ Pages that are **NOT** appendices include:\n"
        "- 'Innehållsförteckning' (table of contents)\n"
        "- Regular report content like summaries, diagrams, measurements\n\n"

        "Respond strictly with one word:\n"
        "- 'yes' → if the page clearly **is** an appendix\n"
        "- 'no' → for all other pages, even if uncertain"
    )


    raw_response, usage = call_openai_image_json(image, appendix_filter_prompt, model)
    is_appendix = "yes" in raw_response.lower()
    return is_appendix, usage


# === Normalization ===
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
    def default_false(val):
        if isinstance(val, dict):
            # nested fields → all False
            return {k: False for k in val}
        # scalar fields → False
        return False

    return {
        field: default_false(model_output.get(field))
        for field in FIELDS
        if field != "SummaryInsights"  # Skip ground truth for SummaryInsights since we won't evaluate it
    }

def cost_usd(tokens: dict, model: str) -> float:
    """
    Compute the estimated USD cost of an OpenAI call based on token counts.

    Args:
        tokens (dict): A dict with keys 'prompt', 'completion', 'cached'.
        model (str): The AI model used.

    Returns:
        float: Estimated cost in USD.
    """
    prices = PRICES[model]
    input_tokens = tokens["prompt"] - tokens["cached"]
    cached_tokens = tokens["cached"]
    output_tokens = tokens["completion"]

    cost = (
        (input_tokens / 1_000_000) * prices["input"] +
        (cached_tokens / 1_000_000) * prices["cached input"] +
        (output_tokens / 1_000_000) * prices["output"]
    )
    return cost


def log_pdf_usage(
    csv_path: str,
    pdf_id: str,
    model: str,
    extraction_strategy: str,
    prompt_tokens: int,
    completion_tokens: int,
    cached_tokens: int,
    total_cost_usd: float,
    pages_extracted: int,
):
    """
    Append a row to a CSV file logging the extraction run for one PDF.
    Creates the file with header if not existing.
    """
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    file_exists = os.path.isfile(csv_path)

    with open(csv_path, mode="a", newline="", encoding="utf-8") as csvfile:
        fieldnames = [
            "timestamp",
            "pdf_id",
            "model",
            "extraction_strategy",
            "prompt_tokens",
            "completion_tokens",
            "cached_tokens",
            "total_cost_usd",
            "pages_extracted",
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        writer.writerow({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "pdf_id": pdf_id,
            "model": model,
            "extraction_strategy": extraction_strategy,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cached_tokens": cached_tokens,
            "total_cost_usd": round(total_cost_usd, 6),
            "pages_extracted": pages_extracted,
        })


def log_batch_summary(
    csv_path: str,
    batch_id: str,
    model: str,
    extraction_strategy: str,
    num_pdfs: int,
    prompt_tokens: int,
    completion_tokens: int,
    cached_tokens: int,
    total_cost_usd: float,
):
    """
    Append a row to a CSV file logging a batch extraction run.
    Creates the file with header if not existing.
    """
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    file_exists = os.path.isfile(csv_path)

    with open(csv_path, mode="a", newline="", encoding="utf-8") as csvfile:
        fieldnames = [
            "timestamp",
            "batch_id",
            "model",
            "extraction_strategy",
            "num_pdfs",
            "prompt_tokens",
            "completion_tokens",
            "cached_tokens",
            "total_cost_usd",
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        writer.writerow({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "batch_id": batch_id,
            "model": model,
            "extraction_strategy": extraction_strategy,
            "num_pdfs": num_pdfs,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cached_tokens": cached_tokens,
            "total_cost_usd": round(total_cost_usd, 6),
        })


def load_image_pdf_ids(path="data/image_pdf_ids.txt") -> set:
    """
    Loads a set of allowed PDF IDs from a text file.
    Used to filter the dataset for image-only PDF evaluations.
    """
    try:
        with open(path, encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    except FileNotFoundError:
        print(f"⚠️ Warning: image_pdf_ids.txt not found at {path}")
        return set()
