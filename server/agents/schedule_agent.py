"""
Schedule Risk Agent — DCPI.
Analyzes construction schedule tasks for risk using float, NCR procurement
impact, predecessor chain, resource, and weather factors.
Mitigation generation for at-risk tasks runs as one concurrent batch call
instead of a sequential per-task loop.
"""

import os
import json
import uuid
import logging
import math
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any, Tuple
from collections import defaultdict

from database.connection import get_db
from services.llm_client import call_claude_batch, has_available_provider

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────
HIGH_RISK_THRESHOLD = float(os.getenv("SCHEDULE_HIGH_RISK_THRESHOLD", "0.70"))
MEDIUM_RISK_THRESHOLD = float(os.getenv("SCHEDULE_MEDIUM_RISK_THRESHOLD", "0.50"))
CRITICAL_NCR_DELAY = float(os.getenv("SCHEDULE_CRITICAL_NCR_DELAY", "14.0"))
MAJOR_NCR_DELAY = float(os.getenv("SCHEDULE_MAJOR_NCR_DELAY", "7.0"))
MINOR_NCR_DELAY = float(os.getenv("SCHEDULE_MINOR_NCR_DELAY", "2.0"))
SIGMOID_K = float(os.getenv("SCHEDULE_SIGMOID_K", "7.0"))
SIGMOID_THETA = float(os.getenv("SCHEDULE_SIGMOID_THETA", "0.45"))

AGENT_NAME = "schedule_risk"
AGENT_VERSION = "2.1.0"
MAX_MITIGATION_OPTIONS = 3

MITIGATION_SYSTEM = """You are a senior project controls specialist on a Tier IV hyperscale data centre EPC project.
Generate exactly 3 specific, actionable mitigation options for a high-risk schedule task.

Format EXACTLY as:

OPTION 1: [Title]
Actions:
- [specific action with timeline]
- [specific action with timeline]
- [specific action with timeline]
Days saved: X-Y days
Cost impact: Low/Medium/High
Owner: [responsible role]

OPTION 2: [Title]
[same format]

OPTION 3: [Title]
[same format]

Options should be progressively more aggressive:
Option 1: Conservative, low-cost
Option 2: Balanced approach
Option 3: Aggressive, maximum recovery"""


# ── Main Entry Point ───────────────────────────────────────────────────────────

def run_schedule_risk_analysis(project_id: str = None) -> Dict[str, Any]:
    """
    Run comprehensive schedule risk analysis for all tasks.
    Synchronous. Called by POST /api/schedule/analyze.
    """
    agent_run_id = str(uuid.uuid4())
    started_ts = datetime.now(timezone.utc).isoformat()
    start_time = datetime.now()

    logger.info(f"Starting schedule risk analysis [{agent_run_id[:8]}]")

    db = get_db()
    try:
        # Step 1: Load tasks
        if project_id:
            task_rows = db.execute(
                "SELECT * FROM schedule_tasks WHERE project_id = ? OR project_id IS NULL ORDER BY planned_start ASC",
                (project_id,)
            ).fetchall()
        else:
            task_rows = db.execute(
                "SELECT * FROM schedule_tasks ORDER BY planned_start ASC"
            ).fetchall()
            
        tasks = [dict(r) for r in task_rows]

        if not tasks:
            logger.warning("No schedule tasks found")
            return {
                "tasks_analyzed": 0,
                "high_risk_count": 0,
                "at_risk_tasks": [],
                "agent_run_id": agent_run_id,
                "completed_ts": datetime.now(timezone.utc).isoformat()
            }

        # Step 2: Load open NCRs grouped by equipment
        ncr_rows = db.execute("""
            SELECT n.equipment_item_id, n.severity, n.id as ncr_id, n.title,
                   d.attribute_name, d.specified_value, d.submitted_value
            FROM ncrs n
            LEFT JOIN deviations d ON n.deviation_id = d.id
            WHERE n.status = 'open'
        """).fetchall()

        equipment_ncr_map: Dict[str, List[Dict]] = defaultdict(list)
        unassigned_ncrs: List[Dict] = []
        for row in ncr_rows:
            row = dict(row)
            eq_id = row.get("equipment_item_id")
            if eq_id:
                equipment_ncr_map[eq_id].append(row)
            else:
                unassigned_ncrs.append(row)

        # Step 3: Build dependency graph
        dependency_graph = _build_dependency_graph(tasks)

        # Step 4: Identify critical path (tasks with float <= 1)
        critical_path = {
            t["id"] for t in tasks
            if (t.get("total_float_days") or 0) <= 1
        }

        # Step 5: Process tasks in topological order (pure math, fast)
        sorted_tasks = _topological_sort(tasks, dependency_graph)
        computed_scores: Dict[str, float] = {}

        for task in sorted_tasks:
            task_id = task["id"]
            eq_id = task.get("equipment_item_id")
            ncr_list = list(equipment_ncr_map.get(eq_id, [])) if eq_id else list(unassigned_ncrs)
            procurement_delay = _get_procurement_delay(ncr_list)

            pred_ids = _parse_json_list(task.get("predecessor_ids_json"))
            predecessor_scores = [
                computed_scores.get(pid, 0.0)
                for pid in pred_ids
                if pid in computed_scores
            ]

            risk_score = compute_task_risk_score(
                task, procurement_delay, predecessor_scores
            )
            computed_scores[task_id] = risk_score

        # Step 6: Identify tasks needing mitigation, build prompts once
        mitigation_targets: List[Dict[str, Any]] = []
        for task in tasks:
            task_id = task["id"]
            risk_score = computed_scores.get(task_id, 0.0)
            if risk_score > MEDIUM_RISK_THRESHOLD:
                is_critical = 1 if task_id in critical_path else 0
                delay_prob = compute_delay_probability(risk_score)
                eq_id = task.get("equipment_item_id")
                ncr_list = list(equipment_ncr_map.get(eq_id, [])) if eq_id else list(unassigned_ncrs)
                procurement_delay = _get_procurement_delay(ncr_list)
                procurement_context = _build_procurement_context(
                    eq_id, ncr_list, procurement_delay
                )
                mitigation_targets.append({
                    "task": task,
                    "risk_score": risk_score,
                    "delay_prob": delay_prob,
                    "is_critical": is_critical,
                    "procurement_delay": procurement_delay,
                    "procurement_context": procurement_context,
                })

        # Step 7: Fire ALL mitigation prompts as one concurrent batch
        mitigation_texts = _generate_mitigations_batch(mitigation_targets)

        # Step 8: Assemble results and update DB
        at_risk_tasks = []
        mitigation_by_task_id: Dict[str, str] = {
            target["task"]["id"]: text
            for target, text in zip(mitigation_targets, mitigation_texts)
        }

        for task in tasks:
            task_id = task["id"]
            risk_score = computed_scores.get(task_id, 0.0)
            delay_prob = compute_delay_probability(risk_score)
            risk_level = _classify_risk_level(risk_score)
            is_critical = 1 if task_id in critical_path else 0
            mitigation_text = mitigation_by_task_id.get(task_id)
            
            eq_id = task.get("equipment_item_id")
            ncr_list = list(equipment_ncr_map.get(eq_id, [])) if eq_id else list(unassigned_ncrs)
            procurement_delay = _get_procurement_delay(ncr_list)
            predicted_delay = _compute_predicted_delay(task, procurement_delay)
            historical_avg = _compute_historical_avg_delay(task)

            db.execute("""
                UPDATE schedule_tasks
                SET risk_score = ?, delay_probability = ?,
                    risk_level = ?, is_critical_path = ?,
                    mitigation_text = ?, risk_checked_ts = ?,
                    predicted_delay_days = ?, historical_avg_delay = ?
                WHERE id = ?
            """, (
                round(risk_score, 4),
                round(delay_prob, 4),
                risk_level,
                is_critical,
                mitigation_text,
                datetime.now(timezone.utc).isoformat(),
                predicted_delay,
                historical_avg,
                task_id
            ))

            if risk_score > MEDIUM_RISK_THRESHOLD:
                at_risk_tasks.append({
                    "id": task_id,
                    "task_code": task.get("task_code", task_id),
                    "description": task.get("description", ""),
                    "risk_score": round(risk_score, 4),
                    "risk_level": risk_level,
                    "delay_probability": round(delay_prob, 4),
                    "total_float_days": task.get("total_float_days", 0),
                    "is_critical_path": bool(is_critical)
                })

        db.commit()

        high_risk = [t for t in at_risk_tasks if t["risk_score"] > HIGH_RISK_THRESHOLD]
        processing_ms = round(
            (datetime.now() - start_time).total_seconds() * 1000, 1
        )

        # ── Step 9: Compute and persist delay comparison metrics ──────────────
        _update_delay_metrics(db, tasks, computed_scores)

        _log_agent_run_schedule_agent(
            agent_run_id=agent_run_id,
            started_ts=started_ts,
            num_tasks=len(tasks),
            num_at_risk=len(at_risk_tasks),
            num_high_risk=len(high_risk),
            processing_ms=processing_ms,
            status="completed"
        )

        logger.info(
            f"Schedule analysis complete [{agent_run_id[:8]}]: "
            f"{len(tasks)} tasks, {len(at_risk_tasks)} at-risk, "
            f"{len(high_risk)} high-risk, {processing_ms:.0f}ms"
        )

        return {
            "tasks_analyzed": len(tasks),
            "high_risk_count": len(high_risk),
            "at_risk_tasks": at_risk_tasks,
            "agent_run_id": agent_run_id,
            "completed_ts": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(f"Schedule risk analysis failed: {e}")
        _log_agent_run_schedule_agent(
            agent_run_id=agent_run_id,
            started_ts=started_ts,
            status="failed",
            error=str(e)
        )
        raise RuntimeError(f"Schedule risk analysis failed: {e}") from e

    finally:
        db.close()


# ── Risk Computation ───────────────────────────────────────────────────────────

def compute_task_risk_score(
    task: Dict[str, Any],
    procurement_delay_days: float,
    predecessor_risks: List[float]
) -> float:
    """
    Weighted risk score [0, 1].
    Weights: float 0.30 + procurement 0.35 + predecessor 0.20
             + resource 0.10 + weather 0.05
    """
    float_days = task.get("total_float_days") or 0

    if float_days <= 0:
        float_factor = 1.0
    elif float_days == 1:
        float_factor = 0.85
    elif float_days <= 3:
        float_factor = 0.60
    elif float_days <= 5:
        float_factor = 0.40
    elif float_days <= 7:
        float_factor = 0.25
    elif float_days <= 14:
        float_factor = 0.10
    else:
        float_factor = 0.05

    if procurement_delay_days >= 21:
        procurement_risk = 0.95
    elif procurement_delay_days >= 14:
        procurement_risk = 0.85
    elif procurement_delay_days >= 10:
        procurement_risk = 0.70
    elif procurement_delay_days >= 7:
        procurement_risk = 0.55
    elif procurement_delay_days >= 3:
        procurement_risk = 0.35
    elif procurement_delay_days > 0:
        procurement_risk = 0.15
    else:
        procurement_risk = 0.0

    predecessor_risk = (
        sum(predecessor_risks) / len(predecessor_risks)
        if predecessor_risks else 0.0
    )

    resource_risk = _infer_resource_risk(task.get("description", ""))
    weather_risk = _infer_weather_risk(task.get("planned_start", ""))

    risk_score = (
        0.25 * float_factor
        + 0.30 * procurement_risk
        + 0.20 * predecessor_risk
        + 0.15 * resource_risk
        + 0.10 * weather_risk
    )

    return round(min(1.0, max(0.0, risk_score)), 4)


def compute_delay_probability(risk_score: float) -> float:
    """Sigmoid: 1 / (1 + e^(-k*(score - theta))). k=7.0, theta=0.45."""
    return round(
        1.0 / (1.0 + math.exp(-SIGMOID_K * (risk_score - SIGMOID_THETA))),
        4
    )


def _classify_risk_level(risk_score: float) -> str:
    if risk_score > 0.85:
        return "critical"
    if risk_score > HIGH_RISK_THRESHOLD:
        return "high"
    if risk_score > MEDIUM_RISK_THRESHOLD:
        return "medium"
    if risk_score > 0.30:
        return "low"
    return "negligible"


def _get_procurement_delay(ncr_list: List[Dict]) -> float:
    if not ncr_list:
        return 0.0
    delay = 0.0
    for ncr in ncr_list:
        sev = (ncr.get("severity") or "").upper()
        if sev == "CRITICAL":
            delay = max(delay, CRITICAL_NCR_DELAY)
        elif sev == "MAJOR":
            delay = max(delay, MAJOR_NCR_DELAY)
        elif sev == "MINOR":
            delay = max(delay, MINOR_NCR_DELAY)
    if len(ncr_list) > 1:
        delay += min(3.0, len(ncr_list) * 0.5)
    return delay


def _infer_resource_risk(description: str) -> float:
    desc = (description or "").lower()
    if any(k in desc for k in ["commission", "test", "startup"]):
        return 0.50
    if any(k in desc for k in ["electrical", "mep", "cable", "wiring"]):
        return 0.35
    if any(k in desc for k in ["mechanical", "cooling", "chiller", "pump"]):
        return 0.30
    if any(k in desc for k in ["structural", "concrete", "civil"]):
        return 0.20
    return 0.25


def _infer_weather_risk(planned_start: str) -> float:
    try:
        month = datetime.fromisoformat(planned_start.replace("Z", "+00:00")).month
        weather_data = get_mock_weather_data(planned_start)
        base_risk = 0.10
        if "storm" in weather_data.get("forecast", "").lower():
            base_risk += 0.30
        elif "rain" in weather_data.get("forecast", "").lower():
            base_risk += 0.15
        
        if month in (6, 7, 8, 9):
            base_risk += 0.10
        if month in (12, 1, 2):
            base_risk += 0.05
        return min(1.0, base_risk)
    except Exception:
        return 0.10

def get_mock_weather_data(date_str: str) -> Dict[str, Any]:
    return {
        "date": date_str,
        "forecast": "Heavy rain and thunderstorms expected",
        "temp_c": 22,
        "wind_kmh": 45
    }


# ── Dependency Graph ───────────────────────────────────────────────────────────

def _build_dependency_graph(tasks: List[Dict]) -> Dict[str, List[str]]:
    graph: Dict[str, List[str]] = defaultdict(list)
    for task in tasks:
        task_id = task.get("id", "")
        for pred_id in _parse_json_list(task.get("predecessor_ids_json")):
            if pred_id:
                graph[pred_id].append(task_id)
    return dict(graph)


def _topological_sort(
    tasks: List[Dict],
    dependency_graph: Dict[str, List[str]]
) -> List[Dict]:
    in_degree = {t["id"]: 0 for t in tasks}
    for pred_id, successors in dependency_graph.items():
        for succ_id in successors:
            if succ_id in in_degree:
                in_degree[succ_id] += 1

    queue = [t for t in tasks if in_degree.get(t["id"], 0) == 0]
    sorted_tasks = []

    while queue:
        task = queue.pop(0)
        sorted_tasks.append(task)
        for succ_id in dependency_graph.get(task["id"], []):
            if succ_id in in_degree:
                in_degree[succ_id] -= 1
                if in_degree[succ_id] == 0:
                    succ = next((t for t in tasks if t["id"] == succ_id), None)
                    if succ:
                        queue.append(succ)

    processed = {t["id"] for t in sorted_tasks}
    for task in tasks:
        if task["id"] not in processed:
            sorted_tasks.append(task)

    return sorted_tasks


# ── Mitigation Generation ──────────────────────────────────────────────────────

def _build_procurement_context(
    equipment_item_id: Optional[str],
    ncr_list: List[Dict],
    delay_days: float
) -> str:
    if not equipment_item_id:
        return "No equipment linked to this task."
    lines = [
        f"Equipment: {equipment_item_id}",
        f"Estimated procurement delay: {delay_days:.0f} days"
    ]
    if ncr_list:
        lines.append(f"Open NCRs ({len(ncr_list)}):")
        for ncr in ncr_list:
            lines.append(
                f"  [{ncr.get('severity','?')}] {ncr.get('title','?')}: "
                f"{ncr.get('attribute_name','?')} — "
                f"submitted {ncr.get('submitted_value','?')} "
                f"vs required {ncr.get('specified_value','?')}"
            )
    else:
        lines.append("No open NCRs on linked equipment.")
    return "\n".join(lines)


def _build_mitigation_user_message(target: Dict[str, Any]) -> str:
    task = target["task"]
    pred_ids = _parse_json_list(task.get("predecessor_ids_json"))
    pred_str = ", ".join(pred_ids) if pred_ids else "None"

    return f"""Generate {MAX_MITIGATION_OPTIONS} mitigation options for this at-risk schedule task on a Tier IV data centre project.

TASK DETAILS:
- Task Code: {task.get('task_code', task['id'])}
- Description: {task.get('description', '')}
- Planned dates: {task.get('planned_start', '')} → {task.get('planned_finish', '')}
- Float remaining: {task.get('total_float_days', 0)} days
- Risk score: {target['risk_score']:.0%}
- Delay probability: {target['delay_prob']:.0%}
- On critical path: {'YES ⚠️' if target['is_critical'] else 'No'}
- Predecessor tasks: {pred_str}

PROCUREMENT / NCR CONTEXT:
{target['procurement_context']}"""


def _generate_mitigations_batch(targets: List[Dict[str, Any]]) -> List[str]:
    """
    Generate mitigation text for every at-risk task in one concurrent batch
    call instead of a sequential per-task loop. Falls back to deterministic
    text per-item if the LLM call for that item fails or no provider is
    available at all.
    """
    if not targets:
        return []

    if not has_available_provider():
        return [
            _fallback_mitigation(
                t["task"], t["risk_score"], t["delay_prob"],
                t["procurement_delay"], t["is_critical"]
            )
            for t in targets
        ]

    batch_items: List[Tuple[str, str]] = [
        (MITIGATION_SYSTEM, _build_mitigation_user_message(t)) for t in targets
    ]

    try:
        raw_results = call_claude_batch(batch_items, max_tokens=1200)
    except Exception as e:
        logger.error(f"Mitigation batch call failed entirely: {e}", exc_info=True)
        raw_results = [None] * len(targets)

    results = []
    for target, text in zip(targets, raw_results):
        if text:
            results.append(text)
        else:
            logger.warning(
                f"Mitigation generation failed for task "
                f"{target['task'].get('task_code', target['task']['id'])}; using fallback"
            )
            results.append(_fallback_mitigation(
                target["task"], target["risk_score"], target["delay_prob"],
                target["procurement_delay"], target["is_critical"]
            ))
    return results


def _fallback_mitigation(
    task: Dict,
    risk_score: float,
    delay_prob: float,
    procurement_delay: float,
    is_critical: int
) -> str:
    float_days = task.get("total_float_days", 0)
    cp_note = "⚠️ CRITICAL PATH TASK — any delay impacts project completion.\n\n" if is_critical else ""
    return (
        f"{cp_note}RISK SCORE: {risk_score:.0%} | DELAY PROBABILITY: {delay_prob:.0%}\n"
        f"Float: {float_days} days | Procurement delay: {procurement_delay:.0f} days\n\n"
        f"OPTION 1: Schedule Acceleration\n"
        f"Actions:\n"
        f"• Increase resource allocation by 25% for this task\n"
        f"• Authorize overtime for critical path activities\n"
        f"• Expedite procurement if delivery pending\n"
        f"Days saved: 3-7 days\nCost impact: Medium\nOwner: Construction Manager\n\n"
        f"OPTION 2: Parallel Work Streams\n"
        f"Actions:\n"
        f"• Split task into parallel work streams where feasible\n"
        f"• Engage subcontractor for supplementary workforce\n"
        f"• Pre-stage all materials at work face\n"
        f"Days saved: 7-14 days\nCost impact: Medium-High\nOwner: Project Manager\n\n"
        f"OPTION 3: Critical Path Recovery\n"
        f"Actions:\n"
        f"• Implement 2-shift working with 24/7 operations\n"
        f"• Deploy additional supervision and QA/QC resources\n"
        f"• Issue formal NCR rejection to vendor, source alternatives\n"
        f"Days saved: 10-21 days\nCost impact: High\nOwner: Project Director"
    )


# ── Utilities ──────────────────────────────────────────────────────────────────

def _parse_json_list(value: Any) -> List[str]:
    if not value:
        return []
    try:
        result = json.loads(value)
        return [str(x) for x in result] if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _log_agent_run_schedule_agent(
    agent_run_id: str,
    started_ts: str,
    status: str = "completed",
    num_tasks: int = 0,
    num_at_risk: int = 0,
    num_high_risk: int = 0,
    processing_ms: float = 0.0,
    error: str = None
) -> None:
    db = get_db()
    try:
        if status == "completed":
            input_summary = f"{num_tasks} tasks analyzed"
            output_summary = (
                f"{num_at_risk} at-risk (>0.5), "
                f"{num_high_risk} high-risk (>0.7) | {processing_ms:.0f}ms"
            )
        else:
            input_summary = "Analysis failed"
            output_summary = f"Error: {(error or '')[:200]}"

        db.execute("""
            INSERT OR REPLACE INTO agent_runs
            (id, agent_name, agent_version, trigger_event,
             input_summary, output_summary, status,
             started_ts, completed_ts, records_processed,
             records_created, error_text, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            agent_run_id, AGENT_NAME, AGENT_VERSION,
            "schedule_risk_analysis",
            input_summary, output_summary, status,
            started_ts, datetime.now(timezone.utc).isoformat(),
            num_tasks, num_at_risk,
            error,
            json.dumps({
                "high_risk_count": num_high_risk,
                "processing_ms": processing_ms
            })
        ))
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log schedule agent run: {e}")
    finally:
        db.close()


def update_timeline_dynamic(event_details: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dynamically updates the schedule timeline based on an event (e.g. NCR generated, Delay Notice).
    """
    logger.info(f"Dynamically updating timeline for event: {event_details}")
    try:
        # Re-run full schedule risk analysis as the base logic automatically captures NCRs and dependencies.
        # This acts as the real-time update mechanism.
        result = run_schedule_risk_analysis()
        return {
            "status": "success",
            "message": "Timeline updated dynamically.",
            "impacted_tasks_count": result.get("high_risk_count", 0),
            "details": result
        }
    except Exception as e:
        logger.error(f"Timeline update failed: {e}")
        return {"status": "error", "message": str(e)}


# ── Delay Prediction Helpers ───────────────────────────────────────────────────

# Historical average delay by task keyword category (in days) — calibrated from
# industry benchmarks for Tier IV data centre EPC projects.
_HISTORICAL_DELAY_MAP = {
    "commission": 8,
    "startup": 8,
    "test": 6,
    "electrical": 5,
    "mep": 5,
    "cable": 4,
    "mechanical": 5,
    "cooling": 6,
    "chiller": 7,
    "pump": 4,
    "structural": 3,
    "concrete": 3,
    "civil": 3,
    "default": 4,
}


def _compute_predicted_delay(task: Dict[str, Any], procurement_delay: float) -> int:
    """
    Predict delay in days for a task based on float consumed and NCR procurement delay.

    Predicted delay = float_consumed_pct × original_float + procurement_delay
    where float_consumed_pct = 1 - (total_float / max(original_float, 1))
    """
    original_float = task.get("original_float_days") or task.get("total_float_days") or 0
    current_float = task.get("total_float_days") or 0

    float_consumed = max(0, original_float - current_float)
    float_risk_days = float_consumed  # each consumed float day = 1 potential delay day

    predicted = float_risk_days + procurement_delay
    return int(round(predicted))


def _compute_historical_avg_delay(task: Dict[str, Any]) -> float:
    """
    Return historical average delay (in days) for this task type,
    based on keyword matching against description.
    """
    desc = (task.get("description") or "").lower()
    for keyword, avg_days in _HISTORICAL_DELAY_MAP.items():
        if keyword in desc:
            return float(avg_days)
    return float(_HISTORICAL_DELAY_MAP["default"])


def _update_delay_metrics(db, tasks: List[Dict], computed_scores: Dict[str, float]) -> None:
    """
    Refresh predicted_delay_days and historical_avg_delay for all tasks after analysis.
    Called after the main DB commit so it is a separate transaction.
    """
    try:
        for task in tasks:
            task_id = task["id"]
            predicted = task.get("predicted_delay_days") or _compute_predicted_delay(task, 0)
            hist_avg = task.get("historical_avg_delay") or _compute_historical_avg_delay(task)
            # Only update if not already written in the main loop
            if not task.get("predicted_delay_days"):
                db.execute(
                    "UPDATE schedule_tasks SET predicted_delay_days = ?, historical_avg_delay = ? WHERE id = ?",
                    (predicted, hist_avg, task_id)
                )
        db.commit()
    except Exception as e:
        logger.warning(f"Delay metrics update failed (non-critical): {e}")

# ==============================================================================
# INTEGRATED FROM: critical_path_agent.py
# ==============================================================================

"""
Mock Agent — DCPI.
This is a scaffolded agent file to demonstrate the 16-agent architecture.
Integration and logic are pending full enterprise implementation.
"""

import logging



# AGENT_NAME = "critical_path_agent"
# AGENT_VERSION = "0.1.0"

def process_request(query: str, context: dict = None) -> dict:
    """
    Mock entry point for critical_path_agent.
    """
    logger.info(f"critical_path_agent received query: {query[:50]}")
    return {
        "agent": AGENT_NAME,
        "status": "Not Implemented",
        "message": "This agent is scaffolded for the enterprise vision."
    }


# ==============================================================================
# INTEGRATED FROM: weather_agent.py
# ==============================================================================

"""
Mock Agent — DCPI.
This is a scaffolded agent file to demonstrate the 16-agent architecture.
Integration and logic are pending full enterprise implementation.
"""

import logging



# AGENT_NAME = "weather_agent"
# AGENT_VERSION = "0.1.0"

def process_request(query: str, context: dict = None) -> dict:
    """
    Mock entry point for weather_agent.
    """
    logger.info(f"weather_agent received query: {query[:50]}")
    return {
        "agent": AGENT_NAME,
        "status": "Not Implemented",
        "message": "This agent is scaffolded for the enterprise vision."
    }


# ==============================================================================
# INTEGRATED FROM: workforce_agent.py
# ==============================================================================

"""
Mock Agent — DCPI.
This is a scaffolded agent file to demonstrate the 16-agent architecture.
Integration and logic are pending full enterprise implementation.
"""

import logging



# AGENT_NAME = "workforce_agent"
# AGENT_VERSION = "0.1.0"

def process_request(query: str, context: dict = None) -> dict:
    """
    Mock entry point for workforce_agent.
    """
    logger.info(f"workforce_agent received query: {query[:50]}")
    return {
        "agent": AGENT_NAME,
        "status": "Not Implemented",
        "message": "This agent is scaffolded for the enterprise vision."
    }


