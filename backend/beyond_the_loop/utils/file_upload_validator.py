import logging
import time

import magic
from pathlib import Path
from fastapi import HTTPException, UploadFile, status
from beyond_the_loop.config import UPLOAD_FILE_MAX_SIZE

log = logging.getLogger(__name__)

# Maps extension -> set of allowed MIME types (detected from file content)
EXTENSION_MIME_MAP: dict[str, set[str]] = {
    # Documents
    "pdf":  {"application/pdf"},
    "doc":  {"application/msword"},
    "docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/zip", "application/octet-stream"},
    "xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/zip", "application/octet-stream"},
    "pptx": {"application/vnd.openxmlformats-officedocument.presentationml.presentation", "application/zip", "application/octet-stream"},
    "tex":  {"text/x-tex", "text/plain"},

    # Text / Code (python-magic gibt hier meist "text/plain" zurück)
    "txt":  {"text/plain"},
    "md":   {"text/plain", "text/markdown"},
    "csv":  {"text/plain", "text/csv"},
    "json": {"text/plain", "application/json"},
    "xml":  {"text/plain", "text/xml", "application/xml"},
    "html": {"text/html", "text/plain"},
    "css":  {"text/plain", "text/css"},
    "js":   {"text/plain", "application/javascript"},
    "ts":   {"text/plain", "application/typescript"},
    "py":   {"text/plain", "text/x-python", "text/x-script.python"},
    "rb":   {"text/plain", "text/x-ruby"},
    "php":  {"text/plain", "text/x-php"},
    "java": {"text/plain", "text/x-java", "text/x-java-source", "text/x-c"},
    "c":    {"text/plain", "text/x-c", "text/x-csrc"},
    "cpp":  {"text/plain", "text/x-c", "text/x-c++", "text/x-c++src"},
    "go":   {"text/plain", "text/x-go"},
    "sql":  {"text/plain"},

    # Images
    "jpg":  {"image/jpeg"},
    "jpeg": {"image/jpeg"},
    "png":  {"image/png"},
    "gif":  {"image/gif"},
    "webp": {"image/webp"},

    # Audio
    "mp3":  {"audio/mpeg"},
    "wav":  {"audio/x-wav", "audio/wav"},
    "ogg":  {"audio/ogg", "application/ogg"},
    "m4a":  {"audio/mp4", "video/mp4"},  # m4a wird oft als mp4-Container erkannt

    # Data / Other
    "pkl":  {"application/octet-stream"},  # Pickle: bewusst restriktiv, niemals deserialisieren ohne Prüfung
}

SUPPORTED_FILE_EXTENSIONS: set[str] = set(EXTENSION_MIME_MAP.keys())

MAX_FILE_SIZE_BYTES = UPLOAD_FILE_MAX_SIZE * 1024 * 1024


class FileValidator:
    READ_HEAD_BYTES = 8192

    @staticmethod
    def validate_upload(file: UploadFile) -> None:
        """
        Two-layer validation:
        1. Extension against SUPPORTED_FILE_EXTENSIONS allowlist
        2. Detected MIME type (from file content) against allowed MIMEs per extension
        """

        # --- Layer 0: Size check ---
        t0 = time.perf_counter()
        head = file.file.read(MAX_FILE_SIZE_BYTES + 1)  # 1 Byte mehr als Limit lesen
        log.info(
            "[UPLOAD_TIMING] step=validate_size_read duration_ms=%.2f bytes_read=%d",
            (time.perf_counter() - t0) * 1000,
            len(head),
        )
        if len(head) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Hochgeladene Datei ist größer als die maximale Dateigröße von 25 MB",
            )
        file.file.seek(0)  # Pointer zurücksetzen

        # --- Layer 1: Extension check ---
        ext = Path(file.filename or "").suffix.lstrip(".").lower()

        if not ext or ext not in SUPPORTED_FILE_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Nicht unterstützter Dateityp: '.{ext}'",
            )

        # --- Layer 2: MIME sniffing ---
        t0 = time.perf_counter()
        head = file.file.read(FileValidator.READ_HEAD_BYTES)
        file.file.seek(0)  # Pointer zurücksetzen für nachfolgende Verarbeitung

        detected_mime: str = magic.from_buffer(head, mime=True) or ""
        log.info(
            "[UPLOAD_TIMING] step=validate_mime_sniff duration_ms=%.2f detected_mime=%s ext=%s",
            (time.perf_counter() - t0) * 1000,
            detected_mime,
            ext,
        )
        allowed_mimes: set[str] = EXTENSION_MIME_MAP[ext]

        print("DETECTED", detected_mime)

        if detected_mime not in allowed_mimes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Ups! Der Inhalt der hochgeladenen Datei passt nicht zur Dateiendung '.{ext}'. "
                    f"Bitte überprüfe das Dateiformat."
                ),
            )