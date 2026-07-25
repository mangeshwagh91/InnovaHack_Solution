"""
Spec Compliance Agent — DCPI.
Compares vendor submittal attributes against specification requirements,
classifies deviations, and generates NCR records. Severity scoring and NCR
generation each run as one concurrent batch call instead of sequential loops.
"""

import os
import json
import uuid
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Any, Tuple

from database.connection import get_db
from services.llm_client import call_claude_batch, call_claude_json_batch, has_available_provider
from services.vector_store import CHROMADB_AVAILABLE, search_spec_clauses

logger = logging.getLogger(__name__)

AGENT_NAME = "spec_compliance"
AGENT_VERSION = "2.1.0"

CRITICAL_DEVIATION_PCT = float(os.getenv("COMPLIANCE_CRITICAL_DEVIATION_PCT", "15.0"))
MAJOR_DEVIATION_PCT = float(os.getenv("COMPLIANCE_MAJOR_DEVIATION_PCT", "10.0"))
MINOR_DEVIATION_PCT = float(os.getenv("COMPLIANCE_MINOR_DEVIATION_PCT", "5.0"))

ATTR_ALIASES: Dict[str, str] = {
    "efficiency": "efficiency_pct",
    "efficiency_percent": "efficiency_pct",
    "efficiency_percentage": "efficiency_pct",
    "full_load_efficiency": "efficiency_pct",
    "online_efficiency": "efficiency_pct",
    "ups_efficiency": "efficiency_pct",
    "operating_efficiency": "efficiency_pct",
    "system_efficiency": "efficiency_pct",
    "battery_autonomy": "battery_autonomy_min",
    "autonomy_min": "battery_autonomy_min",
    "autonomy_minutes": "battery_autonomy_min",
    "battery_runtime": "battery_autonomy_min",
    "backup_time": "battery_autonomy_min",
    "backup_time_min": "battery_autonomy_min",
    "battery_backup_min": "battery_autonomy_min",
    "runtime_minutes": "battery_autonomy_min",
    "battery_duration": "battery_autonomy_min",
    "ip": "ip_rating",
    "ip_rating_code": "ip_rating",
    "ingress_protection": "ip_rating",
    "protection_rating": "ip_rating",
    "ingress_protection_rating": "ip_rating",
    "ip_code": "ip_rating",
    "enclosure_rating": "ip_rating",
    "thdi": "input_thdi_pct",
    "thd_input": "input_thdi_pct",
    "input_thd": "input_thdi_pct",
    "input_current_thd": "input_thdi_pct",
    "input_harmonic_distortion": "input_thdi_pct",
    "thdu": "output_thdu_pct",
    "thd_output": "output_thdu_pct",
    "output_thd": "output_thdu_pct",
    "output_voltage_thd": "output_thdu_pct",
    "output_harmonic_distortion": "output_thdu_pct",
    "rated_power": "rated_kva",
    "rated_capacity": "rated_kva",
    "output_power": "rated_kva",
    "kva_rating": "rated_kva",
    "power_rating": "rated_kva",
    "capacity_kva": "rated_kva",
    "nominal_power": "rated_kva",
    "transfer": "transfer_time_ms",
    "transfer_time": "transfer_time_ms",
    "bypass_transfer_time": "transfer_time_ms",
    "switchover_time": "transfer_time_ms",
    "bypass_time": "transfer_time_ms",
    "input_voltage": "input_voltage_vac",
    "voltage_input": "input_voltage_vac",
    "supply_voltage": "input_voltage_vac",
    "output_voltage": "output_voltage_vac",
    "voltage_output": "output_voltage_vac",
    "frequency": "input_frequency_hz",
    "input_frequency": "input_frequency_hz",
    "output_frequency": "output_frequency_hz",
}

SEVERITY_SYSTEM = """You are a senior quality assurance engineer on a Tier IV hyperscale data centre EPC project.
Classify this specification deviation.

Return ONLY valid JSON:
{
  "severity": "CRITICAL|MAJOR|MINOR|OBSERVATION",
  "justification": "2-3 sentence technical justification",
  "recommended_action": "specific actionable resolution with timeline",
  "w_conform": 0.88
}"""

NCR_SYSTEM = """You are a quality assurance manager on a Tier IV data centre EPC project issuing Non-Conformance Reports.
Write in EXACTLY this format:
TITLE: [Concise technical title under 100 characters]
DESCRIPTION: [2-3 sentences]
IMPACT: [1-2 sentences]
ACTIONS:
1. [Specific action with responsible party and deadline]
2. [Specific action with responsible party and deadline]
3. [Specific action with responsible party and deadline]"""


def _safe_json_loads(value: Any, default: Any, label: str) -> Any:
    try:
        if value is None or value == "":
            return default
        return json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        logger.warning(f"Invalid JSON in {label}: {exc}")
        return default


def check_quantities(po_id: str, project_reqs: Dict[str, int]) -> Dict[str, Any]:
    """Lightweight rule-based quantity checker."""
    db = get_db()
    try:
        po_row = db.execute("SELECT * FROM purchase_orders WHERE id = ?", (po_id,)).fetchone()
        if not po_row:
            return {"status": "ERROR", "message": "PO not found"}
        po = dict(po_row)
        
        eq_row = db.execute("SELECT equipment_class FROM equipment_items WHERE id = ?", (po.get("equipment_item_id"),)).fetchone()
        eq_class = dict(eq_row).get("equipment_class", "UNKNOWN") if eq_row else "UNKNOWN"
        
        ordered_qty = po.get("quantity", 1)
        required_qty = project_reqs.get(eq_class, 0)
        
        if ordered_qty < required_qty:
            return {"status": "SHORTFALL", "ordered": ordered_qty, "required": required_qty, "equipment_class": eq_class}
        elif ordered_qty > required_qty:
            return {"status": "SURPLUS", "ordered": ordered_qty, "required": required_qty, "equipment_class": eq_class}
        else:
            return {"status": "MATCH", "ordered": ordered_qty, "required": required_qty, "equipment_class": eq_class}
    finally:
        db.close()


def run_compliance_check(po_id: str) -> Dict[str, Any]:
    agent_run_id = str(uuid.uuid4())
    started_ts = datetime.now(timezone.utc).isoformat()
    start_time = datetime.now()

    logger.info(f"Compliance check: PO={po_id} [{agent_run_id[:8]}]")

    db = get_db()
    try:
        po_row = db.execute("SELECT * FROM purchase_orders WHERE id = ?", (po_id,)).fetchone()
        if not po_row:
            raise ValueError(f"Purchase order '{po_id}' not found")
        po = dict(po_row)

        raw_attrs = _safe_json_loads(po.get("technical_attributes_json", "{}"), {}, "purchase_orders.technical_attributes_json")
        po_attrs = normalize_attributes(raw_attrs)
        logger.info(
            f"PO {po_id}: {len(po_attrs)} normalised attributes (vendor: {po.get('vendor_name', 'Unknown')})"
        )

        eq_row = db.execute("SELECT * FROM equipment_items WHERE id = ?", (po.get("equipment_item_id"),)).fetchone()
        if eq_row:
            equipment = dict(eq_row)
            equipment_class = equipment.get("equipment_class", "UPS")
        else:
            equipment = {}
            equipment_class = "UPS"


        clauses = []
        if CHROMADB_AVAILABLE:
            try:
                # Use vector search to find relevant clauses for this equipment class
                search_results = search_spec_clauses(equipment_class, n_results=10)
                for res in search_results:
                    if "requirements_json" in res["metadata"]:
                        clauses.append(res["metadata"])
                logger.info(f"Loaded {len(clauses)} spec clauses via Vector Search")
            except Exception as e:
                logger.warning(f"Vector search failed, falling back to SQLite: {e}")
        
        if not clauses:
            spec_clause_ids = _safe_json_loads(
                equipment.get("spec_clause_ids_json", "[]"),
                [],
                "equipment_items.spec_clause_ids_json",
            )
            if not isinstance(spec_clause_ids, list):
                spec_clause_ids = []

            if spec_clause_ids:
                ph = ",".join(["?"] * len(spec_clause_ids))
                clause_rows = db.execute(f"SELECT * FROM spec_clauses WHERE id IN ({ph})", spec_clause_ids).fetchall()
            else:
                clause_rows = db.execute(
                    "SELECT * FROM spec_clauses WHERE equipment_class = ?",
                    (equipment_class,)
                ).fetchall()
            clauses = [dict(r) for r in clause_rows]
            logger.info(f"Loaded {len(clauses)} spec clauses via SQLite")

        all_requirements = _extract_requirements(clauses)
        logger.info(f"Extracted {len(all_requirements)} requirements")

        raw_deviations = compare_attributes(po_attrs, all_requirements, equipment_class)
        
        # If no attributes were extracted at all, flag the entire document as invalid
        if not po_attrs:
            raw_deviations.append({
                "attribute_name": "document_content",
                "specified_value": "Technical Submittal with Performance Attributes",
                "submitted_value": "No technical attributes found (Possible non-technical document)",
                "deviation_pct": None,
                "deviation_type": "INVALID_DOCUMENT",
                "severity": "CRITICAL",
                "w_conform": 0.0,
                "justification": "The uploaded document contains no parsable technical attributes. It appears to be a non-technical document (e.g. delay notification, letter) rather than a valid equipment submittal.",
                "recommended_action": "Reject submission. Request vendor to submit the correct technical datasheet or compliance statement.",
                "mandatory": True,
                "spec_clause_id": None
            })

        logger.info(f"Found {len(raw_deviations)} deviations")

        # Batch-score all deviations concurrently instead of sequentially.
        scored_deviations = _score_deviations_batch(raw_deviations, equipment_class)

        now_ts = datetime.now(timezone.utc).isoformat()
        for dev in scored_deviations:
            dev_id = str(uuid.uuid4())
            dev["id"] = dev_id
            db.execute(
                """
                INSERT OR REPLACE INTO deviations
                (id, po_id, spec_clause_id, attribute_name,
                 specified_value, submitted_value, deviation_pct,
                 severity, deviation_type, w_conform,
                 justification, recommended_action, detected_ts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    dev_id,
                    po_id,
                    dev.get("spec_clause_id"),
                    dev["attribute_name"],
                    dev["specified_value"],
                    dev["submitted_value"],
                    dev.get("deviation_pct"),
                    dev.get("severity", "MINOR"),
                    dev.get("deviation_type", "VALUE"),
                    dev.get("w_conform", 0.5),
                    dev.get("justification", ""),
                    dev.get("recommended_action", ""),
                    now_ts,
                ),
            )
        db.commit()

        # Batch-generate NCRs for all qualifying deviations concurrently.
        ncr_targets = [
            dev for dev in scored_deviations
            if dev.get("severity") in ("CRITICAL", "MAJOR", "MINOR")
        ]
        ncr_ids = _generate_ncrs_batch(ncr_targets, po_id, equipment.get("id"), clauses)

        compliance_status = _determine_compliance_status(scored_deviations)
        conformance_score = _calculate_conformance_score(scored_deviations)
        db.execute(
            """
            UPDATE purchase_orders
            SET compliance_status = ?, deviation_count = ?,
                conformance_score = ?, checked_ts = ?
            WHERE id = ?
            """,
            (compliance_status, len(scored_deviations), round(conformance_score, 4), now_ts, po_id),
        )
        db.commit()

        summary = _build_summary(scored_deviations)
        processing_ms = round((datetime.now() - start_time).total_seconds() * 1000, 1)

        _log_agent_run_compliance_agent(
            agent_run_id=agent_run_id,
            started_ts=started_ts,
            po_id=po_id,
            vendor_name=po.get("vendor_name", ""),
            num_clauses=len(clauses),
            num_requirements=len(all_requirements),
            summary=summary,
            num_ncrs=len(ncr_ids),
            processing_ms=processing_ms,
            status="completed",
        )

        logger.info(
            f"Compliance check complete [{agent_run_id[:8]}]: PO={po_id} status={compliance_status} "
            f"{summary['total']} deviations ({summary['critical']} critical) | {processing_ms:.0f}ms"
        )

        return {
            "po_id": po_id,
            "compliance_status": compliance_status,
            "conformance_score": conformance_score,
            "deviations": scored_deviations,
            "ncr_ids": ncr_ids,
            "summary": summary,
            "agent_run_id": agent_run_id,
            "vendor_name": po.get("vendor_name", ""),
            "po_number": po.get("po_number", ""),
            "processing_time_ms": processing_ms,
        }

    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Compliance check failed for PO {po_id}: {e}", exc_info=True)
        _log_agent_run_compliance_agent(
            agent_run_id=agent_run_id,
            started_ts=started_ts,
            po_id=po_id,
            status="failed",
            error=str(e),
        )
        raise RuntimeError(f"Compliance check failed: {e}") from e
    finally:
        db.close()


def normalize_key(key: str) -> str:
    if not key:
        return ""
    k = re.sub(r"[_\s]+", "_", key.lower().strip()).strip("_")
    return ATTR_ALIASES.get(k, k)


def normalize_attributes(attrs: Dict[str, Any]) -> Dict[str, Any]:
    if not attrs:
        return {}
    normalised = {}
    for key, value in attrs.items():
        canonical = normalize_key(key)
        normalised[canonical] = value
        orig_lower = key.lower().strip()
        if orig_lower != canonical:
            normalised[orig_lower] = value
    for alias, canonical in ATTR_ALIASES.items():
        if canonical in normalised and alias not in normalised:
            normalised[alias] = normalised[canonical]
    return normalised


def find_submitted_value(spec_attr: str, po_attrs: Dict[str, Any]) -> Optional[Any]:
    if not spec_attr or not po_attrs:
        return None
    canonical = normalize_key(spec_attr)
    if canonical in po_attrs:
        return po_attrs[canonical]
    for alias, target in ATTR_ALIASES.items():
        if target == canonical and alias in po_attrs:
            return po_attrs[alias]
    spec_lower = spec_attr.lower().strip()
    for key in po_attrs:
        if spec_lower in key or key in spec_lower:
            return po_attrs[key]
    return None


def _extract_requirements(clauses: List[Dict]) -> List[Dict]:
    all_reqs = []
    seen_attrs = set()
    for clause in clauses:
        try:
            reqs = json.loads(clause.get("requirements_json", "[]"))
        except (json.JSONDecodeError, TypeError):
            reqs = []
        if not isinstance(reqs, list):
            reqs = []
        for req in reqs:
            if not req.get("attribute"):
                continue
            canonical = normalize_key(req["attribute"])
            if canonical not in seen_attrs:
                seen_attrs.add(canonical)
                req["spec_clause_id"] = clause["id"]
                req["clause_number"] = clause.get("clause_number", "")
                req["clause_title"] = clause.get("clause_title", "")
                req["tier"] = clause.get("tier", "TIER_IV")
                all_reqs.append(req)
    return all_reqs


def compare_attributes(po_attrs: Dict[str, Any], spec_requirements: List[Dict], equipment_class: str) -> List[Dict[str, Any]]:
    deviations = []
    for req in spec_requirements:
        spec_attr = req.get("attribute", "")
        if not spec_attr:
            continue
        submitted_val = find_submitted_value(spec_attr, po_attrs)
        if submitted_val is None:
            if req.get("mandatory", False):
                deviations.append({
                    "attribute_name": normalize_key(spec_attr),
                    "specified_value": str(req.get("required_value", "N/A")),
                    "submitted_value": "NOT SUBMITTED",
                    "deviation_pct": None,
                    "deviation_type": "MISSING",
                    "spec_clause_id": req.get("spec_clause_id"),
                    "unit": req.get("unit", ""),
                    "clause_number": req.get("clause_number", ""),
                    "clause_title": req.get("clause_title", ""),
                    "tier": req.get("tier", "TIER_IV"),
                    "mandatory": True,
                })
            continue

        deviation = _compare_single(
            spec_attr=spec_attr,
            required_val=req.get("required_value"),
            submitted_val=submitted_val,
            tolerance_type=req.get("tolerance_type", "EXACT"),
            tolerance_pct=req.get("tolerance_pct"),
            req=req,
        )
        if deviation:
            deviations.append(deviation)
            logger.info(
                f"DEVIATION: {deviation['attribute_name']} — specified={deviation['specified_value']}, "
                f"submitted={deviation['submitted_value']}, delta={deviation.get('deviation_pct')}%"
            )
    return deviations


def _compare_single(spec_attr: str, required_val: Any, submitted_val: Any, tolerance_type: str, tolerance_pct: Optional[float], req: Dict) -> Optional[Dict[str, Any]]:
    is_deviant = False
    deviation_pct = None
    deviation_type = "UNKNOWN"

    if isinstance(required_val, str) or isinstance(submitted_val, str):
        if str(required_val).strip().upper() != str(submitted_val).strip().upper():
            is_deviant = True
            deviation_type = "STRING_MISMATCH"
    else:
        try:
            sub_num = float(submitted_val)
            req_num = float(required_val)

            if tolerance_type == "MIN" and sub_num < req_num:
                is_deviant = True
                deviation_type = "VALUE_BELOW_MIN"
                if req_num != 0:
                    deviation_pct = round(abs(req_num - sub_num) / req_num * 100, 2)
            elif tolerance_type == "MAX" and sub_num > req_num:
                is_deviant = True
                deviation_type = "VALUE_ABOVE_MAX"
                if req_num != 0:
                    deviation_pct = round(abs(sub_num - req_num) / req_num * 100, 2)
            elif tolerance_type == "EXACT":
                if tolerance_pct and float(tolerance_pct) > 0:
                    tol = float(tolerance_pct)
                    lower = req_num * (1 - tol / 100)
                    upper = req_num * (1 + tol / 100)
                    if sub_num < lower or sub_num > upper:
                        is_deviant = True
                        deviation_type = "VALUE_OUTSIDE_RANGE"
                        if req_num != 0:
                            deviation_pct = round(abs(sub_num - req_num) / req_num * 100, 2)
                elif abs(sub_num - req_num) > 0.001:
                    is_deviant = True
                    deviation_type = "VALUE_OUTSIDE_RANGE"
                    if req_num != 0:
                        deviation_pct = round(abs(sub_num - req_num) / req_num * 100, 2)
        except (ValueError, TypeError) as e:
            logger.warning(f"Cannot compare {spec_attr}: {e}")
            if str(submitted_val) != str(required_val):
                is_deviant = True
                deviation_type = "UNKNOWN"

    if is_deviant:
        return {
            "attribute_name": normalize_key(spec_attr),
            "specified_value": str(required_val),
            "submitted_value": str(submitted_val),
            "deviation_pct": deviation_pct,
            "deviation_type": deviation_type,
            "spec_clause_id": req.get("spec_clause_id"),
            "unit": req.get("unit", ""),
            "clause_number": req.get("clause_number", ""),
            "clause_title": req.get("clause_title", ""),
            "tier": req.get("tier", "TIER_IV"),
            "mandatory": req.get("mandatory", False),
        }
    return None


def _build_severity_user_message(dev: Dict[str, Any], equipment_class: str) -> str:
    attr_display = dev["attribute_name"].replace("_", " ").title()
    dev_pct = dev.get("deviation_pct")
    return f"""DEVIATION TO CLASSIFY:

Attribute: {dev['attribute_name']} ({attr_display})
Specification requires: {dev['specified_value']} {dev.get('unit', '')}
Vendor submitted: {dev['submitted_value']} {dev.get('unit', '')}
Deviation magnitude: {f'{dev_pct:.1f}% from requirement' if dev_pct is not None else 'String/type mismatch'}
Comparison type: {dev.get('deviation_type', 'VALUE')}
Equipment class: {equipment_class}
Tier applicability: {dev.get('tier', 'TIER_IV')}
Clause reference: {dev.get('clause_number', '')} — {dev.get('clause_title', '')}
Mandatory: {'Yes' if dev.get('mandatory') else 'No'}

Classify this deviation and provide the w_conform score."""


def _score_deviations_batch(
    deviations: List[Dict[str, Any]],
    equipment_class: str
) -> List[Dict[str, Any]]:
    """
    Score all deviations concurrently via one batch call instead of a
    sequential per-deviation loop. Falls back to heuristic scoring per
    item on failure or when no LLM provider is available.
    """
    if not deviations:
        return []

    if not has_available_provider():
        for dev in deviations:
            _apply_heuristic_scoring(dev)
        return deviations

    batch_items: List[Tuple[str, str]] = [
        (SEVERITY_SYSTEM, _build_severity_user_message(dev, equipment_class))
        for dev in deviations
    ]

    try:
        results = call_claude_json_batch(batch_items, max_tokens=500)
    except Exception as e:
        logger.error(f"Severity scoring batch call failed entirely: {e}", exc_info=True)
        results = [None] * len(deviations)

    for dev, result in zip(deviations, results):
        if dev.get("deviation_type") == "INVALID_DOCUMENT":
            dev["severity"] = "CRITICAL"
            dev["w_conform"] = 0.0
            continue

        if isinstance(result, dict):
            try:
                dev["severity"] = result.get("severity", "MINOR")
                dev["justification"] = result.get("justification", "")
                dev["recommended_action"] = result.get("recommended_action", "Review and resolve with vendor")
                dev["w_conform"] = float(result.get("w_conform", 0.5))
            except (TypeError, ValueError) as e:
                logger.warning(f"Malformed severity result for {dev['attribute_name']}: {e}")
                _apply_heuristic_scoring(dev)
        else:
            logger.warning(f"No severity result for {dev['attribute_name']}; using heuristic")
            _apply_heuristic_scoring(dev)

    return deviations


def _apply_heuristic_scoring(dev: Dict[str, Any]) -> None:
    dev_pct = dev.get("deviation_pct")
    dev_type = dev.get("deviation_type", "")
    is_mandatory = dev.get("mandatory", False)
    attr = dev["attribute_name"]

    if dev_type == "MISSING" and is_mandatory:
        dev["severity"] = "CRITICAL"
        dev["w_conform"] = 0.90
    elif dev_type == "INVALID_DOCUMENT":
        dev["severity"] = "CRITICAL"
        dev["w_conform"] = 1.0
    elif dev_type == "STRING_MISMATCH":
        dev["severity"] = "MINOR"
        dev["w_conform"] = 0.30
    elif dev_pct is not None:
        if dev_pct >= CRITICAL_DEVIATION_PCT:
            dev["severity"] = "CRITICAL"
            dev["w_conform"] = min(0.95, 0.75 + (dev_pct - 15) * 0.01)
        elif dev_pct >= MAJOR_DEVIATION_PCT:
            dev["severity"] = "MAJOR"
            dev["w_conform"] = 0.50 + (dev_pct - 10) * 0.05
        elif dev_pct >= MINOR_DEVIATION_PCT:
            dev["severity"] = "MINOR"
            dev["w_conform"] = 0.15 + (dev_pct - 5) * 0.07
        else:
            dev["severity"] = "OBSERVATION"
            dev["w_conform"] = max(0.0, (dev_pct or 0) * 0.03)
    else:
        dev["severity"] = "MINOR"
        dev["w_conform"] = 0.25

    dev["justification"] = (
        f"Automated heuristic: {attr} submitted {dev['submitted_value']} vs required {dev['specified_value']}. "
        f"Deviation: {dev_pct if dev_pct is not None else 'N/A'}%."
    )
    dev["recommended_action"] = (
        f"Issue formal NCR. Request vendor provide compliant {attr} in revised submittal within 5 business days."
    )


def _build_ncr_user_message(dev: Dict[str, Any], spec_clause: Dict) -> str:
    attr_display = dev["attribute_name"].replace("_", " ").title()
    unit = dev.get("unit", "")
    dev_pct = dev.get("deviation_pct")
    return f"""Generate a formal NCR for this specification deviation:

ATTRIBUTE: {dev['attribute_name']} ({attr_display})
SPECIFICATION REQUIRES: {dev['specified_value']} {unit}
VENDOR SUBMITTED: {dev['submitted_value']} {unit}
DEVIATION: {f'{dev_pct:.1f}% from requirement' if dev_pct is not None else 'Non-compliant value'}
SEVERITY: {dev.get('severity', 'MINOR')}
EQUIPMENT CLASS: {spec_clause.get('equipment_class', 'UPS')}
SPEC CLAUSE: {spec_clause.get('clause_number', '')} — {spec_clause.get('clause_title', '')}
TIER: {spec_clause.get('tier', 'TIER_IV')}
JUSTIFICATION: {dev.get('justification', '')}

Write the NCR using the TITLE/DESCRIPTION/IMPACT/ACTIONS format."""


def _default_ncr_text(dev: Dict[str, Any]) -> str:
    attr_display = dev["attribute_name"].replace("_", " ").title()
    unit = dev.get("unit", "")
    return (
        f"TITLE: {attr_display} Non-Conformance — {dev.get('severity','MINOR')}\n"
        f"DESCRIPTION: Vendor submitted {dev['submitted_value']} {unit} for {dev['attribute_name']} against specified requirement of {dev['specified_value']} {unit}.\n"
        f"IMPACT: Requires resolution before equipment acceptance at site.\n"
        f"ACTIONS:\n"
        f"1. Issue formal NCR to vendor within 24 hours (Quality Manager)\n"
        f"2. Request revised submittal within 5 business days (Vendor Technical Director)\n"
        f"3. Notify Project Manager of potential schedule impact (NCR Coordinator)"
    )


def _generate_ncrs_batch(
    deviations: List[Dict[str, Any]],
    po_id: str,
    equipment_item_id: str,
    clauses: List[Dict]
) -> List[str]:
    """
    Generate NCR text for all qualifying deviations concurrently, then
    write each NCR record to the DB. Returns the list of created NCR ids.
    """
    if not deviations:
        return []

    matching_clauses = [
        next((c for c in clauses if c["id"] == dev.get("spec_clause_id")), clauses[0] if clauses else {})
        for dev in deviations
    ]

    if not has_available_provider():
        response_texts = [_default_ncr_text(dev) for dev in deviations]
    else:
        batch_items: List[Tuple[str, str]] = [
            (NCR_SYSTEM, _build_ncr_user_message(dev, clause))
            for dev, clause in zip(deviations, matching_clauses)
        ]
        try:
            raw_results = call_claude_batch(batch_items, max_tokens=800)
        except Exception as e:
            logger.error(f"NCR generation batch call failed entirely: {e}", exc_info=True)
            raw_results = [None] * len(deviations)

        response_texts = [
            text if text else _default_ncr_text(dev)
            for text, dev in zip(raw_results, deviations)
        ]

    ncr_ids = []
    for dev, clause, response_text in zip(deviations, matching_clauses, response_texts):
        ncr_id = _save_ncr(dev, po_id, equipment_item_id, clause, response_text)
        dev["ncr_id"] = ncr_id
        ncr_ids.append(ncr_id)

    return ncr_ids


def _save_ncr(
    dev: Dict[str, Any],
    po_id: str,
    equipment_item_id: str,
    spec_clause: Dict,
    response_text: str
) -> str:
    ncr_id = str(uuid.uuid4())
    attr_display = dev["attribute_name"].replace("_", " ").title()

    lines = response_text.strip().split("\n")
    title = f"{attr_display} Non-Conformance — {dev.get('severity','MINOR')}"
    actions = []
    in_actions = False
    for line in lines:
        stripped = line.strip()
        if stripped.upper().startswith("TITLE:"):
            candidate = stripped[6:].strip()
            if candidate:
                title = candidate[:200]
            in_actions = False
        elif stripped.upper().startswith("ACTIONS:"):
            in_actions = True
            continue
        elif in_actions and stripped and len(stripped) > 2:
            action_text = re.sub(r"^\d+[\.\)]\s*", "", stripped).strip()
            if action_text:
                actions.append(action_text)

    if not actions:
        actions = [
            f"Issue formal NCR to vendor for {dev['attribute_name']} within 24 hours",
            "Request revised submittal confirming compliant value within 5 business days",
            "Notify Project Manager and Schedule Coordinator of potential impact",
        ]

    schedule_impact = _compute_schedule_impact(equipment_item_id)
    due_date = (datetime.now(timezone.utc) + timedelta(days=5)).strftime("%Y-%m-%d")

    db = get_db()
    try:
        db.execute(
            """
            INSERT OR REPLACE INTO ncrs
            (id, deviation_id, po_id, equipment_item_id, title, description,
             severity, status, raised_ts, due_date, assigned_to,
             spec_clause_ref, page_ref, schedule_impact_json, actions_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ncr_id,
                dev.get("id", ""),
                po_id,
                equipment_item_id,
                title,
                response_text[:2000],
                dev.get("severity", "MINOR"),
                "open",
                datetime.now(timezone.utc).isoformat(),
                due_date,
                "Quality Manager",
                f"{spec_clause.get('clause_number','')} — {spec_clause.get('clause_title','')}",
                spec_clause.get("page_refs_json", "[]"),
                json.dumps(schedule_impact),
                json.dumps(actions),
            ),
        )
        db.commit()
        logger.info(f"NCR saved: {ncr_id[:8]} — {title[:80]}")
    except Exception as e:
        logger.error(f"Failed to save NCR: {e}")
        raise
    finally:
        db.close()

    return ncr_id


def _compute_schedule_impact(equipment_item_id: str) -> Dict[str, Any]:
    if not equipment_item_id:
        return {"linked_task_ids": [], "min_float_days": None, "days_until_required": None, "risk_level": "LOW", "tasks": []}
    db = get_db()
    try:
        rows = db.execute(
            """
            SELECT id, task_code, description, planned_start, planned_finish,
                   total_float_days, is_critical_path
            FROM schedule_tasks
            WHERE equipment_item_id = ?
            ORDER BY planned_start ASC
            """,
            (equipment_item_id,),
        ).fetchall()

        if not rows:
            return {"linked_task_ids": [], "min_float_days": None, "days_until_required": None, "risk_level": "LOW", "tasks": []}

        task_dicts = [dict(r) for r in rows]
        linked_ids = [t["id"] for t in task_dicts]
        float_vals = [t["total_float_days"] for t in task_dicts if t.get("total_float_days") is not None]
        min_float = min(float_vals) if float_vals else None

        days_until = None
        try:
            earliest = min(t["planned_start"] for t in task_dicts if t.get("planned_start"))
            days_until = (datetime.strptime(earliest, "%Y-%m-%d") - datetime.now()).days
        except Exception:
            pass

        is_critical = any(t.get("is_critical_path") for t in task_dicts)
        if is_critical and min_float is not None and min_float <= 0:
            risk_level = "CRITICAL"
        elif min_float is not None and min_float <= 3:
            risk_level = "HIGH"
        elif min_float is not None and min_float <= 7:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        return {
            "linked_task_ids": linked_ids,
            "min_float_days": min_float,
            "days_until_required": days_until,
            "risk_level": risk_level,
            "critical_path_impact": is_critical,
            "tasks": [
                {
                    "id": t["id"],
                    "code": t.get("task_code", t["id"]),
                    "description": t.get("description", "")[:200],
                    "float_days": t.get("total_float_days"),
                }
                for t in task_dicts[:5]
            ],
        }
    except Exception as e:
        logger.error(f"Schedule impact computation failed: {e}")
        return {"linked_task_ids": [], "min_float_days": None, "days_until_required": None, "risk_level": "UNKNOWN"}
    finally:
        db.close()


def _determine_compliance_status(deviations: List[Dict]) -> str:
    if not deviations:
        return "COMPLIANT"
    sevs = [d.get("severity", "") for d in deviations]
    if "CRITICAL" in sevs:
        return "CRITICAL_NON_CONFORMANCE"
    if "MAJOR" in sevs:
        return "NON_CONFORMANT"
    if "MINOR" in sevs:
        return "MINOR_NON_CONFORMANCE"
    if "OBSERVATION" in sevs:
        return "OBSERVATION"
    return "COMPLIANT"


def _calculate_conformance_score(deviations: List[Dict]) -> float:
    if not deviations:
        return 1.0
    severity_base = {"CRITICAL": 0.0, "MAJOR": 0.3, "MINOR": 0.6, "OBSERVATION": 0.9}
    scores = []
    for dev in deviations:
        sev = dev.get("severity", "MINOR")
        w = dev.get("w_conform", 0.5)
        scores.append(severity_base.get(sev, 0.5) * w)
    return round(sum(scores) / len(scores), 4) if scores else 1.0


def _build_summary(deviations: List[Dict]) -> Dict[str, int]:
    summary = {"total": len(deviations), "critical": 0, "major": 0, "minor": 0, "observation": 0}
    for dev in deviations:
        sev = dev.get("severity", "").upper()
        if sev == "CRITICAL":
            summary["critical"] += 1
        elif sev == "MAJOR":
            summary["major"] += 1
        elif sev == "MINOR":
            summary["minor"] += 1
        elif sev == "OBSERVATION":
            summary["observation"] += 1
    return summary


def _log_agent_run_compliance_agent(
    agent_run_id: str,
    started_ts: str,
    po_id: str,
    status: str = "completed",
    vendor_name: str = "",
    num_clauses: int = 0,
    num_requirements: int = 0,
    summary: Dict = None,
    num_ncrs: int = 0,
    processing_ms: float = 0.0,
    error: str = None,
) -> None:
    summary = summary or {}
    db = get_db()
    try:
        if status == "completed":
            input_summary = f"PO={po_id} vendor={vendor_name} clauses={num_clauses} reqs={num_requirements}"
            output_summary = (
                f"{summary.get('total', 0)} deviations: {summary.get('critical', 0)} CRIT, "
                f"{summary.get('major', 0)} MAJ, {summary.get('minor', 0)} MIN | {num_ncrs} NCRs | {processing_ms:.0f}ms"
            )
        else:
            input_summary = f"PO={po_id} — FAILED"
            output_summary = f"Error: {(error or '')[:200]}"

        db.execute(
            """
            INSERT OR REPLACE INTO agent_runs
            (id, agent_name, agent_version, trigger_event,
             input_summary, output_summary, status,
             started_ts, completed_ts, records_processed,
             records_created, error_text, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent_run_id, AGENT_NAME, AGENT_VERSION,
                f"compliance_check:po:{po_id}",
                input_summary, output_summary, status,
                started_ts, datetime.now(timezone.utc).isoformat(),
                num_requirements,
                summary.get("total", 0) + num_ncrs,
                error,
                json.dumps({"po_id": po_id, "processing_ms": processing_ms}),
            ),
        )
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log compliance agent run: {e}")
    finally:
        db.close()

# ==============================================================================
# INTEGRATED FROM: qa_agent.py
# ==============================================================================

"""
Mock Agent — DCPI.
This is a scaffolded agent file to demonstrate the 16-agent architecture.
Integration and logic are pending full enterprise implementation.
"""

import logging



# AGENT_NAME = "qa_agent"
# AGENT_VERSION = "0.1.0"

def process_request(query: str, context: dict = None) -> dict:
    """
    Mock entry point for qa_agent.
    """
    logger.info(f"qa_agent received query: {query[:50]}")
    return {
        "agent": AGENT_NAME,
        "status": "Not Implemented",
        "message": "This agent is scaffolded for the enterprise vision."
    }


# ==============================================================================
# INTEGRATED FROM: requirement_agent.py
# ==============================================================================

"""
Mock Agent — DCPI.
This is a scaffolded agent file to demonstrate the 16-agent architecture.
Integration and logic are pending full enterprise implementation.
"""

import logging



# AGENT_NAME = "requirement_agent"
# AGENT_VERSION = "0.1.0"

def process_request(query: str, context: dict = None) -> dict:
    """
    Mock entry point for requirement_agent.
    """
    logger.info(f"requirement_agent received query: {query[:50]}")
    return {
        "agent": AGENT_NAME,
        "status": "Not Implemented",
        "message": "This agent is scaffolded for the enterprise vision."
    }


