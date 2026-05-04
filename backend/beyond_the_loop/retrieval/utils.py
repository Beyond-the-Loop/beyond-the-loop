import logging
import os
from typing import Optional, Union

from huggingface_hub import snapshot_download
from openai import AzureOpenAI

from open_webui.env import OFFLINE_MODE, SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])


def get_embedding_function(
    embedding_engine,
    embedding_model,
    embedding_function,
    embedding_batch_size,
):
    if embedding_engine == "":
        return lambda query, user=None: embedding_function.encode(query).tolist()
    elif embedding_engine == "openai":
        func = lambda query, user=None: generate_embeddings(
            model=embedding_model,
            text=query,
        )

        def generate_multiple(query, user, func):
            if isinstance(query, list):
                embeddings = []
                for i in range(0, len(query), embedding_batch_size):
                    embeddings.extend(
                        func(query[i : i + embedding_batch_size], user=user)
                    )
                return embeddings
            else:
                return func(query, user)

        return lambda query, user=None: generate_multiple(query, user, func)
    else:
        raise ValueError(f"Unknown embedding engine: {embedding_engine}")


def get_model_path(model: str, update_model: bool = False):
    cache_dir = os.getenv("SENTENCE_TRANSFORMERS_HOME")
    local_files_only = not update_model

    if OFFLINE_MODE:
        local_files_only = True

    snapshot_kwargs = {
        "cache_dir": cache_dir,
        "local_files_only": local_files_only,
    }

    log.debug(f"model: {model}")
    log.debug(f"snapshot_kwargs: {snapshot_kwargs}")

    if (
        os.path.exists(model)
        or ("\\" in model or model.count("/") > 1)
        and local_files_only
    ):
        return model
    elif "/" not in model:
        model = "sentence-transformers" + "/" + model

    snapshot_kwargs["repo_id"] = model

    try:
        model_repo_path = snapshot_download(**snapshot_kwargs)
        log.debug(f"model_repo_path: {model_repo_path}")
        return model_repo_path
    except Exception as e:
        log.exception(f"Cannot determine model snapshot path: {e}")
        return model


def generate_openai_batch_embeddings(
    model: str,
    texts: list[str],
) -> Optional[list[list[float]]]:
    try:
        client = AzureOpenAI(api_version="2023-05-15")

        response = client.embeddings.create(
            input=texts,
            model=model,
        )

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
