"""
Specification Document Parser Service — DCPI.
Parses data centre EPC specification PDFs into structured clause requirements
using LLM-powered extraction with concurrent batch processing.
"""

import os
import re
import json
import uuid
import logging
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any, Tuple

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────
MAX_CLAUSE_TEXT_LENGTH = int(os.getenv("MAX_CLAUSE_TEXT_LENGTH", "3000"))
MAX_PARALLEL_EXTRACTIONS = int(os.getenv("MAX_PARALLEL_EXTRACTIONS", "5"))
MIN_WORDS_FOR_EXTRACTION = int(os.getenv("MIN_WORDS_FOR_EXTRACTION", "15"))
MEGA_BATCH_SIZE = int(os.getenv("MEGA_BATCH_SIZE", "5"))  # Clauses per LLM call

# ── Imports with graceful degradation ─────────────────────────────────────────
try:
    from services.pdf_extractor import extract_text_from_pdf
except ImportError as e:
    logger.error(f"Failed to import pdf_extractor: {e}")
    raise

try:
    from services.llm_client import call_claude_json, call_claude_json_batch, has_available_provider
    LLM_AVAILABLE = True
except ImportError as e:
    logger.warning(f"LLM client not available: {e}")
    LLM_AVAILABLE = False

try:
    from services.vector_store import (
        index_spec_clause, CHROMADB_AVAILABLE,
        get_or_create_collection, embed_texts, _serialize_metadata
    )
    VECTOR_STORE_AVAILABLE = bool(CHROMADB_AVAILABLE)
except ImportError as e:
    logger.warning(f"Vector store not available: {e}")
    VECTOR_STORE_AVAILABLE = False

try:
    from database.connection import get_db
    DATABASE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Database not available: {e}")
    DATABASE_AVAILABLE = False


# ── Prompt ─────────────────────────────────────────────────────────────────────
CLAUSE_BATCH_EXTRACTION_SYSTEM = """You are a technical specification analyst for data centre EPC projects.
Extract structured requirements from the following specification clauses.

Return a JSON object with EXACTLY this structure and no others:
{
  "extracted_clauses": [
    {
      "clause_number": "4.1",
      "equipment_class": "UPS",
      "clause_type": "TECHNICAL",
      "applicable_tier": "TIER_IV",
      "requirements": [
        {
          "attribute": "efficiency_pct",
          "required_value": 96.5,
          "tolerance_type": "MIN",
          "tolerance_pct": null,
          "unit": "%",
          "mandatory": true,
          "description": "Minimum efficiency at full load in VFI mode"
        }
      ],
      "ambiguity_flags": [],
      "standards_referenced": ["IEC 62040-3"],
      "confidence_score": 0.9
    }
  ]
}

Rules for EACH clause:
- equipment_class: UPS | CRAC | GENERATOR | SWITCHGEAR | TRANSFORMER | PDU | COOLING | OTHER
- clause_type: TECHNICAL | QUALITY | SAFETY | ENVIRONMENTAL | INSTALLATION | MAINTENANCE | COMPLIANCE | GENERAL
- applicable_tier: TIER_I | TIER_II | TIER_III | TIER_IV | BOTH | N/A
- tolerance_type: MIN | MAX | EXACT | RANGE
- attribute: snake_case (e.g. efficiency_pct, battery_autonomy_min, ip_rating)
- required_value: number only — no units in the value field
- mandatory: true if text says "shall" or "must", false for "should" or "may"
- confidence_score: 0.0-1.0

Return ONLY valid JSON. No markdown. No preamble. No explanation."""


# ── Main entry points ──────────────────────────────────────────────────────────

def parse_spec_document(document_id: str, file_path: str) -> List[Dict[str, Any]]:
    """
    Synchronous entry point. Called by upload router.
    Alias for parse_spec_document_sync for backward compatibility.
    """
    return parse_spec_document_sync(document_id, file_path)


async def parse_spec_document_async(document_id: str, file_path: str) -> List[Dict[str, Any]]:
    """
    Async wrapper for the synchronous parser.

    Runs the CPU/IO-heavy parse work in a worker thread so async request
    handlers can await it without blocking the event loop.
    """
    return await asyncio.to_thread(parse_spec_document_sync, document_id, file_path)


def parse_spec_document_sync(document_id: str, file_path: str) -> List[Dict[str, Any]]:
    """
    Parse a specification PDF into structured clauses.

    Steps:
    1. Extract text from PDF (PyMuPDF, OCR fallback)
    2. Segment into clauses by numbered header pattern
    3. Filter clauses that contain technical requirements
    4. Extract structured requirements from each clause via LLM (concurrent batch)
    5. Save to SQLite and index in ChromaDB
    6. Return extracted clause list
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Specification file not found: {file_path}")

    logger.info(f"Parsing specification: doc={document_id} file={file_path}")

    try:
        pages = extract_text_from_pdf(file_path)
    except Exception as e:
        logger.error(f"PDF extraction failed: {e}")
        raise ValueError(f"PDF extraction failed: {e}") from e

    if not pages:
        logger.warning(f"No text extracted from {file_path}")
        return []

    logger.info(f"Extracted {len(pages)} pages")

    clauses = segment_into_clauses(pages)
    logger.info(f"Found {len(clauses)} clause segments")

    if not clauses:
        return []

    filtered = [c for c in clauses if should_extract(c)]
    logger.info(f"Filtered {len(filtered)}/{len(clauses)} clauses for LLM extraction")

    if not filtered:
        return []

    if len(filtered) == 1:
        result = extract_clause_requirements(filtered[0], document_id)
        extracted = [result] if result else []
    else:
        extracted = _extract_clauses_concurrent(filtered, document_id)

    if extracted:
        try:
            _save_clauses_to_db(document_id, extracted)
        except Exception as e:
            logger.error(f"Failed to save clauses to DB: {e}")

        if VECTOR_STORE_AVAILABLE:
            try:
                _index_extracted_clauses(extracted, document_id)
            except Exception as e:
                logger.error(f"Failed to index clauses in ChromaDB: {e}")

    logger.info(
        f"Parsed document {document_id}: "
        f"{len(extracted)} clauses extracted from {len(pages)} pages"
    )
    return extracted


# ── Segmentation ───────────────────────────────────────────────────────────────

def segment_into_clauses(pages: List[Dict]) -> List[Dict[str, Any]]:
    """
    Split document text into clauses based on numbered clause headers.
    Handles formats: 4.1, 4.1.1, Section 4.1, [4.1]
    """
    full_text_parts = []
    page_map = []

    for page in pages:
        page_text = page.get("text", "")
        if page_text.strip():
            start_pos = sum(len(p) + 1 for p in full_text_parts)
            full_text_parts.append(page_text)
            page_map.append({
                "start": start_pos,
                "end": start_pos + len(page_text),
                "page_num": page.get("page_num", 1)
            })

    full_text = "\n".join(full_text_parts)
    if not full_text.strip():
        return []

    patterns = [
        re.compile(r"(?m)^\s*(\d+(?:\.\d+)+)\s+([A-Z][^\n]{2,150})$", re.MULTILINE),
        re.compile(
            r"(?m)^\s*(?:Section|Clause|Article)\s+(\d+(?:\.\d+)+)\s*[-:.]?\s*([A-Z][^\n]{2,150})$",
            re.MULTILINE | re.IGNORECASE
        ),
        re.compile(r"(?m)^\s*[[(](\d+(?:\.\d+)+)[])]\s+([A-Z][^\n]{2,150})$", re.MULTILINE),
    ]

    matches = []
    for pattern in patterns:
        matches = list(pattern.finditer(full_text))
        if matches:
            logger.debug(f"Found {len(matches)} clauses using pattern")
            break

    if not matches:
        logger.info("No clause headers found — treating full document as single clause")
        return [{
            "clause_number": "1.0",
            "clause_title": "Full Document",
            "text": full_text[:MAX_CLAUSE_TEXT_LENGTH * 3],
            "pages": [p.get("page_num", 1) for p in pages]
        }]

    clauses = []
    for i, match in enumerate(matches):
        start_pos = match.start()
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        clause_text = full_text[start_pos:end_pos].strip()

        clause_pages = [
            pm["page_num"]
            for pm in page_map
            if start_pos <= pm["end"] and pm["start"] <= end_pos
        ]

        title = re.sub(r'\s+', ' ', match.group(2).strip()).rstrip('.')
        clauses.append({
            "clause_number": match.group(1),
            "clause_title": title[:200],
            "text": clause_text[:MAX_CLAUSE_TEXT_LENGTH * 3],
            "pages": sorted(set(clause_pages)) if clause_pages else [1]
        })

    return clauses


def should_extract(clause: Dict[str, Any]) -> bool:
    """Return True if the clause likely contains technical requirements worth extracting."""
    text = clause.get("text", "")
    words = text.split()

    if len(words) < MIN_WORDS_FOR_EXTRACTION:
        return False

    text_lower = text.lower()

    skip_keywords = [
        "table of contents", "list of figures", "revision history",
        "document control", "acknowledgments", "preface", "glossary"
    ]
    if any(kw in text_lower for kw in skip_keywords):
        return False

    has_requirement = any(kw in text_lower for kw in [
        "shall", "must", "required", "minimum", "maximum", "rating",
        "efficiency", "voltage", "current", "frequency", "power",
        "capacity", "protection", "autonomy", "transfer", "performance",
        "compliance", "conform", "tolerance", "rated", "nominal", "specified"
    ])

    has_numbers = bool(re.search(r'\d+(?:\.\d+)?', text))

    return has_requirement or (has_numbers and len(words) >= 20)


# ── Heuristic (Zero-LLM) extraction ───────────────────────────────────────────

# Regex patterns for common technical requirements
REQUIREMENT_PATTERNS = [
    # "efficiency shall be minimum 96.5%"
    (r'(?:efficiency|η)\s*(?:shall|must|should)?\s*(?:be\s+)?(?:minimum|min|at\s+least|≥|>=)\s*(\d+(?:\.\d+)?)\s*%',
     'efficiency_pct', 'MIN', '%'),
    # "rated at 500 kVA" / "500kVA rated capacity"
    (r'(?:rated|capacity|rating)\s*(?:at|of|:)?\s*(\d+(?:\.\d+)?)\s*kva',
     'rated_kva', 'MIN', 'kVA'),
    (r'(\d+(?:\.\d+)?)\s*kva\s*(?:rated|capacity|rating)',
     'rated_kva', 'MIN', 'kVA'),
    # "input voltage 380-415 VAC" / "input voltage shall be 400 VAC"
    (r'input\s+voltage\s*(?:shall|must)?\s*(?:be)?\s*(?:range)?\s*(\d+(?:\.\d+)?)\s*(?:v|vac)',
     'input_voltage_vac', 'EXACT', 'VAC'),
    # "output voltage 400 VAC"
    (r'output\s+voltage\s*(?:shall|must)?\s*(?:be)?\s*(\d+(?:\.\d+)?)\s*(?:v|vac)',
     'output_voltage_vac', 'EXACT', 'VAC'),
    # "input frequency 50 Hz"
    (r'input\s+frequency\s*(?:shall|must)?\s*(?:be)?\s*(\d+(?:\.\d+)?)\s*hz',
     'input_frequency_hz', 'EXACT', 'Hz'),
    # "output frequency 50 Hz"
    (r'output\s+frequency\s*(?:shall|must)?\s*(?:be)?\s*(\d+(?:\.\d+)?)\s*hz',
     'output_frequency_hz', 'EXACT', 'Hz'),
    # "THDi < 5%" / "input THD shall not exceed 5%"
    (r'(?:thdi|input\s+thd|input\s+harmonic|current\s+thd)\s*(?:shall|must)?\s*(?:be)?\s*(?:less\s+than|<|≤|<=|not\s+exceed|maximum|max)?\s*(\d+(?:\.\d+)?)\s*%',
     'input_thdi_pct', 'MAX', '%'),
    # "THDu < 3%" / "output THD shall not exceed 3%"
    (r'(?:thdu|output\s+thd|output\s+harmonic|voltage\s+thd)\s*(?:shall|must)?\s*(?:be)?\s*(?:less\s+than|<|≤|<=|not\s+exceed|maximum|max)?\s*(\d+(?:\.\d+)?)\s*%',
     'output_thdu_pct', 'MAX', '%'),
    # "transfer time shall not exceed 10ms" / "transfer time < 10 ms"
    (r'transfer\s+time\s*(?:shall|must)?\s*(?:be)?\s*(?:less\s+than|<|≤|<=|not\s+exceed|maximum|max|within)?\s*(\d+(?:\.\d+)?)\s*(?:ms|millisecond)',
     'transfer_time_ms', 'MAX', 'ms'),
    # "battery autonomy minimum 10 minutes" / "backup time shall be at least 15 min"
    (r'(?:battery\s+)?(?:autonomy|backup\s+time|runtime|battery\s+runtime)\s*(?:shall|must)?\s*(?:be)?\s*(?:minimum|min|at\s+least|≥|>=)?\s*(\d+(?:\.\d+)?)\s*(?:min|minute)',
     'battery_autonomy_min', 'MIN', 'min'),
    # "IP31" / "IP rating shall be IP54"
    (r'(?:ip\s*(?:rating)?|ingress\s+protection)\s*(?:shall|must)?\s*(?:be)?\s*(?:at\s+least|minimum)?\s*(?:ip)?\s*(\d{2})',
     'ip_rating', 'MIN', ''),
]

EQUIPMENT_KEYWORDS = {
    'UPS': ['ups', 'uninterruptible', 'battery', 'inverter', 'rectifier', 'vfi'],
    'GENERATOR': ['generator', 'genset', 'diesel', 'alternator', 'prime mover'],
    'CRAC': ['crac', 'crah', 'cooling', 'air conditioning', 'chiller', 'hvac'],
    'SWITCHGEAR': ['switchgear', 'switchboard', 'breaker', 'bus', 'ats', 'transfer switch'],
    'TRANSFORMER': ['transformer', 'step-down', 'step-up', 'dry type'],
    'PDU': ['pdu', 'power distribution', 'busway', 'bus duct'],
    'COOLING': ['cooling tower', 'condenser', 'evaporator', 'refrigerant'],
}

TIER_KEYWORDS = {
    'TIER_IV': ['tier iv', 'tier 4', 'fault tolerant', '2n', '2n+1'],
    'TIER_III': ['tier iii', 'tier 3', 'concurrently maintainable', 'n+1'],
    'TIER_II': ['tier ii', 'tier 2', 'redundant'],
    'TIER_I': ['tier i', 'tier 1', 'basic'],
}


def _detect_equipment_class(text: str) -> str:
    """Detect equipment class from clause text using keyword matching."""
    text_lower = text.lower()
    scores = {}
    for eq_class, keywords in EQUIPMENT_KEYWORDS.items():
        scores[eq_class] = sum(1 for kw in keywords if kw in text_lower)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else 'OTHER'


def _detect_tier(text: str) -> str:
    """Detect applicable tier from clause text."""
    text_lower = text.lower()
    for tier, keywords in TIER_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return tier
    return 'TIER_IV'  # default for data centre specs


def _detect_clause_type(text: str) -> str:
    """Detect clause type from text content."""
    text_lower = text.lower()
    type_keywords = {
        'TECHNICAL': ['shall be', 'must be', 'rated', 'capacity', 'voltage', 'frequency', 'efficiency'],
        'SAFETY': ['safety', 'hazard', 'emergency', 'fire', 'arc flash', 'lockout'],
        'QUALITY': ['quality', 'inspection', 'testing', 'certification', 'iso 9001'],
        'ENVIRONMENTAL': ['environmental', 'temperature', 'humidity', 'altitude', 'noise', 'emission'],
        'INSTALLATION': ['installation', 'mounting', 'foundation', 'cable', 'routing', 'clearance'],
        'MAINTENANCE': ['maintenance', 'serviceability', 'mttr', 'mtbf', 'spare parts'],
        'COMPLIANCE': ['comply', 'conformance', 'standard', 'iec', 'ieee', 'nfpa', 'ul', 'ce mark'],
    }
    scores = {}
    for ctype, keywords in type_keywords.items():
        scores[ctype] = sum(1 for kw in keywords if kw in text_lower)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else 'GENERAL'


def _extract_standards_referenced(text: str) -> List[str]:
    """Extract referenced standards from text."""
    patterns = [
        r'(IEC\s+\d+[\w\-\.]*)',
        r'(IEEE\s+\d+[\w\-\.]*)',
        r'(NFPA\s+\d+[\w\-\.]*)',
        r'(UL\s+\d+[\w\-\.]*)',
        r'(ISO\s+\d+[\w\-\.]*)',
        r'(ASHRAE\s+[\w\-\.]+)',
        r'(EN\s+\d+[\w\-\.]*)',
    ]
    standards = set()
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            standards.add(match.group(1).upper().strip())
    return sorted(standards)


def _extract_requirements_heuristic(clause: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract structured requirements from a clause using regex patterns.
    Returns a dict with requirements list and a confidence score.
    Zero LLM calls. Handles ~80% of data center spec clauses.
    """
    text = clause.get("text", "")
    text_lower = text.lower()
    clause_number = clause.get("clause_number", "?")

    requirements = []
    for pattern, attribute, tolerance_type, unit in REQUIREMENT_PATTERNS:
        for match in re.finditer(pattern, text_lower):
            value = match.group(1)
            # For IP rating, return as string
            if attribute == 'ip_rating':
                req_value = f"IP{value}"
            else:
                try:
                    req_value = float(value)
                except ValueError:
                    req_value = value

            # Check if mandatory
            context_start = max(0, match.start() - 100)
            context = text_lower[context_start:match.end()]
            is_mandatory = any(kw in context for kw in ['shall', 'must', 'required'])

            requirements.append({
                "attribute": attribute,
                "required_value": req_value,
                "tolerance_type": tolerance_type,
                "tolerance_pct": None,
                "unit": unit,
                "mandatory": is_mandatory,
                "description": f"Heuristic extraction from clause {clause_number}"
            })

    # Detect metadata
    equipment_class = _detect_equipment_class(text)
    applicable_tier = _detect_tier(text)
    clause_type = _detect_clause_type(text)
    standards = _extract_standards_referenced(text)

    # Confidence: higher if we found requirements, lower if text is complex
    has_complex_tables = bool(re.search(r'\|.*\|.*\|', text))
    has_nested_lists = text.count('\n') > 20 and bool(re.search(r'[a-z]\)', text_lower))
    word_count = len(text.split())

    if requirements:
        confidence = 0.75
        if len(requirements) >= 3:
            confidence = 0.85
    elif equipment_class != 'OTHER' and clause_type == 'TECHNICAL':
        confidence = 0.3  # Probably has requirements we missed
    else:
        confidence = 0.5  # General clause, heuristic is fine

    # Lower confidence for complex structures that regex may miss
    if has_complex_tables or has_nested_lists:
        confidence *= 0.7

    return {
        "requirements": requirements,
        "equipment_class": equipment_class,
        "clause_type": clause_type,
        "applicable_tier": applicable_tier,
        "ambiguity_flags": ["heuristic_extraction"],
        "standards_referenced": standards,
        "confidence_score": round(confidence, 2),
    }



# ── LLM extraction ─────────────────────────────────────────────────────────────

def _build_extraction_user_message(clause: Dict[str, Any]) -> str:
    clause_number = clause.get("clause_number", "?")
    clause_title = clause.get("clause_title", "")
    clause_text = clause.get("text", "")[:MAX_CLAUSE_TEXT_LENGTH]
    return f"""Extract structured requirements from this specification clause.

CLAUSE {clause_number}: {clause_title}

TEXT:
{clause_text}

Return a single JSON object as specified in the system prompt."""


def _llm_unavailable_stub(clause: Dict[str, Any], document_id: str) -> Dict[str, Any]:
    return {
        "equipment_class": "OTHER",
        "clause_type": "GENERAL",
        "applicable_tier": "N/A",
        "requirements": [],
        "ambiguity_flags": ["llm_unavailable"],
        "standards_referenced": [],
        "confidence_score": 0.1,
        "clause_number": clause.get("clause_number", "?"),
        "clause_title": clause.get("clause_title", ""),
        "document_id": document_id,
        "pages": clause.get("pages", []),
        "id": str(uuid.uuid4()),
        "text": clause.get("text", "")[:MAX_CLAUSE_TEXT_LENGTH],
    }


def _postprocess_extraction(
    result: Optional[Dict[str, Any]],
    clause: Dict[str, Any],
    document_id: str
) -> Optional[Dict[str, Any]]:
    """Apply field defaults/validation to a raw LLM extraction result for one clause."""
    clause_number = clause.get("clause_number", "?")
    clause_title = clause.get("clause_title", "")
    clause_text = clause.get("text", "")[:MAX_CLAUSE_TEXT_LENGTH]

    if not isinstance(result, dict):
        logger.warning(f"No usable extraction for clause {clause_number}; using stub")
        return _llm_unavailable_stub(clause, document_id)

    result.setdefault("equipment_class", "UPS")
    result.setdefault("clause_type", "TECHNICAL")
    result.setdefault("applicable_tier", "TIER_IV")
    result.setdefault("requirements", [])
    result.setdefault("ambiguity_flags", [])
    result.setdefault("standards_referenced", [])
    result.setdefault("confidence_score", 0.5)

    requirements = result.get("requirements", [])
    if not isinstance(requirements, list):
        requirements = []

    validated = []
    for req in requirements:
        if isinstance(req, dict) and req.get("attribute"):
            validated.append({
                "attribute": str(req.get("attribute", "unknown")),
                "required_value": req.get("required_value"),
                "tolerance_type": req.get("tolerance_type", "EXACT"),
                "tolerance_pct": req.get("tolerance_pct"),
                "unit": str(req.get("unit", "")),
                "mandatory": bool(req.get("mandatory", False)),
                "description": str(req.get("description", ""))
            })

    result["requirements"] = validated
    result["clause_number"] = clause_number
    result["clause_title"] = clause_title
    result["document_id"] = document_id
    result["pages"] = clause.get("pages", [])
    result["id"] = str(uuid.uuid4())
    result["text"] = clause_text

    logger.debug(
        f"Extracted {len(validated)} requirements from clause {clause_number} "
        f"(confidence={result.get('confidence_score', 0):.2f})"
    )
    return result


def extract_clause_requirements(
    clause: Dict[str, Any],
    document_id: str
) -> Optional[Dict[str, Any]]:
    """
    Extract structured requirements from a single clause via LLM.
    Used for single-clause documents; batch documents use
    _extract_clauses_concurrent instead.
    """
    if not LLM_AVAILABLE:
        logger.error("LLM client not available — cannot extract requirements")
        return None

    clause_number = clause.get("clause_number", "?")

    if not has_available_provider():
        return _llm_unavailable_stub(clause, document_id)

    user_message = _build_extraction_user_message(clause)

    try:
        result = call_claude_json(CLAUSE_BATCH_EXTRACTION_SYSTEM, user_message, max_tokens=1500)
        return _postprocess_extraction(result, clause, document_id)
    except Exception as e:
        logger.error(
            f"Failed to extract requirements from clause {clause_number}: {e}",
            exc_info=True
        )
        return _llm_unavailable_stub(clause, document_id)


def _extract_clauses_concurrent(
    clauses: List[Dict[str, Any]],
    document_id: str
) -> List[Dict[str, Any]]:
    """
    Concurrent clause extraction using mega-batching.
    Packs MEGA_BATCH_SIZE clauses into a single LLM call to drastically
    reduce the number of API requests (e.g. 100 clauses → 20 calls).
    """
    if not LLM_AVAILABLE:
        logger.error("LLM client not available — cannot extract requirements")
        return []

    if not has_available_provider():
        logger.warning("No LLM provider available — returning stubs for all clauses")
        return [_llm_unavailable_stub(c, document_id) for c in clauses]

    # Group clauses into mega-batches
    mega_batches = []
    for i in range(0, len(clauses), MEGA_BATCH_SIZE):
        batch_clauses = clauses[i:i + MEGA_BATCH_SIZE]
        mega_batches.append(batch_clauses)

    # Build LLM items: each item is a mega-batch of clauses
    items = []
    for batch_clauses in mega_batches:
        combined_text_parts = []
        for c in batch_clauses:
            clause_number = c.get("clause_number", "?")
            clause_title = c.get("clause_title", "")
            clause_text = c.get("text", "")[:MAX_CLAUSE_TEXT_LENGTH]
            combined_text_parts.append(
                f"=== CLAUSE {clause_number}: {clause_title} ===\n{clause_text}"
            )
        combined_user_msg = (
            f"Extract structured requirements from the following {len(batch_clauses)} "
            f"specification clauses. Return ALL clauses in the extracted_clauses array.\n\n"
            + "\n\n".join(combined_text_parts)
            + "\n\nReturn a single JSON object as specified in the system prompt. "
            f"The extracted_clauses array must contain exactly {len(batch_clauses)} entries."
        )
        items.append((CLAUSE_BATCH_EXTRACTION_SYSTEM, combined_user_msg))

    logger.info(
        f"Submitting {len(clauses)} clauses as {len(items)} mega-batches "
        f"(batch_size={MEGA_BATCH_SIZE}) to LLM..."
    )
    batch_results = call_claude_json_batch(items, max_tokens=2000)

    # Unpack mega-batch results back to individual clauses
    extracted = []
    clause_idx = 0
    for batch_clauses, result in zip(mega_batches, batch_results):
        if isinstance(result, dict):
            extracted_clauses_list = result.get("extracted_clauses", [])
            if not isinstance(extracted_clauses_list, list):
                extracted_clauses_list = [result]  # Single result, wrap it

            # Match extracted clauses to input clauses
            for j, clause_data in enumerate(batch_clauses):
                if j < len(extracted_clauses_list):
                    processed = _postprocess_extraction(
                        extracted_clauses_list[j], clause_data, document_id
                    )
                else:
                    processed = _llm_unavailable_stub(clause_data, document_id)
                if processed:
                    extracted.append(processed)
        else:
            # Result is None / failed — use stubs for all clauses in this batch
            for clause_data in batch_clauses:
                extracted.append(_llm_unavailable_stub(clause_data, document_id))
        clause_idx += len(batch_clauses)

    def _parse_num(s: str) -> tuple:
        try:
            return tuple(int(x) for x in s.split("."))
        except (ValueError, AttributeError):
            return (0,)

    extracted.sort(key=lambda x: _parse_num(x.get("clause_number", "0")))
    logger.info(
        f"Mega-batch extraction: {len(extracted)}/{len(clauses)} clauses processed "
        f"in {len(items)} API calls"
    )
    return extracted


# ── Database + Vector store ────────────────────────────────────────────────────

def _save_clauses_to_db(document_id: str, clauses: List[Dict[str, Any]]) -> int:
    """Save extracted clauses to SQLite using executemany for bulk performance."""
    if not DATABASE_AVAILABLE:
        raise RuntimeError("Database not available")

    db = get_db()
    try:
        rows = []
        for clause in clauses:
            clause_id = clause.get("id", str(uuid.uuid4()))
            requirements = clause.get("requirements", [])
            pages = clause.get("pages", [1])
            rows.append((
                clause_id,
                document_id,
                clause.get("clause_number", "0"),
                (clause.get("clause_title") or "")[:200],
                clause.get("equipment_class", "UPS"),
                clause.get("clause_type", "TECHNICAL"),
                clause.get("text", clause.get("raw_text", ""))[:5000],
                json.dumps(requirements),
                clause.get("applicable_tier", "TIER_IV"),
                json.dumps(pages),
                datetime.now(timezone.utc).isoformat(),
                float(clause.get("confidence_score", 0.5))
            ))

        db.executemany("""
            INSERT OR REPLACE INTO spec_clauses (
                id, document_id, clause_number, clause_title,
                equipment_class, clause_type, raw_text,
                requirements_json, tier, page_refs_json,
                extracted_ts, confidence_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)
        db.commit()
        logger.info(f"Batch-saved {len(rows)} clauses to database")
        return len(rows)

    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        logger.error(f"DB save failed: {e}")
        raise
    finally:
        db.close()


def _index_extracted_clauses(
    clauses: List[Dict[str, Any]],
    document_id: str
) -> int:
    """Batch-index clauses in ChromaDB for semantic search.
    Uses batch embedding (single model.encode() call) + single collection.upsert()
    for dramatically faster indexing vs. per-clause calls.
    """
    if not VECTOR_STORE_AVAILABLE:
        return 0

    try:
        collection = get_or_create_collection("spec_clauses")
    except Exception as e:
        logger.error(f"Cannot access spec_clauses collection: {e}")
        return 0

    # Build all items for batch processing
    ids = []
    texts = []
    metadatas = []

    for clause in clauses:
        try:
            clause_id = clause.get("id", str(uuid.uuid4()))
            requirements = clause.get("requirements", [])

            index_text = (
                f"Clause {clause.get('clause_number', '')}: "
                f"{clause.get('clause_title', '')}. "
                f"Equipment: {clause.get('equipment_class', 'UPS')}. "
                f"Tier: {clause.get('applicable_tier', 'TIER_IV')}. "
            )
            if requirements:
                req_parts = [
                    f"{r.get('attribute', '?')}: {r.get('required_value', '?')} {r.get('unit', '')}"
                    for r in requirements[:5]
                ]
                index_text += "Requirements: " + "; ".join(req_parts) + ". "

            raw = clause.get("text", clause.get("raw_text", ""))
            index_text += raw[:1000]

            if not index_text.strip():
                continue

            ids.append(clause_id)
            texts.append(index_text)
            metadatas.append(_serialize_metadata({
                "clause_number": clause.get("clause_number", ""),
                "clause_title": clause.get("clause_title", ""),
                "document_id": document_id,
                "equipment_class": clause.get("equipment_class", "UPS"),
                "tier": clause.get("applicable_tier", "TIER_IV"),
                "requirement_count": str(len(requirements)),
                "confidence_score": str(clause.get("confidence_score", 0.5))
            }))
        except Exception as e:
            logger.error(
                f"Failed to prepare clause {clause.get('clause_number', '?')}: {e}"
            )

    if not ids:
        return 0

    # Batch embed all texts in a single call
    try:
        embeddings = embed_texts(texts)
    except Exception as e:
        logger.error(f"Batch embedding failed: {e}")
        # Fallback to per-clause indexing
        indexed = 0
        for clause in clauses:
            try:
                clause_id = clause.get("id", str(uuid.uuid4()))
                raw = clause.get("text", clause.get("raw_text", ""))
                index_spec_clause(clause_id, raw[:2000], {
                    "clause_number": clause.get("clause_number", ""),
                    "document_id": document_id,
                })
                indexed += 1
            except Exception:
                pass
        return indexed

    # Batch upsert into ChromaDB (chunk by MAX_BATCH_SIZE=100)
    MAX_CHROMA_BATCH = 100
    indexed = 0
    for i in range(0, len(ids), MAX_CHROMA_BATCH):
        batch_ids = ids[i:i + MAX_CHROMA_BATCH]
        batch_texts = texts[i:i + MAX_CHROMA_BATCH]
        batch_embeddings = embeddings[i:i + MAX_CHROMA_BATCH]
        batch_metadatas = metadatas[i:i + MAX_CHROMA_BATCH]
        try:
            collection.upsert(
                ids=batch_ids,
                documents=batch_texts,
                embeddings=batch_embeddings,
                metadatas=batch_metadatas
            )
            indexed += len(batch_ids)
        except Exception as e:
            logger.error(f"ChromaDB batch upsert failed (batch {i}): {e}")

    logger.info(f"Batch-indexed {indexed}/{len(clauses)} clauses in vector store")
    return indexed