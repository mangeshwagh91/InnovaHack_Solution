"""
Commissioning Copilot Router — DCPI.
Endpoints for commissioning task management, checklist generation, and test records.
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from agents.commissioning_agent import (
    get_commissioning_tasks,
    generate_checklist,
    run_step,
    get_all_records,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class RunStepRequest(BaseModel):
    actual_value: str
    checked_by: Optional[str] = "QA Engineer"


@router.get("/tasks")
async def list_commissioning_tasks():
    """List all commissioning tasks with progress and step records."""
    try:
        return get_commissioning_tasks()
    except Exception as e:
        logger.error(f"Failed to list commissioning tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/checklist/generate/{task_id}")
async def generate_task_checklist(task_id: str):
    """Generate a commissioning checklist for a specific schedule task."""
    try:
        return generate_checklist(task_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Checklist generation failed for task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run/{task_id}/step/{step_number}")
async def run_commissioning_step(task_id: str, step_number: int, body: RunStepRequest):
    """Record the result of a commissioning test step."""
    try:
        return run_step(task_id, step_number, body.actual_value, body.checked_by)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Step execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/records")
async def get_commissioning_records():
    """Get all commissioning test records with summary statistics."""
    try:
        return get_all_records()
    except Exception as e:
        logger.error(f"Failed to get commissioning records: {e}")
        raise HTTPException(status_code=500, detail=str(e))
