"""
File conversion for Google RAG Engine compatibility.

Google RAG Engine only supports a limited set of file types. This module
converts non-supported types (mostly source code, tabular data, legacy
Office formats) into RAG-supported formats before upload.

Conversions:
- Source code / config (c, cpp, css, go, java, js, php, py, rb, ts, tex, xml)
  -> .txt (passthrough, content is already text)
- CSV / XLSX -> .json (one record per row)
- DOC (legacy Word) -> .docx (via pypandoc)
"""
import io
import logging
import os
import tempfile
from pathlib import Path
from typing import Tuple

from fastapi import HTTPException, status

log = logging.getLogger(__name__)


# Source code and config files: extension rename only — content is already text.
TEXT_TO_TXT_EXTENSIONS: set[str] = {
    "c", "cpp", "css", "go", "java", "js", "php",
    "pkl", "py", "rb", "ts", "tex", "xml",
}

# Tabular data formats: parsed with pandas and serialized as JSON records.
TABULAR_TO_JSON_EXTENSIONS: set[str] = {"csv", "xlsx"}

# Legacy Office formats converted to modern equivalents via pypandoc.
LEGACY_OFFICE_CONVERSIONS: dict[str, str] = {"doc": "docx"}

# Extensions Google RAG already accepts natively — passthrough.
RAG_NATIVE_EXTENSIONS: set[str] = {
    "pdf", "docx", "pptx", "html", "json", "jsonl", "md", "txt",
}


def convert_for_rag(content: bytes, filename: str) -> Tuple[bytes, str]:
    """
    Convert a file into a Google RAG-supported format.

    Returns (converted_content, new_filename). Falls back to passthrough for
    types we don't handle here (validator already gates input).
    """
    ext = _extract_extension(filename)

    if ext in RAG_NATIVE_EXTENSIONS:
        return content, filename

    if ext in TEXT_TO_TXT_EXTENSIONS:
        return content, _rewrite_extension(filename, "txt")

    if ext in TABULAR_TO_JSON_EXTENSIONS:
        return _convert_tabular_to_json(content, filename, ext)

    if ext in LEGACY_OFFICE_CONVERSIONS:
        target_ext = LEGACY_OFFICE_CONVERSIONS[ext]
        return _convert_legacy_office(content, filename, ext, target_ext)

    return content, filename


def _convert_tabular_to_json(
    content: bytes, filename: str, ext: str
) -> Tuple[bytes, str]:
    """Read CSV/XLSX with pandas and emit a JSON array of row records."""
    import pandas as pd

    buf = io.BytesIO(content)
    try:
        if ext == "csv":
            df = pd.read_csv(buf)
        else:  # xlsx
            df = pd.read_excel(buf)
    except Exception as exc:
        log.warning("Failed to parse %s: %s", filename, exc)
        detail = (
            "The CSV file could not be read — it may be corrupted or have an unexpected format."
            if ext == "csv"
            else "The Excel file could not be read — it may be corrupted or have an unexpected format."
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )

    json_str = df.to_json(orient="records", force_ascii=False)
    new_filename = _rewrite_extension(filename, "json")
    log.info(
        "File conversion: %s -> %s (%d rows, tabular to JSON)",
        filename,
        new_filename,
        len(df),
    )
    return json_str.encode("utf-8"), new_filename


def _convert_legacy_office(
    content: bytes, filename: str, source_ext: str, target_ext: str
) -> Tuple[bytes, str]:
    """Convert legacy Office docs (.doc) to a modern format (.docx) via pypandoc."""
    import pypandoc

    with tempfile.NamedTemporaryFile(suffix=f".{source_ext}", delete=False) as src:
        src.write(content)
        src_path = src.name

    target_path = src_path.replace(f".{source_ext}", f".{target_ext}")
    try:
        try:
            pypandoc.convert_file(src_path, target_ext, outputfile=target_path)
        except Exception as exc:
            log.warning("pypandoc failed for %s: %s", filename, exc)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"The .{source_ext} file could not be converted to .{target_ext}. "
                    f"Please check the file or upload it as .{target_ext}."
                ),
            )
        with open(target_path, "rb") as f:
            converted = f.read()
    finally:
        for path in (src_path, target_path):
            try:
                os.unlink(path)
            except OSError:
                pass

    new_filename = _rewrite_extension(filename, target_ext)
    log.info(
        "File conversion: %s -> %s (%s to %s via pypandoc)",
        filename,
        new_filename,
        source_ext,
        target_ext,
    )
    return converted, new_filename


def _extract_extension(filename: str) -> str:
    return Path(filename).suffix.lstrip(".").lower()


def _rewrite_extension(filename: str, new_ext: str) -> str:
    stem, _ = os.path.splitext(filename)
    return f"{stem}.{new_ext}"
