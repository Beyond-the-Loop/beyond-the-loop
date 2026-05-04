import logging
import os
import re
import time
from dataclasses import dataclass
from os.path import basename

from beyond_the_loop.models.files import Files

log = logging.getLogger(__name__)

_RAG_FILE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
_IMPORT_POLL_INTERVAL_SECONDS = 2
_IMPORT_POLL_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class RagEngineFile:
    name: str
    display_name: str | None = None
    source_uri: str | None = None

    @property
    def file_id(self) -> str:
        return self.name.rsplit("/ragFiles/", 1)[-1]

    def to_file_meta(self, corpus: str, gcs_uri: str | None = None) -> dict:
        return {
            "rag_provider": "google",
            "rag_corpus": corpus,
            "rag_file_id": self.file_id,
            "rag_file_name": self.name,
            "rag_gcs_uri": gcs_uri or self.source_uri,
            "rag_import_status": "imported",
        }


@dataclass(frozen=True)
class RagEngineContext:
    text: str
    source_uri: str | None = None
    score: float | None = None

    @property
    def source_name(self) -> str:
        if self.source_uri:
            return basename(self.source_uri)
        return "Google RAG"


class GoogleRagEngineClient:
    def __init__(
        self,
        corpus: str | None = None,
        project_id: str | None = None,
        location: str | None = None,
    ):
        self.corpus = corpus or _config_value("GOOGLE_RAG_CORPUS", "")
        self.project_id = (
            project_id
            or _config_value("GOOGLE_RAG_PROJECT_ID", "")
            or self._project_from_corpus(self.corpus)
        )
        self.location = location or _config_value("GOOGLE_RAG_LOCATION", "europe-west3")

        if not self.corpus:
            raise ValueError("GOOGLE_RAG_CORPUS is not configured")
        if not self.project_id:
            raise ValueError(
                "GOOGLE_RAG_PROJECT_ID is not configured and cannot be inferred"
            )
        if not self.location:
            raise ValueError("GOOGLE_RAG_LOCATION is not configured")

    def import_gcs_file(
        self,
        gcs_uri: str,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        max_embedding_requests_per_min: int | None = None,
    ) -> RagEngineFile:
        if not gcs_uri.startswith("gs://"):
            raise ValueError("Google RAG import expects a gs:// URI")

        existing_file = self.find_file_by_gcs_uri(gcs_uri)
        if existing_file:
            log.info("Google RAG file already imported: %s", existing_file.name)
            return existing_file

        rag = self._rag()
        response = rag.import_files(
            corpus_name=self.corpus,
            paths=[gcs_uri],
            transformation_config=rag.TransformationConfig(
                rag.ChunkingConfig(
                    chunk_size=chunk_size
                    or int(_config_value("GOOGLE_RAG_IMPORT_CHUNK_SIZE", "1024")),
                    chunk_overlap=chunk_overlap
                    or int(_config_value("GOOGLE_RAG_IMPORT_CHUNK_OVERLAP", "256")),
                )
            ),
            max_embedding_requests_per_min=(
                max_embedding_requests_per_min
                or int(
                    _config_value("GOOGLE_RAG_MAX_EMBEDDING_REQUESTS_PER_MIN", "1000")
                )
            ),
        )
        log.info("Google RAG import response: %s", response)

        rag_file = self._wait_for_file(gcs_uri)
        if not rag_file:
            raise RuntimeError(f"Imported file not found in RAG corpus: {gcs_uri}")

        return rag_file

    def list_files(self) -> list[RagEngineFile]:
        rag = self._rag()
        files = []

        for file in rag.list_files(corpus_name=self.corpus):
            files.append(
                RagEngineFile(
                    name=getattr(file, "name", ""),
                    display_name=getattr(file, "display_name", None),
                    source_uri=getattr(file, "source_uri", None),
                )
            )

        return files

    def find_file_by_gcs_uri(self, gcs_uri: str) -> RagEngineFile | None:
        gcs_basename = basename(gcs_uri)
        display_name_matches = []

        for rag_file in self.list_files():
            if rag_file.source_uri == gcs_uri:
                return rag_file
            if rag_file.display_name == gcs_basename:
                display_name_matches.append(rag_file)

        if len(display_name_matches) == 1:
            return display_name_matches[0]
        if len(display_name_matches) > 1:
            log.warning(
                "Google RAG file lookup by display name is ambiguous for %s",
                gcs_uri,
            )

        return None

    def _wait_for_file(self, gcs_uri: str) -> RagEngineFile | None:
        deadline = time.monotonic() + _IMPORT_POLL_TIMEOUT_SECONDS

        while time.monotonic() <= deadline:
            rag_file = self.find_file_by_gcs_uri(gcs_uri)
            if rag_file:
                return rag_file
            time.sleep(_IMPORT_POLL_INTERVAL_SECONDS)

        return None

    def retrieve_contexts(
        self,
        query: str,
        rag_file_ids: list[str],
        top_k: int = 10,
    ) -> list[RagEngineContext]:
        normalized_ids = normalize_rag_file_ids(rag_file_ids)
        if not normalized_ids:
            return []

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

    def retrieve_sources(
        self,
        queries: list[str],
        rag_file_ids: list[str],
        top_k: int = 10,
    ) -> list[dict]:
        scoped_file_ids = normalize_rag_file_ids(rag_file_ids)
        log.info(
            "Google RAG retrieval with %d scoped file ids and top_k=%s",
            len(scoped_file_ids),
            top_k,
        )

        contexts = []

        for query in queries:
            contexts.extend(self.retrieve_contexts(query, scoped_file_ids, top_k=top_k))

        sources = []
        for context in contexts[:top_k]:
            sources.append(
                {
                    "source": {"name": context.source_name},
                    "document": [context.text],
                    "metadata": [
                        {
                            "source": context.source_name,
                            "source_uri": context.source_uri,
                        }
                    ],
                    "distances": [context.score] if context.score is not None else [],
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
    def _contexts_from_response(response) -> list[RagEngineContext]:
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
                RagEngineContext(
                    text=text,
                    source_uri=getattr(context, "source_uri", None),
                    score=score,
                )
            )

        return contexts


def _config_value(name: str, default: str) -> str:
    try:
        from beyond_the_loop import config

        value = getattr(config, name).value
        return str(value) if value is not None else default
    except Exception:
        return os.environ.get(name, default)


def get_sources_from_google_rag(files, queries, k):
    rag_file_ids = _extract_google_rag_file_ids(files)
    if not rag_file_ids:
        log.info("Google RAG skipped: no scoped rag_file_ids found")
        return []

    client = GoogleRagEngineClient()
    return client.retrieve_sources(queries=queries, rag_file_ids=rag_file_ids, top_k=k)


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
