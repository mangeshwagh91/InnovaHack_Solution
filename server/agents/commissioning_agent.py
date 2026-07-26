"""
Commissioning Copilot Agent — DCPI.
Guides commissioning test sequences for data centre equipment.
Auto-checks acceptance criteria, generates test records, flags non-conformances.
"""

import os
import json
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any

from database.connection import get_db
from services.llm_client import call_claude_json, has_available_provider
from services.vector_store import search_commissioning_checklists, CHROMADB_AVAILABLE

logger = logging.getLogger(__name__)

AGENT_NAME = "commissioning_copilot"
AGENT_VERSION = "1.0.0"

# Keywords that identify commissioning/test tasks in schedule
COMMISSIONING_KEYWORDS = [
    "commission", "test", "startup", "start-up", "start up",
    "energize", "energise", "iat", "sat", "pat", "fat",
    "acceptance test", "load test", "functional test",
    "inspection", "verification", "sign-off", "handover",
    "punch list", "pre-commissioning", "rite", "rfi",
]

# Standard step templates per equipment class
STEP_TEMPLATES: Dict[str, List[Dict]] = {
    "UPS": [
        {"step": 1, "name": "Pre-Power Safety Check", "type": "SAFETY",
         "criteria": "All protective earthing verified, no exposed live parts, PPE confirmed"},
        {"step": 2, "name": "Visual Inspection", "type": "INSPECTION",
         "criteria": "No physical damage, all connections torqued to spec, cable routing correct"},
        {"step": 3, "name": "Insulation Resistance Test", "type": "ELECTRICAL",
         "criteria": "IR > 1 MΩ at 500V DC on all phases"},
        {"step": 4, "name": "Bypass Mode Verification", "type": "FUNCTIONAL",
         "criteria": "Bypass transfer < 4ms with no load interruption"},
        {"step": 5, "name": "Battery Discharge Test", "type": "PERFORMANCE",
         "criteria": "Supports 100% rated load for minimum 10 minutes at full discharge"},
        {"step": 6, "name": "Input/Output Voltage Check", "type": "ELECTRICAL",
         "criteria": "Output voltage ±2% of nominal, THD < 2%"},
        {"step": 7, "name": "Alarm & Event Log Review", "type": "VERIFICATION",
         "criteria": "No critical alarms present, event log clear of faults"},
        {"step": 8, "name": "Load Bank Test — 50%", "type": "PERFORMANCE",
         "criteria": "Stable output at 50% load, efficiency > 94%"},
        {"step": 9, "name": "Load Bank Test — 100%", "type": "PERFORMANCE",
         "criteria": "Stable output at 100% load, no overtemp, efficiency > 92%"},
        {"step": 10, "name": "Commissioning Sign-off", "type": "SIGN_OFF",
         "criteria": "All steps PASS, test record countersigned by QA Engineer and Client Rep"},
    ],
    "PDU": [
        {"step": 1, "name": "Safety Isolation Verification", "type": "SAFETY",
         "criteria": "Lockout/Tagout applied, upstream breaker confirmed open"},
        {"step": 2, "name": "Torque Check — Busbars", "type": "INSPECTION",
         "criteria": "All busbar connections at specified torque (per manufacturer datasheet)"},
        {"step": 3, "name": "Phase Balancing Check", "type": "ELECTRICAL",
         "criteria": "Phase imbalance < 5% across all output branches"},
        {"step": 4, "name": "Breaker Trip Test", "type": "FUNCTIONAL",
         "criteria": "Each branch breaker trips correctly at rated overload within 2s"},
        {"step": 5, "name": "Metering Calibration", "type": "VERIFICATION",
         "criteria": "Current metering within ±1% of clamp meter reference"},
        {"step": 6, "name": "SNMP / BMS Integration Test", "type": "FUNCTIONAL",
         "criteria": "All power readings visible in DCIM within 5s polling interval"},
        {"step": 7, "name": "Sign-off", "type": "SIGN_OFF",
         "criteria": "All steps PASS, test sheet signed"},
    ],
    "COOLING": [
        {"step": 1, "name": "Refrigerant Leak Check", "type": "SAFETY",
         "criteria": "No refrigerant leaks detected, system at design pressure"},
        {"step": 2, "name": "Water Circuit Flush & Fill", "type": "PREPARATION",
         "criteria": "Circuit flushed 3×, water quality pH 7.0–8.5, inhibitor added"},
        {"step": 3, "name": "Pump Rotation Verification", "type": "MECHANICAL",
         "criteria": "All pump rotation confirmed correct before energisation"},
        {"step": 4, "name": "Flow Rate Commissioning", "type": "PERFORMANCE",
         "criteria": "Flow rate within ±10% of design per hydraulic balance sheet"},
        {"step": 5, "name": "Cooling Capacity Test", "type": "PERFORMANCE",
         "criteria": "Unit achieves rated kW capacity at design delta-T"},
        {"step": 6, "name": "Controls & BMS Integration", "type": "FUNCTIONAL",
         "criteria": "Temperature setpoint control confirmed, alarms visible in BMS"},
        {"step": 7, "name": "Sign-off", "type": "SIGN_OFF",
         "criteria": "All steps PASS"},
    ],
    "GENERATOR": [
        {"step": 1, "name": "Fuel System Check", "type": "PREPARATION",
         "criteria": "Fuel tank ≥ 80% full, no leaks, day tank operational"},
        {"step": 2, "name": "Coolant & Lube Oil Check", "type": "PREPARATION",
         "criteria": "Coolant and oil at manufacturer specified levels"},
        {"step": 3, "name": "No-Load Start & Run", "type": "FUNCTIONAL",
         "criteria": "Engine starts within 10s, stable idle, no alarms"},
        {"step": 4, "name": "Voltage & Frequency Check", "type": "ELECTRICAL",
         "criteria": "Output 400V ±2%, 50Hz ±0.5Hz within 15s of start"},
        {"step": 5, "name": "Load Test — 50%", "type": "PERFORMANCE",
         "criteria": "Stable at 50% rated load for 30 minutes, exhaust temp within limits"},
        {"step": 6, "name": "Load Test — 100%", "type": "PERFORMANCE",
         "criteria": "Stable at 100% rated load for 60 minutes, no derating"},
        {"step": 7, "name": "ATS Transfer Test", "type": "FUNCTIONAL",
         "criteria": "ATS picks up load within 10s of mains failure simulation"},
        {"step": 8, "name": "Sign-off", "type": "SIGN_OFF",
         "criteria": "All steps PASS, signed by commissioning engineer"},
    ],
    "DEFAULT": [
        {"step": 1, "name": "Pre-Commissioning Safety Check", "type": "SAFETY",
         "criteria": "All safety protocols verified, isolation confirmed"},
        {"step": 2, "name": "Visual & Mechanical Inspection", "type": "INSPECTION",
         "criteria": "No damage, correct installation per drawings"},
        {"step": 3, "name": "Functional Test", "type": "FUNCTIONAL",
         "criteria": "Unit operates within specified parameters"},
        {"step": 4, "name": "Performance Verification", "type": "PERFORMANCE",
         "criteria": "Meets minimum 95% of rated performance under test load"},
        {"step": 5, "name": "Integration Test", "type": "VERIFICATION",
         "criteria": "Correctly integrated with BMS/SCADA, alarms confirmed"},
        {"step": 6, "name": "Sign-off", "type": "SIGN_OFF",
         "criteria": "All steps PASS, signed by QA Engineer"},
    ],
}

LLM_CHECKLIST_SYSTEM = """You are a commissioning engineer for a Tier IV data centre EPC project.
Generate a commissioning test sequence for the given task.

Return ONLY valid JSON in this format:
{
  "steps": [
    {
      "step_number": 1,
      "step_name": "Step name",
      "step_type": "SAFETY|INSPECTION|ELECTRICAL|FUNCTIONAL|PERFORMANCE|VERIFICATION|SIGN_OFF",
      "acceptance_criteria": "Clear measurable acceptance criterion"
    }
  ],
  "total_steps": 6,
  "estimated_duration_hours": 4,
  "required_personnel": ["QA Engineer", "Site Supervisor"],
  "required_tools": ["Multimeter", "Clamp meter"]
}"""


# ── Main Entry Points ─────────────────────────────────────────────────────────

def get_commissioning_tasks() -> Dict[str, Any]:
    """Return all schedule tasks identified as commissioning tasks."""
    db = get_db()
    try:
        rows = db.execute("""
            SELECT st.*, ei.equipment_class, ei.description as equipment_description
            FROM schedule_tasks st
            LEFT JOIN equipment_items ei ON st.equipment_item_id = ei.id
            ORDER BY st.planned_start ASC
        """).fetchall()
        tasks = [dict(r) for r in rows]

        commissioning_tasks = []
        for task in tasks:
            desc = (task.get("description") or "").lower()
            if any(kw in desc for kw in COMMISSIONING_KEYWORDS):
                # Fetch existing records for this task
                records = db.execute(
                    "SELECT * FROM commissioning_records WHERE task_id = ? ORDER BY step_number",
                    (task["id"],)
                ).fetchall()
                task["commissioning_records"] = [dict(r) for r in records]
                task["total_steps"] = len(records)
                passed = sum(1 for r in records if dict(r).get("pass_fail") == "pass")
                task["steps_passed"] = passed
                task["completion_pct"] = round(passed / len(records) * 100, 1) if records else 0
                commissioning_tasks.append(task)

        # Summary stats
        total = len(commissioning_tasks)
        fully_complete = sum(1 for t in commissioning_tasks
                             if t["total_steps"] > 0 and t["completion_pct"] == 100)
        in_progress = sum(1 for t in commissioning_tasks
                          if 0 < t["completion_pct"] < 100)

        return {
            "commissioning_tasks": commissioning_tasks,
            "total": total,
            "fully_complete": fully_complete,
            "in_progress": in_progress,
            "not_started": total - fully_complete - in_progress,
            "pass_rate_pct": round(fully_complete / total * 100, 1) if total else 0,
        }
    finally:
        db.close()


def generate_checklist(task_id: str) -> Dict[str, Any]:
    """Generate a commissioning checklist for a specific task."""
    db = get_db()
    try:
        row = db.execute("""
            SELECT st.*, ei.equipment_class, ei.description as equip_desc
            FROM schedule_tasks st
            LEFT JOIN equipment_items ei ON st.equipment_item_id = ei.id
            WHERE st.id = ?
        """, (task_id,)).fetchone()

        if not row:
            raise ValueError(f"Task {task_id} not found")

        task = dict(row)
        equipment_class = (task.get("equipment_class") or "DEFAULT").upper()

        # Use equipment-specific template
        for key in STEP_TEMPLATES:
            if key in equipment_class:
                steps = STEP_TEMPLATES[key]
                break
        else:
            steps = STEP_TEMPLATES["DEFAULT"]
            
        # Try to retrieve specific checklist from ChromaDB
        if CHROMADB_AVAILABLE:
            try:
                chk_results = search_commissioning_checklists(equipment_class, n_results=1)
                if chk_results:
                    logger.info(f"Found ChromaDB checklist for {equipment_class}")
                    # Convert found text to basic steps for LLM enhancement or direct use
                    chk_text = chk_results[0]["text"]
                    # If we use LLM, we can pass this text to it
                    task["chroma_checklist_text"] = chk_text
            except Exception as e:
                logger.warning(f"ChromaDB checklist search failed: {e}")

        # Try LLM enhancement if available
        if has_available_provider():
            try:
                user_msg = (
                    f"Task: {task.get('description')}\n"
                    f"Equipment: {task.get('equip_desc', 'Unknown')}\n"
                    f"Class: {equipment_class}\n"
                    f"Planned: {task.get('planned_start')} → {task.get('planned_finish')}\n"
                )
                if task.get("chroma_checklist_text"):
                    user_msg += f"Use this retrieved checklist as a basis:\n{task['chroma_checklist_text']}\n"
                user_msg += f"Generate a detailed commissioning test sequence."
                result = call_claude_json(LLM_CHECKLIST_SYSTEM, user_msg, max_tokens=1500)
                if result.get("steps"):
                    steps = result["steps"]
                    # normalise key names
                    steps = [
                        {
                            "step": s.get("step_number", i + 1),
                            "name": s.get("step_name", f"Step {i+1}"),
                            "type": s.get("step_type", "FUNCTIONAL"),
                            "criteria": s.get("acceptance_criteria", "")
                        }
                        for i, s in enumerate(steps)
                    ]
            except Exception as e:
                logger.warning(f"LLM checklist generation failed, using template: {e}")

        # Delete old records and insert fresh checklist
        db.execute("DELETE FROM commissioning_records WHERE task_id = ?", (task_id,))
        for s in steps:
            db.execute("""
                INSERT INTO commissioning_records
                (id, task_id, step_number, step_name, step_type, acceptance_criteria, status)
                VALUES (?, ?, ?, ?, ?, ?, 'pending')
            """, (
                str(uuid.uuid4()),
                task_id,
                s.get("step", s.get("step_number", 1)),
                s.get("name", s.get("step_name", "")),
                s.get("type", s.get("step_type", "FUNCTIONAL")),
                s.get("criteria", s.get("acceptance_criteria", "")),
            ))
        db.commit()

        logger.info(f"Generated {len(steps)}-step checklist for task {task_id}")
        return {
            "task_id": task_id,
            "task_description": task.get("description"),
            "equipment_class": equipment_class,
            "steps_generated": len(steps),
            "status": "checklist_ready"
        }
    finally:
        db.close()


def run_step(task_id: str, step_number: int, actual_value: str, checked_by: str = "QA Engineer") -> Dict[str, Any]:
    """Record the result of a commissioning step (pass/fail)."""
    db = get_db()
    try:
        record = db.execute(
            "SELECT * FROM commissioning_records WHERE task_id = ? AND step_number = ?",
            (task_id, step_number)
        ).fetchone()

        if not record:
            raise ValueError(f"Step {step_number} not found for task {task_id}")

        record = dict(record)
        criteria = record.get("acceptance_criteria", "")

        # Auto-evaluate pass/fail
        pass_fail = _evaluate_pass_fail(actual_value, criteria)
        status = "complete"

        # Flag NCR for failed steps
        flagged_ncr_id = None
        if pass_fail == "fail":
            flagged_ncr_id = _raise_commissioning_ncr(db, task_id, record, actual_value)

        db.execute("""
            UPDATE commissioning_records
            SET actual_value = ?, pass_fail = ?, status = ?,
                flagged_ncr_id = ?, checked_by = ?, checked_ts = ?
            WHERE task_id = ? AND step_number = ?
        """, (
            actual_value, pass_fail, status,
            flagged_ncr_id, checked_by,
            datetime.now(timezone.utc).isoformat(),
            task_id, step_number
        ))
        db.commit()

        return {
            "task_id": task_id,
            "step_number": step_number,
            "step_name": record["step_name"],
            "actual_value": actual_value,
            "acceptance_criteria": criteria,
            "pass_fail": pass_fail,
            "flagged_ncr_id": flagged_ncr_id,
            "checked_ts": datetime.now(timezone.utc).isoformat()
        }
    finally:
        db.close()


def get_all_records() -> Dict[str, Any]:
    """Get all commissioning records with summary stats."""
    db = get_db()
    try:
        rows = db.execute("""
            SELECT cr.*, st.description as task_description, st.task_code,
                   ei.equipment_class
            FROM commissioning_records cr
            JOIN schedule_tasks st ON cr.task_id = st.id
            LEFT JOIN equipment_items ei ON st.equipment_item_id = ei.id
            ORDER BY cr.task_id, cr.step_number
        """).fetchall()

        records = [dict(r) for r in rows]
        total = len(records)
        passed = sum(1 for r in records if r["pass_fail"] == "pass")
        failed = sum(1 for r in records if r["pass_fail"] == "fail")
        pending = sum(1 for r in records if r["pass_fail"] == "pending")

        return {
            "records": records,
            "total": total,
            "passed": passed,
            "failed": failed,
            "pending": pending,
            "pass_rate_pct": round(passed / (passed + failed) * 100, 1) if (passed + failed) > 0 else 0,
        }
    finally:
        db.close()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _evaluate_pass_fail(actual_value: str, criteria: str) -> str:
    """Simple heuristic pass/fail evaluation."""
    actual_lower = (actual_value or "").lower().strip()
    # Explicit keywords
    if actual_lower in ("pass", "ok", "yes", "good", "conform", "confirmed", "verified", "complete"):
        return "pass"
    if actual_lower in ("fail", "failed", "no", "nok", "not ok", "reject", "rejected", "non-conform"):
        return "fail"
    # Numeric threshold evaluation
    try:
        val = float(actual_lower.replace(",", ".").split()[0])
        # Check criteria for ranges like "> 1" or "±2%"
        if ">" in criteria:
            threshold = float("".join(c for c in criteria.split(">")[1].split()[0] if c.isdigit() or c == "."))
            return "pass" if val > threshold else "fail"
        if "<" in criteria:
            threshold = float("".join(c for c in criteria.split("<")[1].split()[0] if c.isdigit() or c == "."))
            return "pass" if val < threshold else "fail"
    except Exception:
        pass
    # Default — if user provided a value assume pass unless explicitly indicated
    return "pass" if actual_lower else "pending"


def _raise_commissioning_ncr(db, task_id: str, record: Dict, actual_value: str) -> Optional[str]:
    """Create an NCR when a commissioning step fails."""
    try:
        # Get the task's PO if exists
        task_row = db.execute(
            "SELECT equipment_item_id FROM schedule_tasks WHERE id = ?", (task_id,)
        ).fetchone()
        eq_id = dict(task_row).get("equipment_item_id") if task_row else None

        # Need a real PO for the NCR; use first available PO for this equipment
        po_row = None
        if eq_id:
            po_row = db.execute(
                "SELECT id FROM purchase_orders WHERE equipment_item_id = ? LIMIT 1", (eq_id,)
            ).fetchone()

        if not po_row:
            po_row = db.execute("SELECT id FROM purchase_orders LIMIT 1").fetchone()

        if not po_row:
            logger.warning("No purchase order found for commissioning NCR; skipping NCR creation")
            return None

        po_id = dict(po_row)["id"]

        # Create deviation
        dev_id = str(uuid.uuid4())
        db.execute("""
            INSERT INTO deviations
            (id, po_id, attribute_name, specified_value, submitted_value,
             deviation_pct, severity, deviation_type, detected_ts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            dev_id, po_id,
            record["step_name"],
            record["acceptance_criteria"],
            actual_value,
            100.0,
            "MAJOR",
            "COMMISSIONING_FAIL",
            datetime.now(timezone.utc).isoformat()
        ))

        # Create NCR
        ncr_id = str(uuid.uuid4())
        db.execute("""
            INSERT INTO ncrs
            (id, deviation_id, po_id, equipment_item_id, title, description,
             severity, status, raised_ts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ncr_id, dev_id, po_id, eq_id,
            f"Commissioning FAIL: {record['step_name']}",
            f"Step {record['step_number']} failed. "
            f"Criteria: {record['acceptance_criteria']}. "
            f"Actual: {actual_value}",
            "MAJOR",
            "open",
            datetime.now(timezone.utc).isoformat()
        ))

        logger.info(f"Raised NCR {ncr_id} for failed commissioning step {record['step_name']}")
        return ncr_id
    except Exception as e:
        logger.error(f"Failed to raise commissioning NCR: {e}")
        return None
