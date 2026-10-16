import textwrap
from typing import Iterable


def build_pdf(lines: Iterable[str], title: str = "") -> bytes:
    """Render plain text lines into a simple text-based PDF (used for seed data, samples and tests)."""
    import pymupdf as fitz

    doc = fitz.open()
    page = doc.new_page()
    y = 60
    if title:
        page.insert_text((50, y), title, fontsize=14)
        y += 30
    for line in lines:
        wrapped = textwrap.wrap(line, width=92) or [""]
        for i, chunk in enumerate(wrapped):
            if y > 800:
                page = doc.new_page()
                y = 60
            page.insert_text((50 if i == 0 else 64, y), chunk, fontsize=10.5)
            y += 15
        y += 4
    data = doc.tobytes()
    doc.close()
    return data
