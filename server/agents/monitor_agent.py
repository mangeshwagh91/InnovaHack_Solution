import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from database.connection import get_db

logger = logging.getLogger(__name__)

AGENT_NAME = "monitor_agent"
AGENT_VERSION = "1.0.0"


async def monitor_loop(interval_seconds: int = 60):
    """
    Background loop that polls the database, applies threshold rules,
    and writes to the alerts table.
    """
    logger.info(f"Monitor Agent started (polling every {interval_seconds}s)")
    while True:
        try:
            await asyncio.to_thread(_run_monitor_cycle)
        except asyncio.CancelledError:
            logger.info("Monitor Agent loop cancelled.")
            break
        except Exception as e:
            logger.error(f"Monitor Agent encountered an error: {e}")
        await asyncio.sleep(interval_seconds)


def _run_monitor_cycle():
    agent_run_id = str(uuid.uuid4())
    started_ts = datetime.now(timezone.utc).isoformat()
    start_time = datetime.now()
    db = get_db()
    alerts_created = 0
    try:
        # Example Rules (Phase 3 requirements mentioned reading ncrs, schedule_tasks, bids)
        
        # Rule 1: CRITICAL NCRs that are open
        ncrs = db.execute("SELECT id, project_id, title FROM ncrs WHERE status = 'open' AND severity = 'CRITICAL'").fetchall()
        for ncr in ncrs:
            if _create_alert(db, ncr["project_id"], "NCR_CRITICAL", "CRITICAL", f"Open CRITICAL NCR: {ncr['title']}", ncr["id"], "ncrs"):
                alerts_created += 1

        # Rule 2: High-risk schedule tasks
        tasks = db.execute("SELECT id, project_id, task_code, description FROM schedule_tasks WHERE risk_score > 0.85").fetchall()
        for task in tasks:
            if _create_alert(db, task["project_id"], "SCHEDULE_RISK", "MAJOR", f"Critical risk task: {task['task_code']} - {task['description']}", task["id"], "schedule_tasks"):
                alerts_created += 1

        # Rule 3: Bids without AI recommendation
        bids = db.execute("SELECT id, project_id FROM bids WHERE status = 'submitted' AND ai_recommendation IS NULL").fetchall()
        for bid in bids:
            if _create_alert(db, bid["project_id"], "BID_PENDING_REVIEW", "MINOR", f"New bid {bid['id'][:8]} pending AI review", bid["id"], "bids"):
                alerts_created += 1

        db.commit()
        
        processing_ms = round((datetime.now() - start_time).total_seconds() * 1000, 1)
        _log_agent_run(db, agent_run_id, started_ts, alerts_created, processing_ms)
        
    except Exception as e:
        logger.error(f"Error in monitor cycle: {e}")
        db.rollback()
        _log_agent_run(db, agent_run_id, started_ts, alerts_created, 0, error=str(e))
    finally:
        db.close()


def _create_alert(db, project_id, alert_type, severity, message, entity_id, entity_type) -> bool:
    """Creates an alert if it doesn't already exist for this entity and alert type."""
    existing = db.execute("SELECT id FROM alerts WHERE entity_id = ? AND alert_type = ?", (entity_id, alert_type)).fetchone()
    if existing:
        return False
    
    db.execute("""
        INSERT INTO alerts (id, project_id, alert_type, severity, message, entity_id, entity_type, created_ts)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(uuid.uuid4()),
        project_id,
        alert_type,
        severity,
        message,
        entity_id,
        entity_type,
        datetime.now(timezone.utc).isoformat()
    ))
    return True

def _log_agent_run(db, run_id: str, started: str, alerts_created: int, ms: float = 0.0, error: str = None):
    status = "failed" if error else "completed"
    try:
        db.execute('''
            INSERT INTO agent_runs
            (id, agent_name, agent_version, trigger_event, input_summary, output_summary, status, started_ts, completed_ts, records_processed, records_created, error_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            run_id, AGENT_NAME, AGENT_VERSION, "scheduled_poll", "Polling database for monitor rules",
            f"Created {alerts_created} alerts | {ms:.0f}ms" if status == "completed" else f"Failed: {(error or '')[:200]}",
            status, started, datetime.now(timezone.utc).isoformat(), 0, alerts_created, error
        ))
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log monitor agent: {e}")
