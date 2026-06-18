import argparse
import logging
import sys

# Import all model modules so SQLAlchemy can resolve cross-module relationships
# (e.g. Company.domains -> Domain) before the first query runs.
import beyond_the_loop.models.alert  # noqa: F401
import beyond_the_loop.models.analytics  # noqa: F401
import beyond_the_loop.models.auths  # noqa: F401
import beyond_the_loop.models.chats  # noqa: F401
import beyond_the_loop.models.companies  # noqa: F401
import beyond_the_loop.models.completions  # noqa: F401
import beyond_the_loop.models.domains  # noqa: F401
import beyond_the_loop.models.files  # noqa: F401
import beyond_the_loop.models.folders  # noqa: F401
import beyond_the_loop.models.groups  # noqa: F401
import beyond_the_loop.models.knowledge  # noqa: F401
import beyond_the_loop.models.models  # noqa: F401
import beyond_the_loop.models.prompts  # noqa: F401
import beyond_the_loop.models.users  # noqa: F401

from beyond_the_loop.services.file_service import file_service

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def _print_stats(company_id: str | None) -> None:
    stats = file_service.get_cleanup_stats(company_id)
    scope = f"company={company_id}" if company_id else "global"
    log.info(
        "stats (%s): total=%s old=%s protected=%s deletable=%s cutoff=%s threshold_days=%s",
        scope,
        stats["total_files"],
        stats["old_files"],
        stats["protected_files"],
        stats["deletable_files"],
        stats["cutoff_date"],
        stats["threshold_days"],
    )


def _print_preview(company_id: str | None) -> None:
    preview = file_service.preview_cleanup_candidates(company_id)
    log.info(
        "preview (%s): total_old=%s protected=%s deletable=%s",
        company_id or "global",
        preview["total_old_files"],
        preview["protected_count"],
        preview["candidates_count"],
    )
    for c in preview["candidates"]:
        log.info(
            "  candidate id=%s filename=%s days_old=%s path=%s",
            c["file_id"],
            c["filename"],
            c["days_old"],
            c["path"],
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Trigger the file cleanup that deletes files older than "
            f"{file_service.DELETION_THRESHOLD_DAYS} days (protected files in "
            "knowledge bases / assistants are skipped). Deletes DB row, Google "
            "RAG entry, and GCS blob."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print stats and preview candidates; do not delete anything.",
    )
    parser.add_argument(
        "--company-id",
        default=None,
        help="Scope stats/preview to a single company. NOTE: the actual cleanup "
             "always runs globally — the underlying service has no per-company mode.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the interactive confirmation prompt before running the real cleanup.",
    )
    args = parser.parse_args()

    _print_stats(args.company_id)
    _print_preview(args.company_id)

    if args.dry_run:
        log.info("dry-run: no files deleted")
        return 0

    if not args.yes:
        answer = input(
            "This will permanently delete the deletable files above (GLOBAL). "
            "Type 'yes' to proceed: "
        ).strip().lower()
        if answer != "yes":
            log.info("aborted by user")
            return 1

    result = file_service.run_daily_file_cleanup()
    log.info("cleanup result: %s", result)
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
