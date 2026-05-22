"""
Centralized file deletion across DB, Google RAG Engine, and Cloud Storage.
"""

import logging

from beyond_the_loop.models.files import Files
from beyond_the_loop.retrieval.rag_engine import delete_google_rag_file_from_meta
from beyond_the_loop.storage.provider import Storage

log = logging.getLogger(__name__)


def delete_file_fully(file) -> None:
    """
    Delete a file from the database, Google RAG Engine, and cloud storage.

    DB is deleted first because it is the source of truth — once the DB row
    is gone, the user can no longer see or reference the file. Failures in
    RAG or storage cleanup leave harmless orphans (no live references) that
    can be reconciled by a background job later.

    Raises if DB deletion fails so callers can surface the error.
    Accepts FileModel (pydantic) or File (SQLAlchemy) — both expose .id, .meta, .path.
    """
    if file is None:
        return

    if not Files.delete_file_by_id(file.id):
        raise RuntimeError(f"Failed to delete file {file.id} from database")

    try:
        delete_google_rag_file_from_meta(file.meta)
    except Exception as e:
        log.warning(f"Could not delete file {file.id} from Google RAG Engine: {e}")

    if file.path:
        try:
            Storage.delete_file(file.path)
        except Exception as e:
            log.warning(f"Could not delete file {file.id} from storage: {e}")
