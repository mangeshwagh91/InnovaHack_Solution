"""
Tenders Router
Handles vendor tender submissions and procurement intelligence (tender recommendations).
"""
import uuid
import json
from datetime import datetime, timezone
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException

from models.schemas import TenderCreate, TenderResponse
from database.connection import get_db
from agents.procurement_agent import analyze_bids

router = APIRouter()

@router.post("/create", response_model=TenderResponse)
def create_bid(tender: TenderCreate):
    # For a real implementation, vendor_id would come from JWT Auth Token.
    # We will simulate it by taking vendor_id from a header or just using a dummy one for now,
    # or actually we should add vendor_id to the schema since we are keeping it simple.
    
    db = get_db()
    try:
        # In a real app, we verify vendor_id exists
        
        bid_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        db.execute(
            "INSERT INTO tenders (id, project_id, vendor_id, price, lead_time_days, equipment_catalog_json, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (bid_id, tender.project_id, tender.vendor_id, tender.price, tender.lead_time_days, tender.equipment_catalog_json, "submitted", now)
        )
        db.commit()
        
        return {
            "id": bid_id,
            "project_id": tender.project_id,
            "vendor_id": tender.vendor_id,
            "price": tender.price,
            "lead_time_days": tender.lead_time_days,
            "equipment_catalog_json": tender.equipment_catalog_json,
            "status": "submitted",
            "created_at": now
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.get("/{project_id}", response_model=List[TenderResponse])
def get_project_bids(project_id: str):
    db = get_db()
    try:
        rows = db.execute("SELECT * FROM tenders WHERE project_id = ?", (project_id,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        db.close()


@router.patch("/update_status/{bid_id}")
def update_bid_status(bid_id: str, status: str):
    db = get_db()
    try:
        db.execute("UPDATE tenders SET status = ? WHERE id = ?", (status, bid_id))
        db.commit()
        return {"status": "success", "message": f"Tender updated to {status}"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()



@router.post("/recommend")
def recommend_bids(project_id: str):
    """Uses the Procurement Agent to analyze all tenders for a project from DB."""
    from agents.procurement_agent import analyze_bids
    from database.connection import get_db
    
    db = get_db()
    try:
        rows = db.execute("SELECT * FROM tenders WHERE project_id = ?", (project_id,)).fetchall()
        tenders = [dict(row) for row in rows]
    finally:
        db.close()
        
    if not tenders:
        raise HTTPException(status_code=404, detail="No tenders found for this project")

    try:
        result = analyze_bids(tenders)
        if result.get("bids_analyzed", 0) == 0:
            raise HTTPException(status_code=404, detail="No tenders found for this project")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

