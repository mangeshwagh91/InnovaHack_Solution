import logging
import uuid
import os
import tempfile
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
except ImportError:
    RecursiveCharacterTextSplitter = None

from services.vector_store import index_commissioning_checklist

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/upload")
async def upload_integration_standard(
    file: UploadFile = File(...),
    standard_name: str = Form(...)
):
    """
    Ingest a PDF standard document (e.g., Uptime Institute, ASHRAE).
    Extract text, chunk semantically, and embed into ChromaDB.
    """
    if not fitz or not RecursiveCharacterTextSplitter:
        raise HTTPException(
            status_code=500, 
            detail="PDF parsing (PyMuPDF) or LangChain is not installed on the server."
        )

    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported for integrations.")

    logger.info(f"Ingesting {standard_name} from file {file.filename}")

    # 1. Save file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # 2. Extract Text using PyMuPDF
        doc = fitz.open(tmp_path)
        full_text = ""
        for page in doc:
            full_text += page.get_text() + "\n\n"
        doc.close()

        if not full_text.strip():
            raise HTTPException(status_code=400, detail="Could not extract text from the PDF.")

        # 3. Chunking using LangChain
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            separators=["\n\n", "\n", ".", " ", ""]
        )
        chunks = text_splitter.split_text(full_text)
        logger.info(f"Split {file.filename} into {len(chunks)} chunks.")

        # 4. Embed and insert into Vector DB
        # We process them in a loop or batch. vector_store.py has an index function.
        successful = 0
        for i, chunk_text in enumerate(chunks):
            chunk_id = f"{standard_name.lower().replace(' ', '_')}_{uuid.uuid4().hex[:8]}"
            metadata = {
                "source": file.filename,
                "standard": standard_name,
                "chunk_index": i
            }
            try:
                index_commissioning_checklist(chunk_id, chunk_text, metadata)
                successful += 1
            except Exception as e:
                logger.error(f"Failed to embed chunk {i}: {e}")

        return {
            "status": "success",
            "message": f"Successfully ingested {standard_name}",
            "chunks_processed": successful,
            "total_chunks": len(chunks)
        }

    except Exception as e:
        logger.error(f"Failed to process PDF: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
