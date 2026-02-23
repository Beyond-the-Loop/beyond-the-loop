import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Union
from huggingface_hub import snapshot_download
from langchain_classic.retrievers import ContextualCompressionRetriever, EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from beyond_the_loop.retrieval.vector.connector import VECTOR_DB_CLIENT

from open_webui.env import (
    SRC_LOG_LEVELS,
    OFFLINE_MODE,
)

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])


from typing import Any

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.retrievers import BaseRetriever
from openai import AzureOpenAI


class VectorSearchRetriever(BaseRetriever):
    collection_name: Any
    query_embedding: Any  # pre-computed — no API call needed
    top_k: int

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> list[Document]:
        result = VECTOR_DB_CLIENT.search(
            collection_name=self.collection_name,
            vectors=[self.query_embedding],
            limit=self.top_k,
        )

        ids = result.ids[0]
        metadatas = result.metadatas[0]
        documents = result.documents[0]

        results = []
        for idx in range(len(ids)):
            results.append(
                Document(
                    metadata=metadatas[idx],
                    page_content=documents[idx],
                )
            )

        return results


def query_doc(
    collection_name: str, query_embedding: list[float], k: int
):
    try:
        result = VECTOR_DB_CLIENT.search(
            collection_name=collection_name,
            vectors=[query_embedding],
            limit=k,
        )
        return result
    except Exception as e:
        print(e)
        raise e


def query_doc_with_hybrid_search(
    collection_name: str,
    query: str,
    query_embedding,        # pre-computed query vector — used for vector search + reranking
    embedding_function,     # used only for document embeddings in RerankCompressor
    k: int,
    reranking_function,
    r: float,
) -> dict:
    try:
        t_start = time.perf_counter()

        # Step 1: Load ALL documents from collection for BM25
        result = VECTOR_DB_CLIENT.get(collection_name=collection_name)
        num_chunks = len(result.documents[0]) if result and result.documents else 0

        # Step 2: Build BM25 index from all loaded documents
        bm25_retriever = BM25Retriever.from_texts(
            texts=result.documents[0],
            metadatas=result.metadatas[0],
        )
        bm25_retriever.k = k

        # Step 3: Vector retriever — uses pre-computed query_embedding, no API call
        vector_search_retriever = VectorSearchRetriever(
            collection_name=collection_name,
            query_embedding=query_embedding,
            top_k=k,
        )

        ensemble_retriever = EnsembleRetriever(
            retrievers=[bm25_retriever, vector_search_retriever], weights=[0.5, 0.5]
        )
        compressor = RerankCompressor(
            embedding_function=embedding_function,  # for document embeddings
            query_embedding=query_embedding,         # pre-computed, no API call for query
            top_n=k,
            reranking_function=reranking_function,
            r_score=r,
        )

        compression_retriever = ContextualCompressionRetriever(
            base_compressor=compressor, base_retriever=ensemble_retriever
        )

        # Step 4: Run the full ensemble + rerank pipeline
        result = compression_retriever.invoke(query)

        t_end = time.perf_counter()

        result = {
            "distances": [[d.metadata.get("score") for d in result]],
            "documents": [[d.page_content for d in result]],
            "metadatas": [[d.metadata for d in result]],
        }
        return result
    except Exception as e:
        raise e


def merge_and_sort_query_results(
    query_results: list[dict], k: int, reverse: bool = False
) -> list[dict]:
    combined_distances = []
    combined_documents = []
    combined_metadatas = []

    for data in query_results:
        combined_distances.extend(data["distances"][0])
        combined_documents.extend(data["documents"][0])
        combined_metadatas.extend(data["metadatas"][0])

    combined = list(zip(combined_distances, combined_documents, combined_metadatas))
    combined.sort(key=lambda x: x[0], reverse=reverse)

    if not combined:
        sorted_distances = []
        sorted_documents = []
        sorted_metadatas = []
    else:
        sorted_distances, sorted_documents, sorted_metadatas = zip(*combined)
        sorted_distances = list(sorted_distances)[:k]
        sorted_documents = list(sorted_documents)[:k]
        sorted_metadatas = list(sorted_metadatas)[:k]

    return {
        "distances": [sorted_distances],
        "documents": [sorted_documents],
        "metadatas": [sorted_metadatas],
    }


def query_collection(
    collection_names: list[str],
    query_embeddings: list,  # one embedding per query
    k: int,
) -> dict:
    results = []
    for query_embedding in query_embeddings:
        for collection_name in collection_names:
            if collection_name:
                try:
                    result = query_doc(
                        collection_name=collection_name,
                        k=k,
                        query_embedding=query_embedding,
                    )
                    if result is not None:
                        results.append(result.model_dump())
                except Exception as e:
                    log.exception(f"Error when querying the collection: {e}")

    return merge_and_sort_query_results(results, k=k, reverse=True)


def query_collection_with_hybrid_search(
    collection_names: list[str],
    queries: list[str],
    query_embeddings: list,  # one embedding per query, same order as queries
    embedding_function,      # for document embeddings in RerankCompressor
    k: int,
    reranking_function,
    r: float,
) -> dict:
    results = []
    error = False
    for query, query_embedding in zip(queries, query_embeddings):
        for collection_name in collection_names:
            try:
                result = query_doc_with_hybrid_search(
                    collection_name=collection_name,
                    query=query,
                    query_embedding=query_embedding,
                    embedding_function=embedding_function,
                    k=k,
                    reranking_function=reranking_function,
                    r=r,
                )
                results.append(result)
            except Exception as e:
                log.exception(
                    "Error when querying the collection with " f"hybrid_search: {e}"
                )
                error = True

    if error:
        raise Exception(
            "Hybrid search failed for all collections. Using Non hybrid search as fallback."
        )

    return merge_and_sort_query_results(results, k=k, reverse=True)


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


def get_sources_from_files(
    files,
    queries,
    embedding_function,
    k,
    reranking_function,
    r,
    hybrid_search,
):
    # ── Phase 1: Build task list (sequential, determines deduplication) ──────
    extracted_collections = set()
    full_context_results = []   # (context_dict, file) — no search needed
    search_tasks = []           # (file, collection_names) — need vector/hybrid search

    for file in files:
        if file.get("context") == "full":
            context = {
                "documents": [[file.get("file", {}).get("data", {}).get("content")]],
                "metadatas": [[{"file_id": file.get("id"), "name": file.get("name")}]],
            }
            full_context_results.append((context, file))
        else:
            if file.get("type") == "text":
                search_tasks.append((file, None))
                continue

            collection_names = []
            if file.get("type") == "collection":
                if file.get("legacy"):
                    collection_names = file.get("collection_names", [])
                else:
                    collection_names.append(file["id"])
            elif file.get("collection_name"):
                collection_names.append(file["collection_name"])
            elif file.get("id"):
                if file.get("legacy"):
                    collection_names.append(f"{file['id']}")
                else:
                    collection_names.append(f"file-{file['id']}")

            collection_names = set(collection_names).difference(extracted_collections)
            if not collection_names:
                log.debug(f"skipping {file} as it has already been extracted")
                continue

            extracted_collections.update(collection_names)
            search_tasks.append((file, collection_names))

    # ── Phase 2: Batch-compute all query embeddings in one API call ───────────
    query_embeddings = embedding_function(queries) if queries else []

    # ── Phase 3: Execute searches in parallel ────────────────────────────────
    def search_one(file, collection_names):
        if collection_names is None:
            return file.get("content")

        if hybrid_search:
            try:
                return query_collection_with_hybrid_search(
                    collection_names=collection_names,
                    queries=queries,
                    query_embeddings=query_embeddings,
                    embedding_function=embedding_function,
                    k=k,
                    reranking_function=reranking_function,
                    r=r,
                )
            except Exception as e:
                log.debug("Hybrid search failed, falling back to vector-only search.")

        return query_collection(
            collection_names=collection_names,
            query_embeddings=query_embeddings,
            k=k,
        )

    max_workers = min(len(search_tasks), 10)
    ordered_results = [None] * len(search_tasks)

    if search_tasks:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {
                executor.submit(search_one, file, coll): i
                for i, (file, coll) in enumerate(search_tasks)
            }
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    ordered_results[idx] = future.result()
                except Exception as e:
                    log.exception(f"Search task {idx} failed: {e}")

    # ── Phase 4: Assemble results ─────────────────────────────────────────────
    relevant_contexts = []

    for context, file in full_context_results:
        if "data" in file:
            del file["data"]
        relevant_contexts.append({**context, "file": file})

    for i, (file, _) in enumerate(search_tasks):
        context = ordered_results[i]
        if context:
            if "data" in file:
                del file["data"]
            relevant_contexts.append({**context, "file": file})

    sources = []
    for context in relevant_contexts:
        try:
            if "documents" in context:
                if "metadatas" in context:
                    source = {
                        "source": context["file"],
                        "document": context["documents"][0],
                        "metadata": context["metadatas"][0],
                    }
                    if "distances" in context and context["distances"]:
                        source["distances"] = context["distances"][0]
                    sources.append(source)
        except Exception as e:
            log.exception(e)

    return sources


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
        client = AzureOpenAI(
            api_version="2023-05-15"
        )

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


import operator
from typing import Optional, Sequence

from langchain_core.callbacks import Callbacks
from langchain_core.documents import BaseDocumentCompressor, Document


class RerankCompressor(BaseDocumentCompressor):
    embedding_function: Any  # used only for document embeddings
    query_embedding: Any      # pre-computed query vector — no API call for the query
    top_n: int
    reranking_function: Any
    r_score: float

    class Config:
        extra = "forbid"
        arbitrary_types_allowed = True

    def compress_documents(
        self,
        documents: Sequence[Document],
        query: str,
        callbacks: Optional[Callbacks] = None,
    ) -> Sequence[Document]:
        reranking = self.reranking_function is not None

        if reranking:
            scores = self.reranking_function.predict(
                [(query, doc.page_content) for doc in documents]
            )
        else:
            from sentence_transformers import util

            document_embedding = self.embedding_function(
                [doc.page_content for doc in documents]
            )

            scores = util.cos_sim(self.query_embedding, document_embedding)[0]

        docs_with_scores = list(zip(documents, scores.tolist()))
        if self.r_score:
            docs_with_scores = [
                (d, s) for d, s in docs_with_scores if s >= self.r_score
            ]

        result = sorted(docs_with_scores, key=operator.itemgetter(1), reverse=True)
        final_results = []

        for doc, doc_score in result[: self.top_n]:
            metadata = doc.metadata
            metadata["score"] = doc_score
            doc = Document(
                page_content=doc.page_content,
                metadata=metadata,
            )
            final_results.append(doc)

        return final_results
