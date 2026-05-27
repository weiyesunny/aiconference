"""Extract text content from uploaded documents."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_text(file_path: str) -> str:
    """Extract plain text from a document file.

    Supports: .txt, .md, .docx, .pdf
    """
    ext = Path(file_path).suffix.lower()

    if ext in (".txt", ".md"):
        return _read_text(file_path)
    elif ext == ".docx":
        return _read_docx(file_path)
    elif ext == ".pdf":
        return _read_pdf(file_path)
    else:
        raise ValueError(f"Unsupported document type: {ext}")


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _read_docx(path: str) -> str:
    from docx import Document
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _read_pdf(path: str) -> str:
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(path)
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        return "\n".join(pages)
    except ImportError:
        logger.warning("PyPDF2 not installed, cannot read PDF files")
        raise ValueError("PDF 支持需要安装 PyPDF2 依赖")
