import logging
import ftfy
import os
import sys
import tempfile

from langchain_community.document_loaders import (
    BSHTMLLoader,
    CSVLoader,
    Docx2txtLoader,
    OutlookMessageLoader,
    PyPDFLoader,
    TextLoader,
    UnstructuredEPubLoader,
    UnstructuredExcelLoader,
    UnstructuredPowerPointLoader,
    UnstructuredRSTLoader,
    UnstructuredXMLLoader
)

from langchain_core.documents import Document
from open_webui.env import SRC_LOG_LEVELS, GLOBAL_LOG_LEVEL

from pdf2image import convert_from_path
from PIL import Image
import pytesseract
import pymupdf

# DPI used to rasterize scanned PDFs before OCR. 200 is plenty for reliable
# text recognition while using ~4x less memory/CPU per page than 300.
PDF_OCR_DPI = int(os.environ.get("PDF_OCR_DPI", "200"))
PDF_OCR_LANG = os.environ.get("PDF_OCR_LANG", "eng")

logging.basicConfig(stream=sys.stdout, level=GLOBAL_LOG_LEVEL)
log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])

known_source_ext = [
    "go",
    "py",
    "java",
    "sh",
    "bat",
    "ps1",
    "cmd",
    "js",
    "ts",
    "css",
    "cpp",
    "hpp",
    "h",
    "c",
    "cs",
    "sql",
    "log",
    "ini",
    "pl",
    "pm",
    "r",
    "dart",
    "dockerfile",
    "env",
    "php",
    "hs",
    "hsc",
    "lua",
    "nginxconf",
    "conf",
    "m",
    "mm",
    "plsql",
    "perl",
    "rb",
    "rs",
    "db2",
    "scala",
    "bash",
    "swift",
    "vue",
    "svelte",
    "msg",
    "ex",
    "exs",
    "erl",
    "tsx",
    "jsx",
    "hs",
    "lhs",
]



def _is_pdf_image_only(file_path: str) -> bool:
    """Check if PDF contains extractable text or just images."""
    doc = pymupdf.open(file_path)
    for page in doc:
        if page.get_text("text").strip():  # If any text exists
            return False
    return True  # No text on any page → image-based PDF


def _extract_text_from_pdf_images(file_path: str) -> list[Document]:
    """Extract text from a scanned PDF using OCR, one page at a time.

    ``paths_only=True`` makes poppler write each rasterized page to disk
    instead of returning every page as an in-memory PIL image at once. We then
    open, OCR and release one page at a time, so peak memory stays bounded to a
    single page regardless of the page count. Previously the whole document was
    held in RAM (~26 MB/page at 300 DPI), which OOMKilled the pod on large
    scanned PDFs.
    """
    docs = []
    with tempfile.TemporaryDirectory() as temp_dir:
        image_paths = convert_from_path(
            file_path,
            dpi=PDF_OCR_DPI,
            output_folder=temp_dir,
            paths_only=True,
            fmt="png",
        )
        for i, image_path in enumerate(image_paths):
            with Image.open(image_path) as page:
                text = pytesseract.image_to_string(page, lang=PDF_OCR_LANG)
            docs.append(
                Document(
                    page_content=ftfy.fix_text(text),
                    metadata={"source": file_path, "page": i + 1},
                )
            )
    return docs

class Loader:
    def __init__(self, engine: str = "", **kwargs):
        self.engine = engine
        self.kwargs = kwargs

    def _get_loader(self, filename: str, file_content_type: str, file_path: str):
        file_ext = filename.split(".")[-1].lower()

        if file_ext == "pdf":
            if _is_pdf_image_only(file_path):
                loader = None  # We'll handle OCR separately in `load()`
            else:
                loader = PyPDFLoader(file_path)
        elif file_ext == "csv":
            loader = CSVLoader(file_path, encoding="latin1")
        elif file_ext == "rst":
            loader = UnstructuredRSTLoader(file_path, mode="elements")
        elif file_ext == "xml":
            loader = UnstructuredXMLLoader(file_path)
        elif file_ext in ["htm", "html"]:
            loader = BSHTMLLoader(file_path, open_encoding="unicode_escape")
        elif file_ext == "md":
            loader = TextLoader(file_path, autodetect_encoding=True)
        elif file_content_type == "application/epub+zip":
            loader = UnstructuredEPubLoader(file_path)
        elif (
            file_content_type
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            or file_ext == "docx"
        ):
            loader = Docx2txtLoader(file_path)
        elif file_content_type in [
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ] or file_ext in ["xls", "xlsx"]:
            loader = UnstructuredExcelLoader(file_path)
        elif file_content_type in [
            "application/vnd.ms-powerpoint",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ] or file_ext in ["ppt", "pptx"]:
            loader = UnstructuredPowerPointLoader(file_path)
        elif file_ext == "msg":
            loader = OutlookMessageLoader(file_path)
        elif file_ext in known_source_ext or (
            file_content_type and file_content_type.find("text/") >= 0
        ):
            loader = TextLoader(file_path, autodetect_encoding=True)
        else:
            loader = TextLoader(file_path, autodetect_encoding=True)

        return loader


    def load(self, filename: str, file_content_type: str, file_path: str) -> list[Document]:
        loader = self._get_loader(filename, file_content_type, file_path)

        # If loader is None and PDF is image-based → use OCR
        if loader is None:
            docs = _extract_text_from_pdf_images(file_path)
        else:
            docs = loader.load()
            docs = [
                Document(
                    page_content=ftfy.fix_text(doc.page_content),
                    metadata=doc.metadata
                )
                for doc in docs
            ]

        return [
            Document(
                page_content=ftfy.fix_text(doc.page_content), metadata=doc.metadata
            )
            for doc in docs
        ]

