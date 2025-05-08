import base64
import requests
import os
from mistralai import Mistral
from utils.helpers import cost_usd

def encode_image(image_path):
    """Encode the image to base64."""
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except FileNotFoundError:
        print(f"Error: The file {image_path} was not found.")
        return None
    except Exception as e:  # Added general exception handling
        print(f"Error: {e}")
        return None

# Path to your image
image_path = "C:\\Users\\user\\Pictures\\dadandi.jpg"

# Getting the base64 string
base64_image = encode_image(image_path)

# Retrieve the API key from environment variables
api_key = os.environ["MISTRAL_API_KEY"]

# Specify model
model = "mistral-medium-2505"

# Initialize the Mistral client
client = Mistral(api_key=api_key)

# Define the messages for the chat
messages = [
    {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": "What's in this image?"
            },
            {
                "type": "image_url",
                "image_url": f"data:image/jpeg;base64,{base64_image}" 
            }
        ]
    }
]

# Get the chat response
chat_response = client.chat.complete(
    model=model,
    messages=messages
)

print("chat_response.usage.prompt_tokens: ", chat_response.usage.prompt_tokens)
print("chat_response.usage.completion_tokens: ", chat_response.usage.completion_tokens)
print("chat_response.usage.total_tokens: ", chat_response.usage.total_tokens)

token_cost = {
    "prompt": chat_response.usage.prompt_tokens,
    "cached": 0,
    "completion": chat_response.usage.completion_tokens,
}
print("token_cost: $", cost_usd(token_cost, model))

# Print the content of the response
print(chat_response.choices[0].message.content)