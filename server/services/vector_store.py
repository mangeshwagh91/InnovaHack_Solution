"""
Vector Store Service — DCPI.
ChromaDB integration with sentence-transformers embeddings.
Thread-safe singleton pattern. All metadata stored as strings.
is_resolved always stored as lowercase string "true"/"false".
"""

import os
import logging
import threading
import time
import json
from typing import List, Dict, Optional, Any

os.environ["CHROMA_TELEMETRY"] = "False"
os.environ["ANONYMIZED_TELEMETRY"] = "False"

try:
    import chromadb
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────
CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
MAX_RETRIES = int(os.getenv("CHROMA_MAX_RETRIES", "3"))
RETRY_DELAY = float(os.getenv("CHROMA_RETRY_DELAY", "0.5"))
MAX_BATCH_SIZE = int(os.getenv("CHROMA_BATCH_SIZE", "100"))

# ── Thread-safe singletons ─────────────────────────────────────────────────────
_chroma_client: Optional[Any] = None
_embedding_model: Optional[Any] = None
_chroma_lock = threading.RLock()
_embedding_lock = threading.RLock()
_collection_cache: Dict[str, Any] = {}
_cache_lock = threading.RLock()


class VectorStoreError(Exception):
    pass

class EmbeddingError(VectorStoreError):
    pass

class IndexingError(VectorStoreError):
    pass

class SearchError(VectorStoreError):
    pass


# ── Singleton accessors ────────────────────────────────────────────────────────

def _get_embedding_model():
    global _embedding_model
    if not SENTENCE_TRANSFORMERS_AVAILABLE:
        raise EmbeddingError("sentence-transformers is not installed")
    if _embedding_model is None:
        with _embedding_lock:
            if _embedding_model is None:
                try:
                    logger.info(f"Loading embedding model: {EMBEDDING_MODEL_NAME}")
                    _embedding_model = SentenceTransformer(
                        EMBEDDING_MODEL_NAME, device="cpu"
                    )
                    # Warm up
                    _ = _embedding_model.encode("warmup", show_progress_bar=False)
                    logger.info("Embedding model loaded and warmed up")
                except Exception as e:
                    raise EmbeddingError(f"Failed to load embedding model: {e}") from e
    return _embedding_model


def get_chroma_client():
    global _chroma_client
    if not CHROMADB_AVAILABLE:
        raise VectorStoreError("chromadb is not installed")
    if _chroma_client is None:
        with _chroma_lock:
            if _chroma_client is None:
                try:
                    os.makedirs(CHROMA_PATH, exist_ok=True)
                    logger.info(
                        f"Initializing ChromaDB at {os.path.abspath(CHROMA_PATH)}"
                    )
                    _chroma_client = chromadb.PersistentClient(
                        path=CHROMA_PATH,
                        settings=chromadb.Settings(
                            anonymized_telemetry=False,
                            allow_reset=True
                        )
                    )
                    logger.info("ChromaDB client initialized")
                except Exception as e:
                    _chroma_client = None
                    raise VectorStoreError(
                        f"ChromaDB initialization failed: {e}"
                    ) from e
    return _chroma_client


def get_or_create_collection(name: str) -> Any:
    """Get or create a ChromaDB collection. Returns the collection object."""
    with _cache_lock:
        if name in _collection_cache:
            try:
                _ = _collection_cache[name].count()
                return _collection_cache[name]
            except Exception:
                del _collection_cache[name]

    try:
        client = get_chroma_client()
        collection = client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"}
        )
        with _cache_lock:
            _collection_cache[name] = collection
        return collection
    except Exception as e:
        logger.warning(f"Collection '{name}' access failed: {e}")
        if any(k in str(e).lower() for k in ["connection", "timeout"]):
            global _chroma_client
            with _chroma_lock:
                _chroma_client = None
            with _cache_lock:
                _collection_cache.clear()
        raise VectorStoreError(f"Cannot access collection '{name}': {e}") from e


# ── Metadata serialization ─────────────────────────────────────────────────────

def _serialize_metadata(metadata: Dict[str, Any]) -> Dict[str, str]:
    """
    Serialize all metadata values to strings for ChromaDB storage.
    is_resolved is ALWAYS stored as "true" or "false" (lowercase string).
    """
    if not metadata:
        return {}
    result = {}
    for key, value in metadata.items():
        if key == "is_resolved":
            # Always canonical lowercase string
            if value in (True, 1, "true", "True", "1", "yes", "YES"):
                result[key] = "true"
            else:
                result[key] = "false"
        elif value is None:
            result[key] = ""
        elif isinstance(value, bool):
            result[key] = "true" if value else "false"
        elif isinstance(value, (int, float)):
            result[key] = str(value)
        elif isinstance(value, (dict, list)):
            result[key] = json.dumps(value)
        else:
            result[key] = str(value)
    return result


def _build_chunks(results: Dict) -> List[Dict[str, Any]]:
    """Convert raw ChromaDB query results into structured chunk dicts."""
    chunks = []
    try:
        ids = results.get("ids", [[]])
        documents = results.get("documents", [[]])
        metadatas = results.get("metadatas", [[]])
        distances = results.get("distances", [[]])

        if ids and isinstance(ids[0], list):
            ids = ids[0]
            documents = documents[0] if documents else []
            metadatas = metadatas[0] if metadatas else []
            distances = distances[0] if distances else []

        for i, chunk_id in enumerate(ids):
            distance = distances[i] if i < len(distances) else 0.0
            score = max(0.0, min(1.0, 1.0 - distance))
            meta = metadatas[i] if i < len(metadatas) else {}
            # Keep metadata as strings — do NOT deserialize to avoid type confusion
            chunks.append({
                "id": chunk_id,
                "text": documents[i] if i < len(documents) else "",
                "metadata": meta if isinstance(meta, dict) else {},
                "distance": round(distance, 4),
                "score": round(score, 4)
            })
    except Exception as e:
        logger.error(f"Error building chunks from ChromaDB results: {e}")
    return chunks


# ── Embedding ──────────────────────────────────────────────────────────────────

def embed_text(text: str, normalize: bool = True) -> List[float]:
    if not text or not text.strip():
        raise ValueError("Cannot embed empty text")
    try:
        model = _get_embedding_model()
        embedding = model.encode(text, normalize_embeddings=normalize, show_progress_bar=False)
        return embedding.tolist()
    except ValueError:
        raise
    except Exception as e:
        raise EmbeddingError(f"Embedding failed: {e}") from e

def embed_texts(texts: List[str], normalize: bool = True) -> List[List[float]]:
    if not texts:
        return []
    try:
        model = _get_embedding_model()
        embeddings = model.encode(texts, normalize_embeddings=normalize, show_progress_bar=False)
        return embeddings.tolist()
    except Exception as e:
        raise EmbeddingError(f"Batch embedding failed: {e}") from e


# ── Indexing ───────────────────────────────────────────────────────────────────

def index_spec_clause(
    clause_id: str,
    text: str,
    metadata: Dict[str, Any]
) -> bool:
    """Index a specification clause in the 'spec_clauses' ChromaDB collection."""
    if not text or not text.strip():
        logger.warning(f"Skipping empty spec clause '{clause_id}'")
        return False

    try:
        collection = get_or_create_collection("spec_clauses")
        embedding = embed_text(text)
        collection.upsert(
            ids=[clause_id],
            documents=[text],
            embeddings=[embedding],
            metadatas=[_serialize_metadata(metadata)]
        )
        logger.debug(f"Indexed spec clause '{clause_id}' ({len(text)} chars)")
        return True
    except (ValueError, EmbeddingError) as e:
        logger.error(f"Cannot index clause '{clause_id}': {e}")
        raise IndexingError(str(e)) from e
    except Exception as e:
        raise IndexingError(f"Failed to index clause '{clause_id}': {e}") from e
    return False


def index_rfi(
    rfi_id: str,
    text: str,
    metadata: Dict[str, Any]
) -> bool:
    if not text or not text.strip():
        logger.warning(f"Skipping empty RFI '{rfi_id}'")
        return False
    try:
        collection = get_or_create_collection("rfis")
        embedding = embed_text(text)
        meta = _serialize_metadata(metadata)
        if "is_resolved" not in meta:
            meta["is_resolved"] = "false"

        collection.upsert(
            ids=[rfi_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[meta]
        )
        logger.info(f"Indexed RFI {rfi_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to index RFI {rfi_id}: {e}")
        return False

def index_standard(
    standard_id: str,
    text: str,
    metadata: Dict[str, Any]
) -> bool:
    try:
        collection = get_or_create_collection("standards")
        embedding = embed_text(text)
        meta = _serialize_metadata(metadata)

        collection.upsert(
            ids=[standard_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[meta]
        )
        logger.info(f"Indexed standard clause {standard_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to index standard {standard_id}: {e}")
        return False

def index_commissioning_checklist(
    checklist_id: str,
    text: str,
    metadata: Dict[str, Any]
) -> bool:
    try:
        collection = get_or_create_collection("commissioning_checklists")
        embedding = embed_text(text)
        meta = _serialize_metadata(metadata)

        collection.upsert(
            ids=[checklist_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[meta]
        )
        logger.info(f"Indexed checklist {checklist_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to index checklist {checklist_id}: {e}")
        return False


# ── Search ─────────────────────────────────────────────────────────────────────

def search_spec_clauses(
    query: str,
    n_results: int = 5,
    threshold: float = 0.0
) -> List[Dict[str, Any]]:
    """Search spec_clauses collection. Returns list sorted by relevance."""
    if not query or not query.strip():
        return []
    try:
        collection = get_or_create_collection("spec_clauses")
        count = collection.count()
        if count == 0:
            logger.warning("spec_clauses collection is empty — run seed_data.py first")
            return []
        n_results = min(n_results, count)
        embedding = embed_text(query)
        results = collection.query(
            query_embeddings=[embedding],
            n_results=n_results
        )
        chunks = _build_chunks(results)
        if threshold > 0:
            chunks = [c for c in chunks if c["score"] >= threshold]
        logger.debug(f"spec_clauses search: {len(chunks)} results")
        return chunks
    except (VectorStoreError, EmbeddingError):
        raise
    except Exception as e:
        raise SearchError(f"spec_clauses search failed: {e}") from e


def search_rfis(
    query: str,
    n_results: int = 5,
    only_resolved: Optional[bool] = True,
    threshold: float = 0.0
) -> List[Dict[str, Any]]:
    """
    Search rfis collection.

    Args:
        query: Natural language query
        n_results: Max results to return
        only_resolved: If True (default), return only resolved RFIs.
                       If False, return only unresolved.
                       If None, return all regardless of resolved status.
        threshold: Minimum similarity score filter (0.0 = no filter)

    Default is only_resolved=True because agents want resolved RFIs for
    precedent matching and RAG context.
    """
    if not query or not query.strip():
        return []
    try:
        collection = get_or_create_collection("rfis")
        count = collection.count()
        if count == 0:
            logger.warning("rfis collection is empty — run seed_data.py first")
            return []
        n_results = min(n_results, count)
        embedding = embed_text(query)

        # Strategy 1: ChromaDB where filter
        if only_resolved is not None:
            filter_value = "true" if only_resolved else "false"
            try:
                results = collection.query(
                    query_embeddings=[embedding],
                    n_results=n_results,
                    where={"is_resolved": filter_value}
                )
                chunks = _build_chunks(results)
                if chunks:
                    logger.debug(
                        f"rfis search (where filter): {len(chunks)} results"
                    )
                    if threshold > 0:
                        chunks = [c for c in chunks if c["score"] >= threshold]
                    return chunks
                # Fall through to Python filter if where filter returned nothing
                logger.debug(
                    "rfis where filter returned 0 results — "
                    "falling back to Python-side filter"
                )
            except Exception as filter_err:
                logger.warning(f"ChromaDB where filter failed: {filter_err}")

            # Strategy 2: query all, filter in Python
            results = collection.query(
                query_embeddings=[embedding],
                n_results=min(n_results * 3, count)  # fetch extra to have enough after filter
            )
            all_chunks = _build_chunks(results)
            # is_resolved stored as string "true"/"false" in metadata
            resolved_truthy = ("true", "True", "1", "yes", True, 1)
            resolved_falsy = ("false", "False", "0", "no", False, 0)
            if only_resolved:
                chunks = [
                    c for c in all_chunks
                    if c.get("metadata", {}).get("is_resolved", "false") in resolved_truthy
                ]
            else:
                chunks = [
                    c for c in all_chunks
                    if c.get("metadata", {}).get("is_resolved", "false") in resolved_falsy
                ]
            logger.debug(
                f"rfis Python filter: {len(chunks)}/{len(all_chunks)} "
                f"matched is_resolved={only_resolved}"
            )
        else:
            # No filter — return all
            results = collection.query(
                query_embeddings=[embedding],
                n_results=n_results
            )
            chunks = _build_chunks(results)

        if threshold > 0:
            chunks = [c for c in chunks if c["score"] >= threshold]

        return chunks[:n_results]

    except (VectorStoreError, EmbeddingError, SearchError):
        raise
    except Exception as e:
        raise SearchError(f"rfis search failed: {e}") from e

def search_standards(query: str, n_results: int = 5, threshold: float = 0.5) -> List[Dict[str, Any]]:
    if not query or not query.strip(): return []
    try:
        collection = get_or_create_collection("standards")
        count = collection.count()
        if count == 0: return []
        embedding = embed_text(query)
        results = collection.query(
            query_embeddings=[embedding],
            n_results=min(n_results, count)
        )
        chunks = _build_chunks(results)
        if threshold > 0:
            chunks = [c for c in chunks if c["score"] >= threshold]
        return chunks[:n_results]
    except Exception as e:
        logger.error(f"standards search failed: {e}")
        return []

def search_commissioning_checklists(query: str, n_results: int = 3, threshold: float = 0.5) -> List[Dict[str, Any]]:
    if not query or not query.strip(): return []
    try:
        collection = get_or_create_collection("commissioning_checklists")
        count = collection.count()
        if count == 0: return []
        embedding = embed_text(query)
        results = collection.query(
            query_embeddings=[embedding],
            n_results=min(n_results, count)
        )
        chunks = _build_chunks(results)
        if threshold > 0:
            chunks = [c for c in chunks if c["score"] >= threshold]
        return chunks[:n_results]
    except Exception as e:
        logger.error(f"commissioning checklists search failed: {e}")
        return []


# ── Utility ────────────────────────────────────────────────────────────────────

def get_collection_count(collection_name: str) -> int:
    try:
        return get_or_create_collection(collection_name).count()
    except Exception:
        return 0


def delete_collection(collection_name: str) -> bool:
    try:
        client = get_chroma_client()
        client.delete_collection(collection_name)
        with _cache_lock:
            _collection_cache.pop(collection_name, None)
        logger.info(f"Deleted collection '{collection_name}'")
        return True
    except Exception as e:
        logger.error(f"Failed to delete '{collection_name}': {e}")
        return False


def check_health() -> Dict[str, Any]:
    """Health check for vector store — used by monitoring endpoints."""
    health: Dict[str, Any] = {
        "status": "healthy",
        "chromadb": {"available": CHROMADB_AVAILABLE, "path": os.path.abspath(CHROMA_PATH)},
        "embedding": {"available": SENTENCE_TRANSFORMERS_AVAILABLE, "model": EMBEDDING_MODEL_NAME},
        "errors": []
    }
    if CHROMADB_AVAILABLE:
        try:
            client = get_chroma_client()
            collections = client.list_collections()
            health["chromadb"]["connected"] = True
            health["chromadb"]["collections"] = {
                c.name: {"count": c.count()} for c in collections
            }
        except Exception as e:
            health["chromadb"]["connected"] = False
            health["chromadb"]["error"] = str(e)
            health["errors"].append(str(e))
            health["status"] = "degraded"
    else:
        health["status"] = "degraded"
        health["errors"].append("chromadb not installed")

    if SENTENCE_TRANSFORMERS_AVAILABLE:
        try:
            _ = _get_embedding_model()
            health["embedding"]["loaded"] = True
        except Exception as e:
            health["embedding"]["loaded"] = False
            health["embedding"]["error"] = str(e)
            health["errors"].append(str(e))
            health["status"] = "degraded"
    else:
        health["status"] = "degraded"
        health["errors"].append("sentence-transformers not installed")

    return health


def batch_index_spec_clauses(clauses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Batch index spec clauses. Each dict needs 'id', 'text', 'metadata' keys."""
    results = {"total": len(clauses), "successful": 0, "failed": 0, "skipped": 0}
    for i, clause in enumerate(clauses):
        clause_id = clause.get("id", f"clause_{i}")
        text = clause.get("text", "")
        if not text.strip():
            results["skipped"] += 1
            continue
        try:
            index_spec_clause(clause_id, text, clause.get("metadata", {}))
            results["successful"] += 1
        except Exception as e:
            results["failed"] += 1
            logger.error(f"Batch index failed for {clause_id}: {e}")
    return results


def _batch_upsert(collection, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Internal helper for batch upserts."""
    ids, docs, metadatas = [], [], []
    for item in items:
        if not item.get("text", "").strip(): continue
        ids.append(item["id"])
        docs.append(item["text"])
        metadatas.append(_serialize_metadata(item.get("metadata", {})))
    
    if not ids: return {"success": True, "count": 0}
    
    # Batch embed to drastically speed up sentence-transformers
    embeddings = embed_texts(docs)
    
    collection.upsert(ids=ids, documents=docs, embeddings=embeddings, metadatas=metadatas)
    return {"success": True, "count": len(ids)}

def index_commissioning_checklist(chunk_id: str, text: str, metadata: Dict[str, Any]) -> None:
    """Index a single commissioning checklist chunk into ChromaDB."""
    try:
        collection = get_or_create_collection("commissioning_checklists")
        embedding = embed_text(text)
        serialized_meta = _serialize_metadata(metadata)
        collection.upsert(
            ids=[chunk_id],
            documents=[text],
            embeddings=[embedding],
            metadatas=[serialized_meta]
        )
    except Exception as e:
        logger.error(f"Failed to index checklist chunk {chunk_id}: {e}")
        raise IndexingError(f"Checklist indexing failed: {e}") from e

def batch_index_rfis(rfis: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Batch index RFIs. Expected keys: 'id', 'text', 'is_resolved', 'metadata'."""
    try:
        collection = get_or_create_collection("rfis")
        return _batch_upsert(collection, rfis)
    except Exception as e:
        logger.error(f"Batch index RFIs failed: {e}")
        return {"success": False, "count": 0, "error": str(e)}

def batch_index_standards(standards: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Batch index standards. Expected keys: 'id', 'text', 'metadata'."""
    try:
        collection = get_or_create_collection("standards")
        return _batch_upsert(collection, standards)
    except Exception as e:
        logger.error(f"Batch index standards failed: {e}")
        return {"success": False, "count": 0, "error": str(e)}

def batch_index_commissioning_checklists(checklists: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Batch index checklists. Expected keys: 'id', 'text', 'metadata'."""
    try:
        collection = get_or_create_collection("commissioning_checklists")
        return _batch_upsert(collection, checklists)
    except Exception as e:
        logger.error(f"Batch index checklists failed: {e}")
        return {"success": False, "count": 0, "error": str(e)}


def initialize_collections() -> Dict[str, bool]:
    """Force initialization of all core collections."""
    status = {}
    for coll_name in ["spec_clauses", "rfis", "standards", "commissioning_checklists"]:
        try:
            get_or_create_collection(coll_name)
            status[coll_name] = True
        except Exception:
            status[coll_name] = False
    return status


def cleanup_collections() -> None:
    """Release cached ChromaDB client and collection references."""
    global _chroma_client
    with _cache_lock:
        _collection_cache.clear()
    with _chroma_lock:
        _chroma_client = None