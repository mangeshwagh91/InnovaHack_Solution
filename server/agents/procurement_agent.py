"""
Procurement & ERP Agent — DCPI.
Handles vendor bidding, purchase orders, inventory, and lead times.
Analyzes tenders and gives recommendations (price, compliance, lead time, quality).
"""

import os
import json
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

from database.connection import get_db
from services.llm_client import call_claude_json, has_available_provider

logger = logging.getLogger(__name__)

AGENT_NAME = "procurement_erp"
AGENT_VERSION = "2.0.0"

BID_ANALYSIS_SYSTEM = """You are a senior procurement manager for a Tier IV data centre EPC project.
Analyze the provided vendor tenders. Score each tender out of 10 for price, compliance, lead time, and risk.
Provide an overall recommendation.

Return ONLY valid JSON in this format:
{
  "recommendations": [
    {
      "vendor_name": "Vendor A",
      "price_score": 8.5,
      "compliance_score": 9.0,
      "lead_time_score": 7.0,
      "risk_score": 9.5,
      "overall_score": 8.5,
      "recommendation": "RECOMMENDED|ALTERNATE|NOT_RECOMMENDED",
      "justification": "Short justification text"
    }
  ]
}"""

def analyze_bids(tenders: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyzes vendor tenders and provides recommendations."""
    agent_run_id = str(uuid.uuid4())
    started_ts = datetime.now(timezone.utc).isoformat()
    start_time = datetime.now()

    logger.info(f"Analyzing {len(tenders)} tenders [{agent_run_id[:8]}]")

    try:
        if not tenders:
            raise ValueError("No tenders provided for analysis.")

        if not has_available_provider():
            logger.warning("LLM provider unavailable. Using fallback heuristic.")
            recommendations = _fallback_bid_analysis(tenders)
        else:
            user_message = f"Please analyze these tenders:\n{json.dumps(tenders, indent=2)}"
            try:
                response = call_claude_json(BID_ANALYSIS_SYSTEM, user_message, max_tokens=1500)
                recommendations = response.get("recommendations", [])
            except Exception as e:
                logger.error(f"LLM call failed for tender analysis: {e}")
                recommendations = _fallback_bid_analysis(tenders)

        processing_ms = round((datetime.now() - start_time).total_seconds() * 1000, 1)
        _log_agent_run_procurement_agent(agent_run_id, started_ts, f"Analyzed {len(tenders)} tenders", status="completed", num_records=len(recommendations))

        return {
            "bids_analyzed": len(tenders),
            "recommendations": recommendations,
            "agent_run_id": agent_run_id
        }

    except Exception as e:
        logger.error(f"Tender analysis failed [{agent_run_id[:8]}]: {e}")
        _log_agent_run_procurement_agent(agent_run_id, started_ts, "Tender analysis", status="failed", error=str(e))
        raise RuntimeError(f"Tender analysis failed: {e}") from e

def _fallback_bid_analysis(tenders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    recommendations = []
    for tender in tenders:
        price = tender.get("price", 10000)
        lead_time = tender.get("lead_time_days", 30)
        
        # Simple heuristic
        price_score = max(0, 10 - (price / 10000))
        lead_time_score = max(0, 10 - (lead_time / 10))
        compliance_score = tender.get("compliance_score", 8.0)
        risk_score = tender.get("risk_score", 8.0)
        overall = (price_score + lead_time_score + compliance_score + risk_score) / 4
        
        rec = "RECOMMENDED" if overall > 8 else "ALTERNATE"
        
        recommendations.append({
            "vendor_name": tender.get("vendor_name", "Unknown"),
            "price_score": round(price_score, 1),
            "compliance_score": round(compliance_score, 1),
            "lead_time_score": round(lead_time_score, 1),
            "risk_score": round(risk_score, 1),
            "overall_score": round(overall, 1),
            "recommendation": rec,
            "justification": "Automated heuristic based on price, lead time, compliance, and risk."
        })
    return recommendations

def get_mock_shipment_tracking(po_id: str) -> Dict[str, Any]:
    """Provides mock shipment tracking for a given Purchase Order."""
    logger.info(f"Retrieving shipment tracking for {po_id}")
    return {
        "po_id": po_id,
        "status": "IN_TRANSIT",
        "origin": "Shenzhen, China",
        "destination": "Frankfurt, Germany",
        "estimated_arrival": "2026-08-15",
        "current_location": "Suez Canal",
        "alerts": ["Delay of 2 days due to port congestion"]
    }

def _log_agent_run_procurement_agent(agent_run_id: str, started_ts: str, input_summary: str, status: str = "completed", num_records: int = 0, error: str = None) -> None:
    db = get_db()
    try:
        output_summary = f"Generated {num_records} recommendations" if status == "completed" else f"Failed: {(error or '')[:200]}"
        db.execute('''
            INSERT OR REPLACE INTO agent_runs
            (id, agent_name, agent_version, trigger_event, input_summary, output_summary, status, started_ts, completed_ts, records_processed, records_created, error_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            agent_run_id, AGENT_NAME, AGENT_VERSION, "bid_analysis", input_summary,
            output_summary, status, started_ts, datetime.now(timezone.utc).isoformat(), num_records, num_records, error
        ))
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log procurement agent run: {e}")
    finally:
        db.close()


# ==============================================================================
# INTEGRATED FROM: vendor_agent.py
# ==============================================================================

"""
Mock Agent — DCPI.
This is a scaffolded agent file to demonstrate the 16-agent architecture.
Integration and logic are pending full enterprise implementation.
"""

import logging



# AGENT_NAME = "vendor_agent"
# AGENT_VERSION = "0.1.0"

def process_request(query: str, context: dict = None) -> dict:
    """
    Mock entry point for vendor_agent.
    """
    logger.info(f"vendor_agent received query: {query[:50]}")
    return {
        "agent": AGENT_NAME,
        "status": "Not Implemented",
        "message": "This agent is scaffolded for the enterprise vision."
    }


# ==============================================================================
# INTEGRATED FROM: cost_agent.py
# ==============================================================================

"""
Cost Agent — DCPI.
Calculates financial impacts, variance, and Estimated at Completion (EAC) based on schedule delays.
"""

import logging
import uuid
import json
from datetime import datetime, timezone



# AGENT_NAME = "cost_agent"
# AGENT_VERSION = "1.0.0"

def calculate_delay_impact(item_name: str, delay_days: int) -> dict:
    """
    Given an item and a delay, calculate the cost impact.
    (Mocked for hackathon purposes, but illustrates the API).
    """
    logger.info(f"Cost Agent calculating impact for {item_name} delayed by {delay_days} days.")
    
    # Simple heuristic for demo
    daily_penalty = 50000  # $50k/day LDs or extended prelims
    total_impact = delay_days * daily_penalty
    
    return {
        "item_name": item_name,
        "delay_days": delay_days,
        "daily_penalty_rate": daily_penalty,
        "total_financial_impact": total_impact,
        "impact_category": "Liquidated Damages & Preliminaries",
        "currency": "USD",
        "mitigation_cost": min(total_impact * 0.4, 250000) # Cheaper to mitigate (e.g. air freight)
    }


