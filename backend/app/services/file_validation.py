import os
import re
import zipfile
import io
from dataclasses import dataclass
from typing import Optional

from app.core.config import settings

PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class FileValidationError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class ValidatedFile:
    extension: str  # ".pdf" or ".docx"
    mime_type: str
    safe_name: str


def sanitize_filename(filename: str) -> str:
    """Strip any path components and unsafe characters from a client-supplied filename."""
    name = os.path.basename(filename.replace("\\", "/")).strip()
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name)
    name = name.lstrip(".") or "paper"
    return name[:200]


def validate_upload(filename: str, content: bytes, max_bytes: Optional[int] = None) -> ValidatedFile:
    """Validate size, extension and magic bytes. The client-declared MIME type is not trusted."""
    if not content:
        raise FileValidationError("The uploaded file is empty.")
    max_bytes = settings.max_upload_bytes if max_bytes is None else max_bytes
    if len(content) > max_bytes:
        raise FileValidationError(
            f"File size exceeds maximum allowed limit of {max_bytes // (1024 * 1024)}MB.", status_code=413
        )

    safe_name = sanitize_filename(filename or "")
    extension = os.path.splitext(safe_name)[1].lower()

    if extension == ".pdf":
        if not content.lstrip()[:5].startswith(b"%PDF-"):
            raise FileValidationError("File content is not a valid PDF document.")
        return ValidatedFile(".pdf", PDF_MIME, safe_name)

    if extension == ".docx":
        if not content.startswith(b"PK"):
            raise FileValidationError("File content is not a valid DOCX document.")
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                if "word/document.xml" not in archive.namelist():
                    raise FileValidationError("File content is not a valid DOCX document.")
        except zipfile.BadZipFile:
            raise FileValidationError("File is encrypted or unreadable. Please upload an unprotected PDF/DOCX.")
        return ValidatedFile(".docx", DOCX_MIME, safe_name)

    raise FileValidationError("Unsupported file type. Please upload a PDF or DOCX file.", status_code=415)
