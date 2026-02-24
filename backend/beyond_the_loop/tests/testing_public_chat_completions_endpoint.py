from openai import OpenAI
import logging

from openai.types.chat import ChatCompletionUserMessageParam
from openai.types.shared_params import ResponseFormatJSONSchema

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

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

structured_output_response = client.chat.completions.create(
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

log.info(f"Structured output response: {structured_output_response}")

file_rag_response = client.chat.completions.create(
    model="GPT-5 mini",
    messages=[
        ChatCompletionUserMessageParam(
            role="user",
            content="Fasse das Dokument für mich zusammen"
        )
    ],
    metadata={
        "file_id": "b8cec44d-7e6f-48c6-8214-f42ec8024a0c"
    }
)

log.info(f"File RAG response: {file_rag_response}")