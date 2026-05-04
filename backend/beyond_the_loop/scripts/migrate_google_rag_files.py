import argparse
import logging
import sys

from beyond_the_loop.models.files import Files
from beyond_the_loop.retrieval.rag_engine import GoogleRagEngineClient

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate existing file table rows into Google Cloud RAG Engine."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned imports without updating file.meta.",
    )
    parser.add_argument(
        "--file-id",
        action="append",
        default=[],
        help="Only migrate this file ID. Can be passed multiple times.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum number of files to inspect. 0 means no limit.",
    )
    args = parser.parse_args()

    client = GoogleRagEngineClient()
    files = (
        [Files.get_file_by_id(file_id) for file_id in args.file_id]
        if args.file_id
        else Files.get_files()
    )
    files = [file for file in files if file]
    if args.limit:
        files = files[: args.limit]

    inspected = 0
    migrated = 0
    skipped = 0
    failed = 0

    for file in files:
        inspected += 1
        meta = file.meta or {}

        if meta.get("rag_file_id"):
            skipped += 1
            log.info("skip already migrated: %s (%s)", file.filename, file.id)
            continue

        if not file.path or not file.path.startswith("gs://"):
            skipped += 1
            log.warning("skip non-GCS file: %s (%s) path=%s", file.filename, file.id, file.path)
            continue

        if args.dry_run:
            migrated += 1
            log.info("dry-run import: %s (%s) %s", file.filename, file.id, file.path)
            continue

        try:
            rag_file = client.import_gcs_file(file.path)
            Files.update_file_metadata_by_id(
                file.id,
                rag_file.to_file_meta(corpus=client.corpus, gcs_uri=file.path),
            )
            migrated += 1
            log.info("migrated: %s (%s) -> %s", file.filename, file.id, rag_file.name)
        except Exception as e:
            failed += 1
            log.exception("failed: %s (%s)", file.filename, file.id)
            Files.update_file_metadata_by_id(
                file.id,
                {
                    "rag_provider": "google",
                    "rag_gcs_uri": file.path,
                    "rag_import_status": "failed",
                    "rag_import_error": str(e),
                },
            )

    log.info(
        "done inspected=%s migrated=%s skipped=%s failed=%s dry_run=%s",
        inspected,
        migrated,
        skipped,
        failed,
        args.dry_run,
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
