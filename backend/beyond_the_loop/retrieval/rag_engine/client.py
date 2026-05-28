import logging
import os
import re
import time
from functools import lru_cache
from os.path import basename

from beyond_the_loop.models.files import Files

log = logging.getLogger(__name__)

_RAG_FILE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class GoogleRagEngineClient:
    def __init__(self):
        self.corpus = os.getenv("GOOGLE_RAG_CORPUS", "")
        self.project_id = (
            os.getenv("GOOGLE_RAG_PROJECT_ID", "")
            or self._project_from_corpus(self.corpus)
        )
        self.location = os.getenv("GOOGLE_RAG_LOCATION", "europe-west3")

        if not self.corpus:
            raise ValueError("GOOGLE_RAG_CORPUS is not configured")
        if not self.project_id:
            raise ValueError(
                "GOOGLE_RAG_PROJECT_ID is not configured and cannot be inferred"
            )
        if not self.location:
            raise ValueError("GOOGLE_RAG_LOCATION is not configured")

    def upload_file_to_corpus(self, local_path: str, display_name: str | None = None):
        t0 = time.perf_counter()
        rag = self._rag()
        log.info(
            "[UPLOAD_TIMING] step=rag_vertexai_init duration_ms=%.2f",
            (time.perf_counter() - t0) * 1000,
        )

        try:
            file_size = os.path.getsize(local_path)
        except OSError:
            file_size = -1

        t0 = time.perf_counter()
        rag_file = rag.upload_file(
            corpus_name=self.corpus,
            path=local_path,
            display_name=display_name or basename(local_path),
        )
        log.info(
            "[UPLOAD_TIMING] step=rag_upload_file_api duration_ms=%.2f bytes=%d rag_file=%s",
            (time.perf_counter() - t0) * 1000,
            file_size,
            getattr(rag_file, "name", "<unknown>"),
        )
        log.info("Google RAG file uploaded: %s", getattr(rag_file, "name", "<unknown>"))
        return rag_file

    def retrieve_contexts(self, query: str, rag_file_ids: list[str]) -> list[dict]:
        normalized_ids = normalize_rag_file_ids(rag_file_ids)
        if not normalized_ids:
            return []

        top_k = int(os.getenv("RAG_TOP_K", "10"))
        rag = self._rag()
        response = rag.retrieval_query(
            rag_resources=[
                rag.RagResource(
                    rag_corpus=self.corpus,
                    rag_file_ids=normalized_ids,
                )
            ],
            text=query,
            rag_retrieval_config=rag.RagRetrievalConfig(top_k=top_k),
        )

        return self._contexts_from_response(response)

    def delete_file(self, rag_file_name_or_id: str | None) -> None:
        if not rag_file_name_or_id:
            return

        rag = self._rag()
        try:
            rag.delete_file(
                name=rag_file_name_or_id,
                corpus_name=None if "/ragFiles/" in rag_file_name_or_id else self.corpus,
            )
        except Exception as e:
            if e.__class__.__name__ == "NotFound":
                log.info("Google RAG file already deleted: %s", rag_file_name_or_id)
                return
            raise

    def retrieve_sources(self, queries: list[str], rag_file_ids: list[str]) -> list[dict]:
        scoped_file_ids = normalize_rag_file_ids(rag_file_ids)
        top_k = int(os.getenv("RAG_TOP_K", "10"))
        log.info(
            "Google RAG retrieval with %d scoped file ids and top_k=%s",
            len(scoped_file_ids),
            top_k,
        )

        contexts = []

        for query in queries:
            contexts.extend(self.retrieve_contexts(query, scoped_file_ids))

        sources = []
        for context in contexts[:top_k]:
            source_uri = context.get("source_uri")
            source_name = basename(source_uri) if source_uri else "Google RAG"
            sources.append(
                {
                    "type": "rag",
                    "name": source_name,
                    "file_id": None,
                    "snippets": [context["text"]],
                    "scores": (
                        [context["score"]] if context.get("score") is not None else []
                    ),
                    "metadata": [
                        {
                            "source": source_name,
                            "source_uri": source_uri,
                        }
                    ],
                }
            )

        log.info("Google RAG retrieval returned %d sources", len(sources))
        return sources

    def _rag(self):
        import vertexai
        from vertexai import rag

        vertexai.init(project=self.project_id, location=self.location)
        return rag

    @staticmethod
    def _project_from_corpus(corpus: str | None) -> str | None:
        if not corpus or not corpus.startswith("projects/"):
            return os.environ.get("GOOGLE_CLOUD_PROJECT")
        return corpus.split("/", 2)[1]

    @staticmethod
    def _contexts_from_response(response) -> list[dict]:
        contexts_container = getattr(response, "contexts", None)
        raw_contexts = getattr(contexts_container, "contexts", []) or []
        contexts = []

        for context in raw_contexts:
            text = getattr(context, "text", None)
            if not text:
                continue

            score = getattr(context, "score", None)
            if score is None:
                score = getattr(context, "distance", None)

            contexts.append(
                {
                    "text": text,
                    "source_uri": getattr(context, "source_uri", None),
                    "score": score,
                }
            )

        return contexts


@lru_cache(maxsize=1)
def get_google_rag_client() -> GoogleRagEngineClient:
    return GoogleRagEngineClient()


def rag_file_to_file_meta(rag_file, corpus: str, gcs_uri: str | None = None) -> dict:
    rag_file_name = getattr(rag_file, "name", "")
    source_uri = getattr(rag_file, "source_uri", None)

    return {
        "rag_provider": "google",
        "rag_corpus": corpus,
        "rag_file_id": rag_file_name.rsplit("/ragFiles/", 1)[-1],
        "rag_file_name": rag_file_name,
        "rag_gcs_uri": gcs_uri or source_uri,
        "rag_import_status": "imported",
    }


def get_sources_from_google_rag(files, queries):
    rag_file_ids = _extract_google_rag_file_ids(files)
    if not rag_file_ids:
        log.info("Google RAG skipped: no scoped rag_file_ids found")
        return []

    info_by_gcs_uri = _build_file_info_by_gcs_uri(files)

    client = get_google_rag_client()
    sources = client.retrieve_sources(queries=queries, rag_file_ids=rag_file_ids)

    for source in sources:
        metadata_list = source.get("metadata") or []
        source_uri = metadata_list[0].get("source_uri") if metadata_list else None
        info = info_by_gcs_uri.get(source_uri) if source_uri else None
        if info:
            if info.get("name"):
                source["name"] = info["name"]
            if info.get("file_id"):
                source["file_id"] = info["file_id"]
            for meta in metadata_list:
                if info.get("name"):
                    meta["source"] = info["name"]
                if info.get("file_id"):
                    meta["file_id"] = info["file_id"]

    return sources


def _build_file_info_by_gcs_uri(files) -> dict:
    mapping = {}

    for file in files:
        meta = file.get("meta") or {}
        rag_gcs_uri = meta.get("rag_gcs_uri")
        original_name = meta.get("name") or file.get("name")
        file_id = _extract_db_file_id(file)

        if not rag_gcs_uri or not original_name:
            file_record = Files.get_file_by_id(file_id) if file_id else None
            if file_record:
                file_meta = file_record.meta or {}
                rag_gcs_uri = rag_gcs_uri or file_meta.get("rag_gcs_uri")
                original_name = (
                    original_name
                    or file_meta.get("name")
                    or file_record.filename
                )

        if rag_gcs_uri:
            info = {"name": original_name, "file_id": file_id}
            mapping[rag_gcs_uri] = info
            # rag.upload_file() returns the display_name as source_uri, which we
            # set to the GCS basename (UUID-prefixed filename) for uniqueness.
            mapping[basename(rag_gcs_uri)] = info

    return mapping


def delete_google_rag_file_from_meta(meta: dict | None) -> None:
    if not meta:
        return

    rag_file_name = meta.get("rag_file_name") or meta.get("rag_file_id")
    if not rag_file_name:
        return

    get_google_rag_client().delete_file(rag_file_name)


def normalize_rag_file_ids(values: list[str]) -> list[str]:
    normalized = []
    seen = set()

    for value in values:
        rag_file_id = _normalize_rag_file_id(value)
        if rag_file_id not in seen:
            normalized.append(rag_file_id)
            seen.add(rag_file_id)

    return normalized


def _normalize_rag_file_id(value: str) -> str:
    if not value:
        raise ValueError("RAG file ID is empty")

    rag_file_id = value.rsplit("/ragFiles/", 1)[-1].strip()
    if not _RAG_FILE_ID_PATTERN.match(rag_file_id):
        raise ValueError(f"Invalid RAG file ID: {value}")

    return rag_file_id


def _extract_google_rag_file_ids(files) -> list[str]:
    rag_file_ids = []

    for file in files:
        meta = file.get("meta") or {}
        rag_file_id = meta.get("rag_file_id") or meta.get("rag_file_name")

        if not rag_file_id:
            file_id = _extract_db_file_id(file)
            file_record = Files.get_file_by_id(file_id) if file_id else None
            file_meta = file_record.meta if file_record else {}
            rag_file_id = (file_meta or {}).get("rag_file_id") or (
                file_meta or {}
            ).get("rag_file_name")

        if rag_file_id:
            rag_file_ids.append(rag_file_id)

    return rag_file_ids


def _extract_db_file_id(file: dict) -> str | None:
    file_id = file.get("id")
    if not file_id:
        return None

    if file.get("type") == "collection" and file_id.startswith("file-"):
        return file_id.removeprefix("file-")

    return file_id
