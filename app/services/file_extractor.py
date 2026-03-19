"""Extract text from uploaded files (PDF, DOCX, TXT)."""

import logging

logger = logging.getLogger("smartexec.file_extractor")


def extract_text(content: bytes, filename: str) -> str:
    """Extract text from file content based on filename extension."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext == "pdf":
        return _extract_pdf(content)
    elif ext == "docx":
        return _extract_docx(content)
    elif ext in ("txt", "md", "csv", "tsv", "log"):
        return _extract_text(content)
    else:
        logger.warning("Unsupported file type: %s", ext)
        return f"[Unsupported file type: .{ext}]"


def _extract_pdf(content: bytes) -> str:
    """Extract text from PDF using pdfminer."""
    try:
        from io import BytesIO
        from pdfminer.high_level import extract_text as pdf_extract

        return pdf_extract(BytesIO(content))
    except ImportError:
        logger.error("pdfminer.six not installed")
        return "[PDF extraction requires pdfminer.six]"
    except Exception as e:
        logger.error("PDF extraction failed: %s", e)
        return f"[PDF extraction error: {e}]"


def _extract_docx(content: bytes) -> str:
    """Extract text from DOCX using python-docx."""
    try:
        from io import BytesIO
        from docx import Document

        doc = Document(BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs)
    except ImportError:
        logger.error("python-docx not installed")
        return "[DOCX extraction requires python-docx]"
    except Exception as e:
        logger.error("DOCX extraction failed: %s", e)
        return f"[DOCX extraction error: {e}]"


def _extract_text(content: bytes) -> str:
    """Extract text from plain text files with encoding detection."""
    try:
        import chardet

        detected = chardet.detect(content)
        encoding = detected.get("encoding", "utf-8") or "utf-8"
        return content.decode(encoding)
    except ImportError:
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            return content.decode("shift_jis", errors="replace")
    except Exception as e:
        logger.error("Text extraction failed: %s", e)
        return content.decode("utf-8", errors="replace")
