import os
from openai import OpenAI, RateLimitError

client = OpenAI()

response = client.chat.completions.create(
    model="gpt-4o",          # or "gpt-4o" if you have access
    messages=[{"role": "user", "content": "Hej! svara med ett ord."}],
)

print("Assistant:", response.choices[0].message.content)
print("Usage:", response.usage)