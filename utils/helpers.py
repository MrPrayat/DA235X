from openai import OpenAI, RateLimitError
import base64
import io
import time
import random
import requests
from pdf2image import convert_from_bytes
from PIL import Image
import json
from schema.schema import FIELDS, FIELD_DEFINITIONS
from openai import OpenAI, RateLimitError

# === GPT Helpers ===
client = OpenAI()

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


def is_appendix_page_gpt(image: Image.Image) -> bool:
    appendix_filter_prompt = (
        "You're reviewing a page from a Swedish housing inspection report. "
        "Your task is to determine whether this page is an *appendix* or *general conditions section*, typically found at the end of the document.\n\n"

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


    raw_response = call_openai_image_json(image, appendix_filter_prompt)
    return "yes" in raw_response.lower()


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
    def nullify(value):
        if isinstance(value, dict):
            return {k: None for k in value}
        return None

    return {
        field: nullify(model_output.get(field))
        for field in FIELDS
        if field != "SummaryInsights"  # Skip ground truth for SummaryInsights since we won't evaluate it
    }