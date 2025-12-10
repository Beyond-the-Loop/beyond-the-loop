import logging
import ftfy
import sys

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
import pytesseract
import pymupdf

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
    """Extract text from scanned PDF using OCR."""
    pages = convert_from_path(file_path, dpi=300)
    docs = []
    for i, page in enumerate(pages):
        text = pytesseract.image_to_string(page, lang="eng")
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

        print("DAS SIND DIE DOCS", docs)

        return [
            Document(
                page_content=ftfy.fix_text(doc.page_content), metadata=doc.metadata
            )
            for doc in docs
        ]

