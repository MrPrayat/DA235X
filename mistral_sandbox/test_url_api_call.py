import os
from mistralai import Mistral
from utils.helpers import cost_usd

# Retrieve the API key from environment variables
api_key = os.environ["MISTRAL_API_KEY"]

# Specify model
model = "pixtral-12b-2409"

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
                "image_url": "https://tripfixers.com/wp-content/uploads/2019/11/eiffel-tower-with-snow.jpeg"
            }
        ]
    }
]

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

