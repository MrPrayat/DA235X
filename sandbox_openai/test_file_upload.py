from openai import OpenAI
from pathlib import Path
from utils.helpers import cost_usd

client = OpenAI()

# Upload PDF
upload = client.files.create(
    file=Path("PR-IndividualPlan.pdf"),
    purpose="user_data"
)

# Query
response = client.responses.create(
    model="gpt-4.1",
    input=[{
        "role": "user",
        "content": [
            {"type": "input_file", "file_id": upload.id},
            {"type": "input_text", "text": "What is this document about??"},
        ]
    }]
)

usage = response.usage
print("Usage:", usage)
print(f"Prompt tokens: {usage.input_tokens}")
print(f"Cached tokens: {usage.input_tokens_details.cached_tokens}")
print(f"Output tokens: {usage.output_tokens}")
print(f"Total tokens: {usage.total_tokens}")

# —— new cost calculation —— 
tokens = {
    "prompt":     usage.input_tokens,
    "completion": usage.output_tokens,
    "cached":     usage.input_tokens_details.cached_tokens,
}
cost = cost_usd(tokens, model="gpt-4.1")
print(f"Estimated cost: ${cost:.4f}")

print(response.output_text)
