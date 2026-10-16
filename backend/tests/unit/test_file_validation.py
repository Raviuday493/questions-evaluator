import io
import zipfile

import pytest

from app.services.file_validation import FileValidationError, sanitize_filename, validate_upload


def _docx_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", "<w:document/>")
    return buf.getvalue()


def test_accepts_pdf_and_docx_by_content():
    assert validate_upload("paper.PDF", b"%PDF-1.7 ...").mime_type == "application/pdf"
    assert validate_upload("paper.docx", _docx_bytes()).extension == ".docx"


@pytest.mark.parametrize("name,content,code", [
    ("paper.pdf", b"not a pdf", 400),
    ("paper.docx", b"PK\x03\x04garbage", 400),
    ("paper.exe", b"%PDF-1.7", 415),
    ("paper.pdf", b"", 400),
])
def test_rejects_invalid_files(name, content, code):
    with pytest.raises(FileValidationError) as exc:
        validate_upload(name, content)
    assert exc.value.status_code == code


def test_sanitize_filename_strips_paths_and_unsafe_characters():
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("C:/Users/x/my paper<1>.pdf") == "my paper_1_.pdf"
    assert sanitize_filename("...") == "paper"
