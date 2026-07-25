import os
import json
import logging
import math
from datetime import datetime, timezone
from typing import Dict, Any

from database.connection import get_db
from services.llm_client import call_claude, has_available_provider

logger = logging.getLogger(__name__)

SUPPLY_CHAIN_SYSTEM_PROMPT = """You are a senior supply chain risk analyst for a Tier IV data center project.
Your job is to analyze a delayed shipment of critical equipment, calculate the impact, and model procurement alternatives.

Given the shipment details, provide a JSON response with the following structure:
{
    "risk_assessment": "Short natural language paragraph explaining the risk based on distance/days delayed.",
    "alternatives": [
        {
            "action": "Description of alternative (e.g. Expedite Air Freight, Source from Local Vendor)",
            "estimated_cost_impact": "+$15,000",
            "time_saved_days": 3,
            "feasibility": "High/Medium/Low"
        }
    ],
    "recommendation": "Your top recommendation to keep the project on critical path."
}

Ensure the output is ONLY valid JSON.
"""

def analyze_shipment_risk(shipment_id: str) -> Dict[str, Any]:
    db = get_db()
    try:
        row = db.execute("SELECT * FROM shipments WHERE id = ?", (shipment_id,)).fetchone()
        if not row:
            raise ValueError(f"Shipment {shipment_id} not found.")
        
        shipment = dict(row)
        
        # --- 1. Deterministic Mathematics ---
        # Calculate Haversine Distance (miles)
        def haversine(lat1, lon1, lat2, lon2):
            R = 3958.8  # Earth radius in miles
            dlat = math.radians(lat2 - lat1)
            dlon = math.radians(lon2 - lon1)
            a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            return R * c
            
        distance_miles = haversine(
            shipment.get('current_lat', 0), shipment.get('current_lng', 0),
            shipment.get('dest_lat', 0), shipment.get('dest_lng', 0)
        )
        
        # Speed heuristic (commercial truck avg = 50mph including breaks)
        AVG_SPEED_MPH = 50.0
        required_transit_hours = distance_miles / AVG_SPEED_MPH
        
        # Calculate time remaining
        try:
            req_delivery = datetime.fromisoformat(shipment.get('required_delivery').replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            hours_remaining = (req_delivery - now).total_seconds() / 3600.0
        except:
            hours_remaining = 0
            
        is_late_mathematically = required_transit_hours > hours_remaining
        delay_hours = required_transit_hours - hours_remaining if is_late_mathematically else 0
        
        # --- 2. Schedule Critical Path Check & Weighted Scoring ---
        risk_score = 0
        reasons = []
        
        if delay_hours > 0:
            delay_days = delay_hours / 24.0
            if delay_days > 10:
                risk_score += 40
                reasons.append(f"Severe Delay: {delay_days:.1f} days late")
            elif delay_days > 3:
                risk_score += 25
                reasons.append(f"Significant Delay: {delay_days:.1f} days late")
            else:
                risk_score += 15
                reasons.append(f"Minor Delay: {delay_days:.1f} days late")

        schedule_float_days = 0
        is_critical = False
        equip_id = shipment.get('equipment_item_id')
        if equip_id:
            task = db.execute("SELECT total_float_days, is_critical_path FROM schedule_tasks WHERE equipment_item_id = ?", (equip_id,)).fetchone()
            if task:
                schedule_float_days = task[0]
                is_critical = task[1] == 1
                
                if schedule_float_days <= 0 or is_critical:
                    risk_score += 35
                    reasons.append("On Critical Path - Zero float")
                elif schedule_float_days <= 5:
                    risk_score += 20
                    reasons.append(f"Low float: {schedule_float_days} days")

        # User's Risk Tier Logic
        trigger_mitigation = False
        if risk_score >= 70:
            final_risk = "CRITICAL"
            trigger_mitigation = True
        elif risk_score >= 45:
            final_risk = "HIGH"
            trigger_mitigation = True
        elif risk_score >= 25:
            final_risk = "MEDIUM"
            trigger_mitigation = False
        else:
            final_risk = "LOW"
            trigger_mitigation = False

        # Update DB if risk changed
        if shipment.get("risk_level") != final_risk:
            db.execute("UPDATE shipments SET risk_level = ? WHERE id = ?", (final_risk, shipment_id))
            db.commit()

        if not trigger_mitigation:
            # If not critical/high, don't waste LLM tokens
            return {
                "risk_assessment": f"Risk Score: {risk_score}/100. Status: {final_risk}. " + " | ".join(reasons),
                "alternatives": [],
                "recommendation": "Monitor shipment closely, but active mitigation is not required at this score."
            }

        # Build Data-Grounded Prompt
        user_message = f"""
Shipment Tracking Data:
- Carrier: {shipment.get('carrier_name')}
- Origin: Lat {shipment.get('origin_lat')}, Lng {shipment.get('origin_lng')}
- Current: Lat {shipment.get('current_lat')}, Lng {shipment.get('current_lng')}
- Destination: Lat {shipment.get('dest_lat')}, Lng {shipment.get('dest_lng')}

**Deterministic Mathematical Analysis & Scoring:**
- Remaining Distance: {distance_miles:.1f} miles
- Calculated Delay: {delay_hours:.1f} hours
- Schedule Float Available: {schedule_float_days} days
- Computed Risk Score: {risk_score}/100 ({final_risk})
- Risk Factors: {', '.join(reasons)}

The algorithmic risk score is {final_risk}. Please generate precise mitigation alternatives based on this hard data.
"""
        
        ai_alternatives_json = "[]"
        if has_available_provider():
            try:
                response = call_claude(SUPPLY_CHAIN_SYSTEM_PROMPT, user_message, max_tokens=1000)
                # Cleanup markdown formatting if any
                response = response.replace("```json", "").replace("```", "").strip()
                
                # Update DB
                db.execute(
                    "UPDATE shipments SET ai_alternatives_json = ?, last_updated_ts = ? WHERE id = ?",
                    (response, datetime.now(timezone.utc).isoformat(), shipment_id)
                )
                db.commit()
                return json.loads(response)
            except Exception as e:
                logger.error(f"Failed to call LLM for supply chain agent: {e}")
                
        # Return what's in the DB if LLM fails or no provider
        existing = shipment.get("ai_alternatives_json")
        return json.loads(existing) if existing and existing != "[]" else {}
        
    finally:
        db.close()
