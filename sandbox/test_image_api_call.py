import os
from google import genai
from google.genai import types
from utils.helpers import cost_usd
import httpx

MODEL_NAME = "gemini-2.5-flash-preview-04-17"
PROMPT = "What is the cadastral designation of this property? And what is the biggest risk for me" \
          " as a potential buyer of this property in terms of unexpected renovation needs in the coming 3 years?"


gemini_api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=gemini_api_key)
doc_url = "https://documents.bcdn.se/a9/01/5803e049a3c6/.pdf"

# Retrieve and encode the PDF byte
doc_data = httpx.get(doc_url).content

response = client.models.generate_content(
    model=MODEL_NAME,
    contents=[
        types.Part.from_bytes(
            data=doc_data,
            mime_type="application/pdf",
        ),
        PROMPT
    ],
    config=genai.types.GenerateContentConfig(
    thinking_config=genai.types.ThinkingConfig(
        thinking_budget=1024
    )
  )
)

usage = response.usage_metadata
prompt_tokens     = usage.prompt_token_count or 0
completion_tokens = usage.candidates_token_count or 0

cost = cost_usd(
    {
        "prompt": prompt_tokens,
        "completion": completion_tokens,
        "cached": 0
    },
    MODEL_NAME
    )

print("Usage: ", usage)
print("\n\n")
print("Assistant:", response.text)
print(f"Tokens — prompt: {prompt_tokens}, completion: {completion_tokens}")
print(f"Estimated cost: ${cost:.6f}")