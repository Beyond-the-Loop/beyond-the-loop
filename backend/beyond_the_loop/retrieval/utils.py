import logging
from typing import Optional, Union

from openai import AzureOpenAI

from open_webui.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])


def get_embedding_function(
    embedding_engine,
    embedding_model,
    embedding_batch_size,
):
    if embedding_engine != "openai":
        raise ValueError(f"Unsupported embedding engine: {embedding_engine}")

    func = lambda query, user=None: generate_embeddings(
        model=embedding_model,
        text=query,
    )

    def generate_multiple(query, user, func):
        if isinstance(query, list):
            embeddings = []
            for i in range(0, len(query), embedding_batch_size):
                embeddings.extend(func(query[i : i + embedding_batch_size], user=user))
            return embeddings
        return func(query, user)

    return lambda query, user=None: generate_multiple(query, user, func)


def generate_openai_batch_embeddings(
    model: str,
    texts: list[str],
) -> Optional[list[list[float]]]:
    try:
        client = AzureOpenAI(api_version="2023-05-15")
        response = client.embeddings.create(input=texts, model=model)
        return [response.data[i].embedding for i in range(len(texts))]
    except Exception as e:
        log.exception(e)
        return None


def generate_embeddings(model: str, text: Union[str, list[str]]):
    if isinstance(text, list):
        embeddings = generate_openai_batch_embeddings(model, text)
    else:
        embeddings = generate_openai_batch_embeddings(model, [text])

    return embeddings[0] if isinstance(text, str) else embeddings
