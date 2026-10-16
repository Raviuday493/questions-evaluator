import logging

logger = logging.getLogger("qpi.ocr")


class OCRUnavailableError(Exception):
    """Raised when OCR is needed but Tesseract/Poppler are not installed or OCR fails."""


class OCRService:
    @staticmethod
    def extract_text_with_ocr(file_bytes: bytes) -> str:
        """Fallback OCR extraction for scanned PDFs using pdf2image (Poppler) and pytesseract (Tesseract)."""
        try:
            import pytesseract
            from pdf2image import convert_from_bytes
        except ImportError as exc:
            raise OCRUnavailableError("OCR libraries are not installed.") from exc

        try:
            pytesseract.get_tesseract_version()
        except Exception as exc:
            raise OCRUnavailableError("Tesseract OCR is not installed on the server.") from exc

        try:
            logger.info("Triggering Tesseract OCR fallback for scanned PDF...")
            images = convert_from_bytes(file_bytes, dpi=300)
            extracted = "\n".join(pytesseract.image_to_string(img.convert("L")) for img in images).strip()
        except Exception as exc:
            logger.error("OCR extraction failed: %s", exc, exc_info=True)
            raise OCRUnavailableError("OCR extraction failed for this document.") from exc

        logger.info("OCR extraction completed. Yielded %d characters.", len(extracted))
        return extracted
