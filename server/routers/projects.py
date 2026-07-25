"""
Projects Router
Handles CRUD operations for projects, including vendor-facing open projects.
"""
import uuid
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, HTTPException

from models.schemas import ProjectCreate, ProjectResponse
from database.connection import get_db

router = APIRouter()

@router.post("/", response_model=ProjectResponse)
def create_project(project: ProjectCreate):
    db = get_db()
    try:
        project_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        db.execute(
            "INSERT INTO projects (id, name, size_mw, deadline, budget, status, created_at, location, capacity_unit, equipment_budget, tier, description, pm) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (project_id, project.name, project.size_mw, project.deadline, project.budget, "active", now, project.location, project.capacity_unit, project.equipment_budget, project.tier, project.description, project.pm)
        )
        db.commit()
        
        return {
            "id": project_id,
            "name": project.name,
            "size_mw": project.size_mw,
            "deadline": project.deadline,
            "budget": project.budget,
            "status": "active",
            "created_at": now,
            "location": project.location,
            "capacity_unit": project.capacity_unit,
            "equipment_budget": project.equipment_budget,
            "tier": project.tier,
            "description": project.description,
            "pm": project.pm
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.get("/", response_model=List[ProjectResponse])
def get_all_projects():
    """List all projects (internal team)"""
    db = get_db()
    try:
        rows = db.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]
    finally:
        db.close()


@router.get("/open", response_model=List[ProjectResponse])
def get_open_projects():
    """List open projects for vendors"""
    db = get_db()
    try:
        rows = db.execute("SELECT * FROM projects WHERE status = 'active' ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]
    finally:
        db.close()


@router.patch("/{project_id}/status", response_model=ProjectResponse)
def update_project_status(project_id: str, status: str):
    """Update project status (active, paused, completed)"""
    db = get_db()
    try:
        if status not in ["active", "paused", "completed"]:
            raise HTTPException(status_code=400, detail="Invalid status")
        
        row = db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Project not found")
            
        db.execute("UPDATE projects SET status = ? WHERE id = ?", (status, project_id))
        db.commit()
        
        row = db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return dict(row)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.delete("/{project_id}")
def delete_project(project_id: str):
    """Delete a project and all its associated data"""
    db = get_db()
    try:
        # Check if project exists
        row = db.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Project not found")

        # Delete from all child tables first due to foreign keys
        
        # 1. Deviations (has po_id and spec_clause_id, but we'll delete by po_id)
        db.execute("DELETE FROM deviations WHERE po_id IN (SELECT id FROM purchase_orders WHERE project_id = ?)", (project_id,))
        
        # 2. NCRs (has deviation_id and po_id)
        db.execute("DELETE FROM ncrs WHERE po_id IN (SELECT id FROM purchase_orders WHERE project_id = ?)", (project_id,))
        
        # 3. RFIs
        db.execute("DELETE FROM rfis WHERE project_id = ?", (project_id,))
        
        # 4. Schedule tasks
        db.execute("DELETE FROM schedule_tasks WHERE project_id = ?", (project_id,))
        
        # 5. Purchase orders
        db.execute("DELETE FROM purchase_orders WHERE project_id = ?", (project_id,))
        
        # 6. Equipment items
        db.execute("DELETE FROM equipment_items WHERE project_id = ?", (project_id,))
        
        # 7. Spec clauses (via documents)
        db.execute("DELETE FROM spec_clauses WHERE document_id IN (SELECT id FROM documents WHERE project_id = ?)", (project_id,))
        
        # 8. Documents
        db.execute("DELETE FROM documents WHERE project_id = ?", (project_id,))
        
        # 9. Project
        db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        
        db.commit()
        
        return {"status": "success", "message": "Project deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
