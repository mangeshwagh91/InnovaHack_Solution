"""
Knowledge & Document Intelligence Agent — DCPI.
RAG-powered agent that answers project RFI queries, searches specifications,
and remembers project-specific details (maps, designs, delays) by ingesting PDFs.
"""

import os
import json
import uuid
import logging
import re
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field

from database.connection import get_db
from services.llm_client import call_claude, has_available_provider
from services.vector_store import (
    search_spec_clauses,
    search_rfis,
    search_standards,
    get_or_create_collection,
    embed_text,
    embed_texts,
    _serialize_metadata,
    CHROMADB_AVAILABLE
)

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────
MAX_SPEC_RESULTS = int(os.getenv("RFI_MAX_SPEC_RESULTS", "5"))
MAX_RFI_RESULTS = int(os.getenv("RFI_MAX_RFI_RESULTS", "5"))
PRECEDENT_THRESHOLD = float(os.getenv("RFI_PRECEDENT_THRESHOLD", "0.82"))
MAX_CONTEXT_CHARS = int(os.getenv("RFI_MAX_CONTEXT_CHARS", "700"))
MAX_ANSWER_WORDS = int(os.getenv("RFI_MAX_ANSWER_WORDS", "400"))

AGENT_NAME = "knowledge_intelligence"
AGENT_VERSION = "2.0.0"

@dataclass
class RetrievedSource:
    rank: int
    doc_id: str
    doc_type: str
    text: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def label(self) -> str:
        if self.doc_type == "spec_clause":
            clause_num = self.metadata.get("clause_number", "N/A")
            return f"SPEC CLAUSE {clause_num}"
        elif self.doc_type == "rfi":
            rfi_code = self.metadata.get("rfi_code", "N/A")
            return f"RFI {rfi_code}"
        elif self.doc_type == "document_memory":
            doc_type = self.metadata.get("document_type", "Document")
            return f"MEMORY: {doc_type}"
        return "UNKNOWN SOURCE"


RAG_SYSTEM = """You are a senior technical manager on a Tier IV hyperscale data centre EPC project.

Answer questions from the project team using ONLY the information provided in the CONTEXT below.

STRICT RULES:
1. CHIT-CHAT EXCEPTION: If the user says "hi", "hello", "hey", or casual greetings, ignore all other rules. Just reply naturally and warmly in 1-2 sentences. Do NOT include source citations, RFI mentions, or confidence tags.
2. Answer ONLY from the provided context. Do not use general knowledge for technical queries.
3. Cite EVERY factual claim using [SOURCE N].
4. If a precedent RFI resolved a similar issue, LEAD your answer with it.
5. If the context does NOT contain sufficient information for a technical query, explicitly state: "The project documents do not contain a definitive answer. Recommend raising a formal RFI."
6. Be DIRECT and ACTIONABLE.
7. Keep your answer under {max_words} words.
8. Structure: If answering a complex technical RFI, use: (a) Precedent resolution if any, (b) Specification/Memory requirements, (c) Recommended action. For general project queries, answer naturally and directly.
9. For technical queries, end with: [Confidence: HIGH/MEDIUM/LOW]"""


def _chunk_text(text: str, chunk_size: int = 2000, overlap: int = 200) -> List[str]:
    chunks = []
    start = 0
    text_len = len(text)
    while start < text_len:
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


def ingest_document_memory(document_id: str, text: str, document_type: str, metadata: Dict[str, Any]) -> bool:
    """Ingest a document chunk into the 'document_memory' collection for delay memory/design updates."""
    if not text or not text.strip() or not CHROMADB_AVAILABLE:
        return False
    try:
        collection = get_or_create_collection("document_memory")
        
        chunks = _chunk_text(text, chunk_size=2000, overlap=200)
        
        batch_size = 100
        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i:i+batch_size]
            ids = [f"{document_id}_{i}_{j}_{uuid.uuid4().hex[:4]}" for j in range(len(batch_chunks))]
            embeddings = embed_texts(batch_chunks)
            
            metadatas = []
            for _ in batch_chunks:
                meta = metadata.copy()
                meta["document_type"] = document_type
                meta["ingested_at"] = datetime.now(timezone.utc).isoformat()
                metadatas.append(_serialize_metadata(meta))
                
            collection.upsert(
                ids=ids,
                documents=batch_chunks,
                embeddings=embeddings,
                metadatas=metadatas
            )
            
        logger.info(f"Ingested {len(chunks)} document memory chunks for {document_id} ({document_type})")
        return True
    except Exception as e:
        logger.error(f"Failed to ingest document memory: {e}")
        return False


def _search_document_memory(query: str, n_results: int = 3) -> List[RetrievedSource]:
    """Search ingested document memory."""
    if not CHROMADB_AVAILABLE or not query.strip():
        return []
    try:
        collection = get_or_create_collection("document_memory")
        if collection.count() == 0:
            return []
        embedding = embed_text(query)
        results = collection.query(query_embeddings=[embedding], n_results=n_results)
        chunks = []
        if results and results.get("ids") and results["ids"][0]:
            ids = results["ids"][0]
            docs = results["documents"][0]
            metas = results["metadatas"][0]
            dists = results["distances"][0]
            for i in range(len(ids)):
                chunks.append(RetrievedSource(
                    rank=0, doc_id=ids[i], doc_type="document_memory",
                    text=docs[i], score=max(0.0, 1.0 - dists[i]), metadata=metas[i]
                ))
        return chunks
    except Exception as e:
        logger.error(f"Failed to search document memory: {e}")
        return []


def answer_query(query: str) -> Dict[str, Any]:
    """Answer an RFI query using RAG over spec clauses, precedent RFIs, and document memory."""
    agent_run_id = str(uuid.uuid4())
    started_ts = datetime.now(timezone.utc).isoformat()
    start_time = datetime.now()

    logger.info(f"Knowledge query [{agent_run_id[:8]}]: {query[:100]}")

    # Explicit Memory Injection check
    lower_query = query.strip().lower()
    if lower_query.startswith("remember:") or lower_query.startswith("save:"):
        text_to_save = query.split(":", 1)[1].strip()
        if text_to_save:
            success = ingest_document_memory(
                document_id=str(uuid.uuid4()),
                text=text_to_save,
                document_type="user_chat_memory",
                metadata={"source": "user_input", "query": query}
            )
            return {
                "answer": "Memory saved successfully. The RFI Copilot will now consider this in future answers." if success else "Failed to save memory to the database.",
                "sources": [],
                "precedent_rfis": [],
                "confidence": 1.0,
                "agent_run_id": agent_run_id
            }

    try:
        spec_results = []
        rfi_results = []
        std_results = []
        if CHROMADB_AVAILABLE:
            try:
                spec_results = search_spec_clauses(query, n_results=MAX_SPEC_RESULTS)
                rfi_results = search_rfis(query, n_results=MAX_RFI_RESULTS)
                std_results = search_standards(query, n_results=MAX_SPEC_RESULTS)
            except Exception as e:
                logger.warning(f"Vector search failed: {e}")
        
        memory_chunks = _search_document_memory(query)
        
        # Convert standards into RetrievedSource objects
        for std in std_results:
            memory_chunks.append(RetrievedSource(
                rank=0, doc_id=std["id"], doc_type="standard",
                text=std["text"], score=std["score"], metadata=std.get("metadata", {})
            ))

        all_chunks = _build_source_list(spec_results, rfi_results, memory_chunks)
        precedent_rfis = _find_precedent_rfis(rfi_results)

        context_text = _build_context_text(all_chunks)
        precedent_text = _build_precedent_text(precedent_rfis)
        user_message = _build_user_message(context_text, precedent_text, query)

        if not has_available_provider():
            if not all_chunks:
                answer_text = "The project documents do not contain any relevant information to answer this query."
                confidence = 0.0
            else:
                answer_text = _fallback_answer(all_chunks, precedent_rfis)
                confidence = _compute_confidence(all_chunks)
        else:
            try:
                answer_text = call_claude(
                    RAG_SYSTEM.format(max_words=MAX_ANSWER_WORDS),
                    user_message,
                    max_tokens=1200
                )
                
                # Parse LLM confidence if available
                llm_confidence = None
                match = re.search(r"\[Confidence:\s*(HIGH|MEDIUM|LOW)\]", answer_text, re.IGNORECASE)
                if match:
                    conf_str = match.group(1).upper()
                    if conf_str == "HIGH": llm_confidence = 0.95
                    elif conf_str == "MEDIUM": llm_confidence = 0.70
                    elif conf_str == "LOW": llm_confidence = 0.40
                
                    # Remove the confidence tag from the answer text so it doesn't show in the UI twice
                    answer_text = re.sub(r"\n?\[Confidence:\s*(HIGH|MEDIUM|LOW)\]\n?", "", answer_text, flags=re.IGNORECASE).strip()
                
                confidence = llm_confidence if llm_confidence is not None else _compute_confidence(all_chunks)
            except Exception as e:
                logger.error(f"LLM call failed for knowledge query: {e}")
                if not all_chunks:
                    answer_text = "The project documents do not contain any relevant information to answer this query."
                    confidence = 0.0
                else:
                    answer_text = _fallback_answer(all_chunks, precedent_rfis)
                    confidence = _compute_confidence(all_chunks)

        sources = [
            {
                "doc_id": c.doc_id,
                "doc_type": c.doc_type,
                "clause_number": c.metadata.get("clause_number", "") or c.metadata.get("rfi_code", ""),
                "page_ref": c.metadata.get("document_id", ""),
                "score": c.score,
                "text_preview": c.text[:150]
            } for c in all_chunks[:10]
        ]

        processing_ms = round((datetime.now() - start_time).total_seconds() * 1000, 1)
        _log_agent_run_knowledge_agent(agent_run_id, started_ts, query, status="completed", confidence=confidence, num_sources=len(all_chunks))
        
        return {
            "answer": answer_text,
            "sources": sources,
            "precedent_rfis": [
                {
                    "rfi_id": p["rfi_id"], "rfi_code": p["rfi_code"], "title": p["title"],
                    "resolution_summary": p["resolution_summary"], "similarity_score": p["similarity_score"]
                } for p in precedent_rfis
            ],
            "confidence": confidence,
            "agent_run_id": agent_run_id
        }

    except Exception as e:
        logger.error(f"Knowledge query failed [{agent_run_id[:8]}]: {e}")
        _log_agent_run_knowledge_agent(agent_run_id, started_ts, query, status="failed", error=str(e))
        raise RuntimeError(f"Knowledge query processing failed: {e}") from e


def _build_source_list(spec_results: List[Dict], rfi_results: List[Dict], memory_chunks: List[RetrievedSource]) -> List[RetrievedSource]:
    all_chunks = memory_chunks.copy()
    for chunk in spec_results:
        all_chunks.append(RetrievedSource(0, chunk.get("id", ""), "spec_clause", chunk.get("text", ""), chunk.get("score", 0.0), chunk.get("metadata", {})))
    for chunk in rfi_results:
        all_chunks.append(RetrievedSource(0, chunk.get("id", ""), "rfi", chunk.get("text", ""), chunk.get("score", 0.0), chunk.get("metadata", {})))
    
    all_chunks.sort(key=lambda x: x.score, reverse=True)
    for i, chunk in enumerate(all_chunks):
        chunk.rank = i + 1
    return all_chunks


def _find_precedent_rfis(rfi_results: List[Dict]) -> List[Dict[str, Any]]:
    precedents = []
    db = get_db()
    try:
        for chunk in rfi_results:
            score = chunk.get("score", 0.0)
            if score < PRECEDENT_THRESHOLD: continue
            if str(chunk.get("metadata", {}).get("is_resolved", "false")).lower() not in {"true", "1", "yes"}: continue
            
            rfi_id = chunk.get("id", "")
            row = db.execute("SELECT id, rfi_code, title, resolution_text FROM rfis WHERE id = ?", (rfi_id,)).fetchone()
            if row:
                row = dict(row)
                precedents.append({
                    "rfi_id": row["id"], "rfi_code": row.get("rfi_code", "N/A"),
                    "title": row.get("title", "Untitled RFI"),
                    "resolution_summary": (row.get("resolution_text") or "")[:300],
                    "similarity_score": score
                })
        precedents.sort(key=lambda x: x["similarity_score"], reverse=True)
    finally:
        db.close()
    return precedents


def _build_context_text(chunks: List[RetrievedSource]) -> str:
    return "\n\n---\n\n".join([f"[SOURCE {c.rank} | {c.label}]\n{c.text[:MAX_CONTEXT_CHARS]}" for c in chunks[:12]])


def _build_precedent_text(precedents: List[Dict]) -> str:
    if not precedents: return ""
    lines = [f"PRECEDENT RFIs (similarity > {PRECEDENT_THRESHOLD}):"]
    for i, p in enumerate(precedents[:3], 1):
        lines.append(f"{i}. {p['rfi_code']}: {p['title']}\n   Resolution: {p['resolution_summary'][:250]}\n   Similarity: {p['similarity_score']:.0%}")
    return "\n".join(lines)


import urllib.request
import urllib.parse
import json

def _build_user_message(context_text: str, precedent_text: str, query: str) -> str:
    db = get_db()
    project_context = ""
    try:
        proj_row = db.execute("SELECT * FROM projects ORDER BY created_at DESC LIMIT 1").fetchone()
        if proj_row:
            proj = dict(proj_row)
            location = proj.get('location') or 'N/A'
            weather_data = "Weather data unavailable."
            if location and location != 'N/A':
                try:
                    loc_enc = urllib.parse.quote(location)
                    req = urllib.request.Request(f"https://wttr.in/{loc_enc}?format=j1", headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=1.5) as response:
                        w_json = json.loads(response.read().decode())
                        cc = w_json['current_condition'][0]
                        weather_data = f"{cc['temp_C']}°C, {cc['weatherDesc'][0]['value']}, Humidity: {cc['humidity']}%"
                except Exception as e:
                    logger.warning(f"Failed to fetch weather for {location}: {e}")
            
            project_context += (
                f"CURRENT PROJECT CONTEXT:\n"
                f"- Name: {proj['name']}\n"
                f"- Capacity: {proj['size_mw']} {proj.get('capacity_unit') or 'MW'}\n"
                f"- Deadline: {proj['deadline']}\n"
                f"- Location: {location}\n"
                f"- Current Weather: {weather_data}\n"
                f"- Tier: {proj.get('tier') or 'N/A'}\n"
                f"- Project Manager: {proj.get('pm') or 'N/A'}\n"
                f"- Total Budget: ${proj['budget']}\n\n"
            )

            # Fetch recent tenders
            tenders = db.execute("SELECT * FROM tenders WHERE project_id = ? ORDER BY created_at DESC LIMIT 3", (proj['id'],)).fetchall()
            if tenders:
                project_context += "RECENT VENDOR TENDERS:\n"
                for b in tenders:
                    b_dict = dict(b)
                    project_context += f" - Tender from {b_dict.get('vendor_id')} for {b_dict.get('price')}\n"
                project_context += "\n"
            
            # Fetch recent purchase orders
            pos = db.execute("SELECT * FROM purchase_orders WHERE project_id = ? ORDER BY po_date DESC LIMIT 3", (proj['id'],)).fetchall()
            if pos:
                project_context += "RECENT PURCHASE ORDERS & TRACKING:\n"
                for p in pos:
                    project_context += f"- PO Number: {p['po_number']} | Vendor: {p['vendor_name']} | Status: {p['compliance_status']} | Conformance: {p['conformance_score']}\n"
                project_context += "\n"
                
    finally:
        db.close()
        
    parts = [project_context + f"CONTEXT FROM PROJECT DOCUMENTS:\n{context_text}"]
    if precedent_text: parts.append(precedent_text)
    parts.append(f"QUERY FROM PROJECT TEAM:\n{query}")
    parts.append("Answer using ONLY the context above. Cite sources using [SOURCE N]. Lead with any precedent RFI if found. Be specific and actionable.")
    return "\n\n".join(parts)


def _fallback_answer(chunks: List[RetrievedSource], precedents: List[Dict]) -> str:
    parts = []
    if precedents:
        parts.append("Precedent RFIs Found:")
        for p in precedents[:3]:
            parts.append(f"- {p['rfi_code']}: {p['resolution_summary'][:200]}")
    if chunks:
        top = chunks[0]
        parts.append(f"\nMost Relevant Document:\n[{top.label}]\n{top.text[:300]}...")
    parts.append("\n⚠️ Automated fallback response — LLM unavailable. Review documents above and consult technical team.")
    return "\n".join(parts)


def _compute_confidence(chunks: List[RetrievedSource]) -> float:
    if not chunks: return 0.0
    return round(min(1.0, max(c.score for c in chunks) + min(0.15, len(chunks) * 0.03)), 4)


def _log_agent_run_knowledge_agent(agent_run_id: str, started_ts: str, query: str, status: str = "completed", confidence: float = 0.0, num_sources: int = 0, error: str = None) -> None:
    db = get_db()
    try:
        db.execute('''
            INSERT OR REPLACE INTO agent_runs
            (id, agent_name, agent_version, trigger_event, input_summary, output_summary, status, started_ts, completed_ts, records_processed, records_created, error_text, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            agent_run_id, AGENT_NAME, AGENT_VERSION, "knowledge_query", f"Query: {query[:150]}",
            f"Confidence={confidence:.2f} | {num_sources} sources" if status == "completed" else f"Failed: {(error or '')[:200]}",
            status, started_ts, datetime.now(timezone.utc).isoformat(), num_sources, 0, error, json.dumps({"confidence": confidence})
        ))
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log knowledge agent run: {e}")
    finally:
        db.close()


