from openai import OpenAI
import logging

from openai.types.chat import ChatCompletionUserMessageParam
from openai.types.shared_params import ResponseFormatJSONSchema

# logging.basicConfig(level=logging.DEBUG)

client = OpenAI(
    api_key="sk-e549954e642b403493ece2cf91597d02",
    base_url="http://localhost:8080/api/openai"
)

schema = {
    "name": "classification_result",
    "schema": {
        "type": "object",
        "properties": {
            "color": {
                "type": "string",
                "enum": ["red", "green"]
            }
        },
        "required": ["color"]
    }
}

response = client.chat.completions.create(
    model="GPT-5 mini",
    messages=[
        ChatCompletionUserMessageParam(
            role="user",
            content="Hello, how are you? Choose a color between red and green randomly"
        )
    ],
    response_format=ResponseFormatJSONSchema(
        type="json_schema",
        json_schema=schema
    )
)

print(response)