"""
Main Orchestrator Agent (Brain) — DCPI.
LangGraph Supervisor Node that receives high-level requests,
decides which specialized agent(s) to call, and returns the response.
"""

import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, TypedDict, Optional

from langgraph.graph import StateGraph, END
from database.connection import get_db
from services.llm_client import call_claude_json, has_available_provider

from agents.knowledge_agent import answer_query as run_knowledge_query
from agents.procurement_agent import analyze_bids, get_mock_shipment_tracking
from agents.compliance_agent import run_compliance_check
from agents.schedule_agent import run_schedule_risk_analysis, update_timeline_dynamic, get_mock_weather_data
from agents.commissioning_agent import get_commissioning_tasks, generate_checklist

logger = logging.getLogger(__name__)

AGENT_NAME = "orchestrator_brain"
AGENT_VERSION = "3.0.0"

ORCHESTRATOR_SYSTEM = """You are the Main Orchestrator Agent for the DCPI platform.
Classify the user's intent into one of the 7 components:
1. KNOWLEDGE: Answering questions about past RFIs, document memory, delay precedents, specs, or weather. If the user asks a question (e.g. "Has this been raised...", "What is the..."), route here.
2. PROCUREMENT: Bidding, purchase orders, supply chain, lead times.
3. QUALITY: Running compliance checks, generating NCR reports. (Do NOT route general questions about deviations here, route them to KNOWLEDGE).
4. SCHEDULE: Schedule risk, critical path, float, workforce (DO NOT route weather queries here).
5. COMMISSIONING: Testing, startup, functional tests, checklists, commissioning.
6. REPORT: Dashboard, project health, summaries, metrics aggregation.
7. GENERAL: Generic chat.

Return ONLY valid JSON:
{
  "intent": "KNOWLEDGE|PROCUREMENT|QUALITY|SCHEDULE|COMMISSIONING|REPORT|GENERAL",
  "confidence": 0.95,
  "extracted_parameters": {
    "po_id": "extract if present",
    "tenders": "extract if present",
    "event_details": "extract if present",
    "task_id": "extract if present",
    "project_id": "extract if present"
  }
}"""


class OrchestratorState(TypedDict, total=False):
    query: str
    context: Dict[str, Any]
    intent: str
    extracted_parameters: Dict[str, Any]
    agent_response: Dict[str, Any]
    agent_run_id: str
    started_ts: str
    error: Optional[str]


# ── Nodes ──────────────────────────────────────────────────────────────────────

def classify_node(state: OrchestratorState) -> Dict:
    query = state.get("query", "")
    context = state.get("context", {})
    
    if not has_available_provider():
        q = query.lower()
        if "tender" in q or "vendor" in q: intent = "PROCUREMENT"
        elif "schedule" in q or "risk" in q: intent = "SCHEDULE"
        elif "compliance" in q or "po" in q: intent = "QUALITY"
        elif "commission" in q or "test" in q: intent = "COMMISSIONING"
        elif "report" in q or "dashboard" in q or "metric" in q: intent = "REPORT"
        else: intent = "KNOWLEDGE"
        params = context
    else:
        try:
            msg = f"Query: {query}\nContext: {json.dumps(context)}"
            res = call_claude_json(ORCHESTRATOR_SYSTEM, msg, max_tokens=500)
            intent = res.get("intent", "KNOWLEDGE").upper()
            params = res.get("extracted_parameters", {})
        except Exception as e:
            logger.warning(f"Orchestrator LLM failed: {e}")
            intent = "KNOWLEDGE"
            params = {}

    for k, v in context.items():
        if k not in params:
            params[k] = v

    return {"intent": intent, "extracted_parameters": params}


def simulate_supply_chain_shock(item_name: str, delay_weeks: int) -> dict:
    return {
        "status": "Mocked",
        "message": f"Simulating supply chain shock for {item_name} by {delay_weeks} weeks",
        "impact": "High"
    }


def knowledge_node(state: OrchestratorState) -> Dict:
    query = state.get("query", "")
    res = {
        "agent": "Knowledge & Document Agent",
        "knowledge_response": run_knowledge_query(query)
    }
    return {"agent_response": res}


def procurement_node(state: OrchestratorState) -> Dict:
    tenders = state.get("extracted_parameters", {}).get("tenders", [])
    po_id = state.get("extracted_parameters", {}).get("po_id")
    
    if po_id:
        res_data = get_mock_shipment_tracking(po_id)
    else:
        res_data = analyze_bids(tenders) if tenders else {"message": "No tenders or PO ID provided"}
        
    res = {
        "agent": "Procurement & Supply Chain Agent",
        "procurement_response": res_data
    }
    return {"agent_response": res}


def quality_node(state: OrchestratorState) -> Dict:
    po_id = state.get("extracted_parameters", {}).get("po_id")
    
    if not po_id:
        # Instead of failing or defaulting to PO-001, return a clear error
        check = {"error": "Please provide a valid Purchase Order ID (e.g. 'PO-PS1500-001') to run a compliance check."}
    else:
        try:
            check = run_compliance_check(po_id)
        except ValueError as e:
            check = {"error": str(e)}

    res = {
        "agent": "Compliance & Quality Agent",
        "compliance_check": check
    }
    return {"agent_response": res}


def schedule_node(state: OrchestratorState) -> Dict:
    event = state.get("extracted_parameters", {}).get("event_details")
    query = state.get("query", "").lower()
    
    if event:
        res_data = update_timeline_dynamic(event)
    else:
        res_data = run_schedule_risk_analysis()
        
    res = {
        "agent": "Schedule & Risk Agent",
        "schedule_response": res_data
    }
    return {"agent_response": res}


def commissioning_node(state: OrchestratorState) -> Dict:
    task_id = state.get("extracted_parameters", {}).get("task_id")
    res = {
        "agent": "Commissioning Agent",
        "commissioning_tasks": generate_checklist(task_id) if task_id else get_commissioning_tasks()
    }
    return {"agent_response": res}


def report_node(state: OrchestratorState) -> Dict:
    res = {
        "agent": "Report & Dashboard Agent",
        "message": "Dashboard agent called."
    }
    return {"agent_response": res}


# ── Edges ──────────────────────────────────────────────────────────────────────

def route_intent(state: OrchestratorState) -> str:
    intent = state.get("intent", "KNOWLEDGE")
    if intent == "PROCUREMENT": return "procurement"
    if intent == "QUALITY": return "quality"
    if intent == "SCHEDULE": return "schedule"
    if intent == "COMMISSIONING": return "commissioning"
    if intent == "REPORT": return "report"
    return "knowledge"


# ── Graph Builder ──────────────────────────────────────────────────────────────

_compiled_graph = None

def get_orchestrator_graph():
    global _compiled_graph
    if _compiled_graph is not None:
        return _compiled_graph

    workflow = StateGraph(OrchestratorState)

    workflow.add_node("classify", classify_node)
    workflow.add_node("knowledge", knowledge_node)
    workflow.add_node("procurement", procurement_node)
    workflow.add_node("quality", quality_node)
    workflow.add_node("schedule", schedule_node)
    workflow.add_node("commissioning", commissioning_node)
    workflow.add_node("report", report_node)

    workflow.set_entry_point("classify")
    
    workflow.add_conditional_edges(
        "classify",
        route_intent,
        {
            "knowledge": "knowledge",
            "procurement": "procurement",
            "quality": "quality",
            "schedule": "schedule",
            "commissioning": "commissioning",
            "report": "report"
        }
    )

    workflow.add_edge("knowledge", END)
    workflow.add_edge("procurement", END)
    workflow.add_edge("quality", END)
    workflow.add_edge("schedule", END)
    workflow.add_edge("commissioning", END)
    workflow.add_edge("report", END)

    _compiled_graph = workflow.compile()
    return _compiled_graph


# ── Public Entry Point ─────────────────────────────────────────────────────────

def process_request(query: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    run_id = str(uuid.uuid4())
    started = datetime.now(timezone.utc).isoformat()
    start_ms = datetime.now()
    
    graph = get_orchestrator_graph()
    initial_state = {
        "query": query,
        "context": context or {},
        "agent_run_id": run_id,
        "started_ts": started
    }

    try:
        final_state = graph.invoke(initial_state)
        processing_ms = round((datetime.now() - start_ms).total_seconds() * 1000, 1)
        intent = final_state.get("intent", "UNKNOWN")
        
        _log_agent_run(run_id, started, query, intent, "completed", processing_ms)
        
        return {
            "query": query,
            "intent": intent,
            "agent_response": final_state.get("agent_response", {}),
            "agent_run_id": run_id,
            "processing_time_ms": processing_ms
        }
    except Exception as e:
        logger.error(f"Orchestrator graph failed: {e}")
        _log_agent_run(run_id, started, query, "ERROR", "failed", error=str(e))
        return {"query": query, "intent": "ERROR", "error": str(e), "agent_run_id": run_id}


def _log_agent_run(run_id: str, started: str, query: str, intent: str, status: str, ms: float = 0.0, error: str = None):
    db = get_db()
    try:
        db.execute('''
            INSERT OR REPLACE INTO agent_runs
            (id, agent_name, agent_version, trigger_event, input_summary, output_summary, status, started_ts, completed_ts, records_processed, records_created, error_text, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            run_id, AGENT_NAME, AGENT_VERSION, "orchestrator_routing", f"Query: {query[:150]}",
            f"Routed to {intent} | {ms:.0f}ms" if status == "completed" else f"Failed: {(error or '')[:200]}",
            status, started, datetime.now(timezone.utc).isoformat(), 1, 0, error, json.dumps({"intent": intent})
        ))
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log orchestrator: {e}")
    finally:
        db.close()
