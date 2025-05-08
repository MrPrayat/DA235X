import os
from mistralai import Mistral
from utils.helpers import cost_usd

api_key = os.environ["MISTRAL_API_KEY"]
model = "mistral-medium-2505"

client = Mistral(api_key=api_key)

chat_response = client.chat.complete(
    model= model,
    messages = [
        {
            "role": "user",
            "content": "What is the best Persian dish?",
        },
    ]
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
#print(chat_response.choices[0].message.content)