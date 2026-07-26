"""
PDF Extraction Service — DCPI.
Primary: PyMuPDF (fitz) for fast native text extraction.
Fallback: OCR via pytesseract + pdf2image (only if both are installed).
"""

import logging
import importlib
import os
from pathlib import Path
from typing import List, Dict, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────
OCR_DPI = int(os.getenv("PDF_OCR_DPI", "300"))
OCR_LANGUAGES = os.getenv("PDF_OCR_LANGUAGES", "eng")
OCR_CONFIG = os.getenv("PDF_OCR_CONFIG", "--oem 3 --psm 6")
MAX_OCR_PAGES = int(os.getenv("PDF_MAX_OCR_PAGES", "100"))
PARALLEL_PAGE_THRESHOLD = int(os.getenv("PDF_PARALLEL_THRESHOLD", "5"))
OCR_MAX_WORKERS = int(os.getenv("PDF_OCR_MAX_WORKERS", str(min(32, (os.cpu_count() or 4) * 2))))
NATIVE_MAX_WORKERS = int(os.getenv("PDF_NATIVE_MAX_WORKERS", str(min(32, (os.cpu_count() or 4) * 2))))

# Shared thread pool to avoid per-call overhead
_shared_executor: Optional[ThreadPoolExecutor] = None
_executor_lock = __import__('threading').Lock()


def _get_shared_executor(max_workers: int = None) -> ThreadPoolExecutor:
    """Get or create a shared ThreadPoolExecutor singleton."""
    global _shared_executor
    if _shared_executor is None:
        with _executor_lock:
            if _shared_executor is None:
                workers = max_workers or NATIVE_MAX_WORKERS
                _shared_executor = ThreadPoolExecutor(max_workers=workers)
                logger.info(f"Created shared PDF ThreadPoolExecutor (workers={workers})")
    return _shared_executor


# ── Custom Exceptions ──────────────────────────────────────────────────────────

class PDFExtractionError(Exception):
    pass

class PDFEncryptedError(PDFExtractionError):
    pass

class PDFCorruptedError(PDFExtractionError):
    pass


def _load_pymupdf():
    """Load the real PyMuPDF module, avoiding any shadowing fitz package."""
    last_error = None

    for module_name in ("pymupdf", "fitz"):
        try:
            module = importlib.import_module(module_name)
        except ImportError as e:
            last_error = e
            continue

        if hasattr(module, "open"):
            return module

        last_error = ImportError(
            f"Module '{module_name}' does not expose PyMuPDF's open() API"
        )

    raise ImportError(
        "PyMuPDF is required. Install the PyMuPDF package and remove any "
        "conflicting fitz namespace package."
    ) from last_error


# ── Core Extraction ────────────────────────────────────────────────────────────

def extract_text_from_pdf(
    file_path: str,
    use_ocr_fallback: bool = True,
    max_pages: Optional[int] = None,
    parallel: bool = True
) -> List[Dict[str, Any]]:
    """
    Extract text from PDF. Returns list of {page_num, text, word_count} dicts.
    Falls back to OCR if text content is too sparse and OCR deps are installed.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    file_size = os.path.getsize(file_path)
    if file_size == 0:
        raise PDFCorruptedError(f"PDF file is empty: {file_path}")

    logger.info(
        f"Extracting PDF: {Path(file_path).name} ({file_size / 1024:.1f} KB)"
    )

    fitz = _load_pymupdf()

    doc = None
    try:
        doc = _open_pdf_document(fitz, file_path)

        total_pages = len(doc)
        if total_pages == 0:
            logger.warning(f"PDF has no pages: {file_path}")
            return []

        pages_to_extract = min(total_pages, max_pages) if max_pages else total_pages

        # Check for scanned document (near-zero text density)
        if _check_if_scanned(fitz, doc):
            if use_ocr_fallback:
                logger.info(f"PDF appears scanned — attempting OCR: {Path(file_path).name}")
                doc.close()
                doc = None
                ocr_pages = _extract_with_ocr(file_path, max_pages)
                if ocr_pages:
                    return ocr_pages
                logger.warning("OCR fallback returned no pages; using native text extraction result")
                doc = _open_pdf_document(fitz, file_path)
            else:
                logger.warning(f"PDF appears scanned but OCR is disabled")

        # Extract pages
        if parallel and pages_to_extract >= PARALLEL_PAGE_THRESHOLD:
            pages = _extract_pages_parallel(fitz, doc, pages_to_extract, max_workers=NATIVE_MAX_WORKERS)
        else:
            pages = _extract_pages_sequential(fitz, doc, pages_to_extract)

        total_words = sum(p.get("word_count", 0) for p in pages)
        avg_words = total_words / len(pages) if pages else 0

        # Very sparse text — try OCR fallback
        if avg_words < 5 and use_ocr_fallback:
            logger.info(
                f"Very low text density ({avg_words:.1f} words/page), trying OCR"
            )
            doc.close()
            doc = None
            ocr_pages = _extract_with_ocr(file_path, max_pages)
            if ocr_pages:
                return ocr_pages
            logger.warning("OCR fallback returned no pages; keeping native text extraction result")
            return pages

        logger.info(
            f"Extracted {len(pages)} pages, {total_words} words "
            f"({avg_words:.1f} avg/page) from {Path(file_path).name}"
        )
        return pages

    except (PDFEncryptedError, PDFCorruptedError):
        raise
    except Exception as e:
        logger.error(f"PDF extraction error: {e}", exc_info=True)
        if use_ocr_fallback:
            try:
                return _extract_with_ocr(file_path, max_pages)
            except Exception as ocr_err:
                logger.error(f"OCR fallback also failed: {ocr_err}")
        return []
    finally:
        if doc:
            try:
                doc.close()
            except Exception:
                pass


def _open_pdf_document(fitz, file_path: str):
    try:
        doc = fitz.open(file_path)
    except Exception as e:
        err_str = str(e).lower()
        if "password" in err_str:
            raise PDFEncryptedError(f"PDF is encrypted: {file_path}") from e
        elif "corrupt" in err_str or "damaged" in err_str:
            raise PDFCorruptedError(f"PDF is corrupted: {file_path}") from e
        else:
            raise PDFCorruptedError(f"Cannot open PDF: {e}") from e

    if doc.is_encrypted:
        for pwd in ["", "password", "1234", "0000"]:
            try:
                if doc.authenticate(pwd):
                    break
            except Exception:
                continue
        else:
            doc.close()
            raise PDFEncryptedError(
                f"PDF requires a password: {file_path}"
            )
    return doc


def _check_if_scanned(fitz, doc) -> bool:
    sample_pages = min(len(doc), 5)
    total_chars = 0
    total_words = 0
    for page_num in range(sample_pages):
        try:
            text = doc[page_num].get_text("text")
            stripped = text.strip()
            total_chars += len(stripped)
            total_words += len(stripped.split()) if stripped else 0
        except Exception:
            continue
    return total_chars < 50 and total_words < 10


def _extract_pages_sequential(
    fitz, doc, num_pages: int
) -> List[Dict[str, Any]]:
    pages = []
    for page_num in range(num_pages):
        try:
            page = doc[page_num]
            text = page.get_text("text")

            if not text or len(text.strip()) < 50:
                text = page.get_text(
                    "text",
                    flags=fitz.TEXT_PRESERVE_LIGATURES | fitz.TEXT_PRESERVE_WHITESPACE
                )
            if not text or len(text.strip()) < 20:
                blocks = page.get_text("blocks")
                text = "\n".join(
                    b[4] for b in blocks if len(b) > 4 and isinstance(b[4], str)
                )

            word_count = len(text.split()) if text else 0
            pages.append({
                "page_num": page_num + 1,
                "text": text or "",
                "word_count": word_count,
                "char_count": len(text) if text else 0
            })
        except Exception as e:
            logger.warning(f"Failed to extract page {page_num + 1}: {e}")
            pages.append({
                "page_num": page_num + 1,
                "text": "",
                "word_count": 0,
                "char_count": 0
            })
    return pages


def _extract_pages_parallel(
    fitz, doc, num_pages: int, max_workers: int = 8
) -> List[Dict[str, Any]]:
    """Extract pages in parallel using page-range batching.
    Instead of re-opening the doc per thread (expensive), we split
    pages into ranges and give each thread a range to extract from
    its own doc handle.
    """
    doc_path = doc.name  # Get file path for thread-local re-open
    effective_workers = min(max_workers, num_pages)
    
    # Split pages into roughly equal ranges
    pages_per_worker = max(1, num_pages // effective_workers)
    ranges = []
    for i in range(0, num_pages, pages_per_worker):
        ranges.append((i, min(i + pages_per_worker, num_pages)))

    def extract_range(page_range: tuple) -> List[Dict[str, Any]]:
        start, end = page_range
        thread_doc = None
        results = []
        try:
            thread_doc = fitz.open(doc_path)
            for page_num in range(start, end):
                try:
                    page = thread_doc[page_num]
                    text = page.get_text("text")
                    if not text or len(text.strip()) < 50:
                        text = page.get_text(
                            "text",
                            flags=fitz.TEXT_PRESERVE_LIGATURES | fitz.TEXT_PRESERVE_WHITESPACE
                        )
                    word_count = len(text.split()) if text else 0
                    results.append({
                        "page_num": page_num + 1,
                        "text": text or "",
                        "word_count": word_count,
                        "char_count": len(text) if text else 0
                    })
                except Exception:
                    results.append({
                        "page_num": page_num + 1, "text": "",
                        "word_count": 0, "char_count": 0
                    })
        except Exception:
            # If doc open fails, return empty results for the range
            for page_num in range(start, end):
                results.append({
                    "page_num": page_num + 1, "text": "",
                    "word_count": 0, "char_count": 0
                })
        finally:
            if thread_doc:
                try:
                    thread_doc.close()
                except Exception:
                    pass
        return results

    executor = _get_shared_executor(max_workers)
    pages_dict = {}
    futures = {executor.submit(extract_range, r): r for r in ranges}
    for future in as_completed(futures):
        for result in future.result():
            pages_dict[result["page_num"]] = result

    return [pages_dict[i] for i in sorted(pages_dict.keys())]


def _extract_with_ocr(
    file_path: str,
    max_pages: Optional[int] = None
) -> List[Dict[str, Any]]:
    logger.info(f"Starting OCR extraction: {Path(file_path).name}")

    try:
        pdf2image = importlib.import_module("pdf2image")
    except ImportError:
        logger.error("pdf2image not installed — OCR unavailable. pip install pdf2image")
        return []

    try:
        pytesseract = importlib.import_module("pytesseract")
    except ImportError:
        logger.error("pytesseract not installed — OCR unavailable. pip install pytesseract")
        return []

    try:
        pytesseract.get_tesseract_version()
    except Exception:
        logger.error(
            "Tesseract not found. Install from https://github.com/UB-Mannheim/tesseract/wiki"
        )
        return []

    try:
        convert_kwargs: Dict[str, Any] = {
            "dpi": OCR_DPI,
            "fmt": "jpeg",
            "grayscale": True
        }
        if max_pages and max_pages < MAX_OCR_PAGES:
            convert_kwargs["first_page"] = 1
            convert_kwargs["last_page"] = max_pages

        images = pdf2image.convert_from_path(file_path, **convert_kwargs)
        if not images:
            return []

        def _ocr_single(index_and_image):
            i, image = index_and_image
            try:
                text = pytesseract.image_to_string(
                    image, lang=OCR_LANGUAGES, config=OCR_CONFIG
                )
                word_count = len(text.split()) if text else 0
                return {
                    "page_num": i + 1,
                    "text": text.strip() if text else "",
                    "word_count": word_count,
                    "char_count": len(text) if text else 0,
                    "extraction_method": "ocr"
                }
            except Exception as e:
                logger.error(f"OCR failed page {i + 1}: {e}")
                return {
                    "page_num": i + 1, "text": "", "word_count": 0,
                    "char_count": 0, "extraction_method": "ocr"
                }

        pages_dict: Dict[int, Dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=OCR_MAX_WORKERS) as executor:
            futures = {
                executor.submit(_ocr_single, (i, image)): i
                for i, image in enumerate(images)
            }
            for future in as_completed(futures):
                result = future.result()
                pages_dict[result["page_num"]] = result

        pages = [pages_dict[i] for i in sorted(pages_dict.keys())]
        total_words = sum(p["word_count"] for p in pages)
        logger.info(f"OCR complete: {len(pages)} pages, {total_words} words")
        return pages

    except Exception as e:
        logger.error(f"OCR extraction failed: {e}", exc_info=True)
        return []


# ── Convenience wrappers ───────────────────────────────────────────────────────

def extract_full_text(
    file_path: str,
    use_ocr_fallback: bool = True,
    include_page_markers: bool = True
) -> str:
    pages = extract_text_from_pdf(file_path, use_ocr_fallback)
    if not pages:
        return ""
    parts = []
    for page in pages:
        text = page.get("text", "").strip()
        if text:
            if include_page_markers:
                parts.append(f"\n--- PAGE {page['page_num']} ---\n{text}")
            else:
                parts.append(text)
    return "\n".join(parts)


def get_pdf_info(file_path: str) -> Dict[str, Any]:
    if not os.path.exists(file_path):
        return {"error": "File not found", "file_path": file_path}
    try:
        fitz = _load_pymupdf()
    except ImportError as e:
        return {"error": str(e)}
    try:
        doc = fitz.open(file_path)
        is_encrypted = doc.is_encrypted
        page_count = len(doc)
        total_words = 0
        for i in range(min(page_count, 5)):
            try:
                text = doc[i].get_text("text")
                total_words += len(text.split()) if text else 0
            except Exception:
                pass
        has_text = total_words > 50
        meta = doc.metadata or {}
        doc.close()
        stat = os.stat(file_path)
        return {
            "file_path": file_path,
            "file_name": Path(file_path).name,
            "file_size": stat.st_size,
            "page_count": page_count,
            "is_encrypted": is_encrypted,
            "has_text": has_text,
            "is_scanned": not has_text and page_count > 0,
            "needs_ocr": not has_text and page_count > 0,
            "metadata": {
                "title": meta.get("title", ""),
                "author": meta.get("author", ""),
                "format": meta.get("format", "PDF")
            }
        }
    except Exception as e:
        return {"error": str(e), "file_path": file_path}