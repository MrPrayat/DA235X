import os
from google import genai
from utils.helpers import cost_usd

model_name = "gemini-2.5-flash-preview-04-17"

gemini_api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=gemini_api_key)

response = client.models.generate_content(
    model="gemini-2.5-flash-preview-04-17",
    contents="Explain how AI works in a few words",
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
    model_name
    )

print("Assistant:", response.text)
print("Usage: ", usage)
print(f"Tokens — prompt: {prompt_tokens}, completion: {completion_tokens}")
print(f"Estimated cost: ${cost:.6f}")