from openai import OpenAI
client = OpenAI()

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "What's in this image?"},
            {
                "type": "image_url",
                "image_url": {
                    "url": "https://i.chzbgr.com/full/9357200640/h8A83F472/want-one-thing-and-its-fucking-disgusting-2017-10-22-156-am-windfury-totem-iii-larsens-creation",
                },
            },
        ],
    }],
)

print(response.choices[0].message.content)