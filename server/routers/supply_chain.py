from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
import logging

from database.connection import get_db
from agents.supply_chain_agent import analyze_shipment_risk

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/shipments")
def get_all_shipments() -> Dict[str, Any]:
    db = get_db()
    try:
        rows = db.execute("SELECT * FROM shipments").fetchall()
        shipments = [dict(row) for row in rows]
        
        # Parse JSON fields
        import json
        for s in shipments:
            if s.get("ai_alternatives_json"):
                try:
                    s["ai_alternatives"] = json.loads(s["ai_alternatives_json"])
                except:
                    s["ai_alternatives"] = {}
                    
        return {"shipments": shipments, "total": len(shipments)}
    except Exception as e:
        logger.error(f"Error fetching shipments: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.post("/shipments/{shipment_id}/analyze")
def analyze_shipment(shipment_id: str) -> Dict[str, Any]:
    try:
        alternatives = analyze_shipment_risk(shipment_id)
        return {"status": "success", "alternatives": alternatives}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error analyzing shipment: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/alerts")
def get_supply_chain_alerts() -> List[Dict[str, Any]]:
    # Mock alerts since there is no alerts table currently
    return [
        {
            "id": "alert-1",
            "type": "weather",
            "severity": "high",
            "message": "Hurricane warning off the coast of Florida affecting shipping routes.",
            "timestamp": "2026-07-11T12:00:00Z"
        },
        {
            "id": "alert-2",
            "type": "port_congestion",
            "severity": "medium",
            "message": "Heavy congestion at Port of Long Beach. Expect 2-4 day delays.",
            "timestamp": "2026-07-10T08:30:00Z"
        }
    ]
