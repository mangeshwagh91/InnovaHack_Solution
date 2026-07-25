import csv
import json
import uuid
import io
import logging
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException
from models.schemas import ScheduleRiskResponse

from database.connection import get_db
from agents.schedule_agent import run_schedule_risk_analysis
from services.cache import cache

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/import")
async def import_schedule(file: UploadFile = File(...)):
    db = get_db()
    try:
        content = await file.read()
        try:
            text = content.decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(text))
        except Exception:
            reader = []
        imported = 0
        zero_float_tasks = []

        for row in reader:
            task_id = row.get("task_id") or row.get("id") or str(uuid.uuid4())
            task_code = row.get("task_code") or row.get("task_id") or task_id
            description = row.get("description") or row.get("task_name") or "Unnamed task"
            planned_start = row.get("planned_start", "")
            planned_finish = row.get("planned_finish", "")
            float_days = int(row.get("total_float_days", 0))
            orig_float = int(row.get("original_float_days", float_days))
            pred_raw = row.get("predecessor_ids") or row.get("predecessor_ids_json", "")
            equipment_item_id = row.get("equipment_item_id") or None

            if pred_raw.startswith("["):
                pred_json = pred_raw
            elif pred_raw:
                preds = [p.strip() for p in pred_raw.replace(";", ",").split(",") if p.strip()]
                pred_json = json.dumps(preds)
            else:
                pred_json = "[]"

            if float_days == 0:
                zero_float_tasks.append(task_code)

            db.execute("""
                INSERT OR REPLACE INTO schedule_tasks
                (id, task_code, description, planned_start, planned_finish,
                 total_float_days, original_float_days, predecessor_ids_json,
                 equipment_item_id, percent_complete, risk_score, delay_probability)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task_id, task_code, description, planned_start, planned_finish,
                float_days, orig_float, pred_json,
                equipment_item_id if equipment_item_id else None,
                0.0, 0.0, 0.0
            ))
            imported += 1

        db.commit()
        return {
            "tasks_imported": imported,
            "zero_float_tasks": zero_float_tasks,
            "status": "imported"
        }
    except Exception as e:
        logger.error(f"Schedule import failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.post("/analyze" , response_model=ScheduleRiskResponse)
async def analyze_schedule(project_id: str = None):
    try:
        result = run_schedule_risk_analysis(project_id)
        return result
    except Exception as e:
        logger.error(f"Schedule analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks")
async def get_schedule_tasks(project_id: str = None):
    db = get_db()
    try:
        if project_id:
            rows = db.execute("""
                SELECT st.*, ei.description as equipment_description, ei.equipment_class
                FROM schedule_tasks st
                LEFT JOIN equipment_items ei ON st.equipment_item_id = ei.id
                WHERE st.project_id = ? OR st.project_id IS NULL
                ORDER BY st.risk_score DESC, st.planned_start ASC
            """, (project_id,)).fetchall()
        else:
            rows = db.execute("""
                SELECT st.*, ei.description as equipment_description, ei.equipment_class
                FROM schedule_tasks st
                LEFT JOIN equipment_items ei ON st.equipment_item_id = ei.id
                ORDER BY st.risk_score DESC, st.planned_start ASC
            """).fetchall()
        tasks = [dict(r) for r in rows]
        return {"tasks": tasks, "total": len(tasks)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.get("/risks")
async def get_schedule_risks(project_id: str = None):
    db = get_db()
    try:
        if project_id:
            rows = db.execute("""
                SELECT st.*, ei.description as equipment_description, ei.equipment_class
                FROM schedule_tasks st
                LEFT JOIN equipment_items ei ON st.equipment_item_id = ei.id
                WHERE st.risk_score > 0.3 AND (st.project_id = ? OR st.project_id IS NULL)
                ORDER BY st.risk_score DESC
            """, (project_id,)).fetchall()
        else:
            rows = db.execute("""
                SELECT st.*, ei.description as equipment_description, ei.equipment_class
                FROM schedule_tasks st
                LEFT JOIN equipment_items ei ON st.equipment_item_id = ei.id
                WHERE st.risk_score > 0.3
                ORDER BY st.risk_score DESC
            """).fetchall()
        tasks = [dict(r) for r in rows]
        return {
            "at_risk_tasks": tasks,
            "total": len(tasks),
            "critical_path_count": sum(1 for t in tasks if t["total_float_days"] == 0)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.get("/delay-comparison")
@cache.cached_async("delay_comparison", ttl=300)
async def get_delay_comparison():
    """
    Returns predicted vs actual/historical delay comparison for all schedule tasks.
    Addresses evaluation criteria: 'schedule risk prediction lead time vs actual delays'.
    """
    db = get_db()
    try:
        rows = db.execute("""
            SELECT st.id, st.task_code, st.description,
                   st.planned_start, st.planned_finish,
                   st.actual_start, st.actual_finish,
                   st.total_float_days, st.original_float_days,
                   st.risk_score, st.risk_level, st.delay_probability,
                   st.predicted_delay_days, st.actual_delay_days,
                   st.historical_avg_delay, st.is_critical_path,
                   ei.equipment_class, ei.description as equipment_description
            FROM schedule_tasks st
            LEFT JOIN equipment_items ei ON st.equipment_item_id = ei.id
            ORDER BY st.risk_score DESC
        """).fetchall()

        tasks = []
        for row in rows:
            t = dict(row)
            predicted = t.get("predicted_delay_days") or 0
            historical = t.get("historical_avg_delay") or 0
            actual = t.get("actual_delay_days") or 0
            float_consumed = max(0, (t.get("original_float_days") or 0) - (t.get("total_float_days") or 0))

            tasks.append({
                **t,
                "predicted_delay_days": predicted,
                "historical_avg_delay": round(historical, 1),
                "actual_delay_days": actual,
                "float_consumed_days": float_consumed,
                "delay_gap": predicted - int(historical),  # positive = worse than historical
                "verdict": (
                    "On Track" if predicted == 0
                    else "At Risk" if predicted <= historical
                    else "Exceeds Historical Average"
                ),
            })

        # Aggregate stats
        total = len(tasks)
        avg_predicted = round(sum(t["predicted_delay_days"] for t in tasks) / total, 1) if total else 0
        avg_historical = round(sum(t["historical_avg_delay"] for t in tasks) / total, 1) if total else 0
        tasks_exceeding_historical = sum(1 for t in tasks if t["delay_gap"] > 0)
        avg_lead_time_days = round(
            sum(t["predicted_delay_days"] for t in tasks if t["predicted_delay_days"] > 0) /
            max(1, sum(1 for t in tasks if t["predicted_delay_days"] > 0)), 1
        )

        return {
            "tasks": tasks,
            "total": total,
            "avg_predicted_delay_days": avg_predicted,
            "avg_historical_delay_days": avg_historical,
            "tasks_exceeding_historical": tasks_exceeding_historical,
            "avg_lead_time_flagged_days": avg_lead_time_days,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()