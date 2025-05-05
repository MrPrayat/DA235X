import os
from google import genai
from google.genai import types

MODEL_NAME = "gemini-2.5-flash-preview-04-17"
gemini_api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=gemini_api_key)


with open(r"C:\Users\user\Pictures\studentkort - kopia.jpg", 'rb') as f:
    image_bytes = f.read()

response = client.models.generate_content(
model='gemini-2.0-flash',
contents=[
    types.Part.from_bytes(
    data=image_bytes,
    mime_type='image/jpeg',
    ),
    'Caption this image.'
]
)

print(response.text)