import os
import uuid
import logging
import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, status
from database.connection import get_db
from routers.upload import save_upload_async, _parse_spec_bg
from services.ingestion_queue import ingestion_queue

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/inbound-email", status_code=status.HTTP_200_OK)
async def inbound_email_webhook(request: Request):
    """
    Webhook endpoint to receive SendGrid Inbound Parse emails.
    Content-Type is multipart/form-data.
    """
    # SendGrid sends multipart/form-data
    form_data = await request.form()
    
    # Extract basic email fields
    to_address = form_data.get("to", "")
    if isinstance(to_address, str):
        pass
    else:
        to_address = str(to_address)
        
    from_address = form_data.get("from", "")
    subject = form_data.get("subject", "")
    
    logger.info(f"Received inbound email from {from_address} to {to_address}")
    
    # Extract project ID from the 'to' address.
    # We expect format like: project-<project_id>@inbound.example.com
    # or <project_id>@inbound.example.com
    project_id = None
    if to_address:
        # Simplest approach: extract the username part of the email
        username = to_address.split('@')[0] if '@' in to_address else to_address
        # Remove any "project-" prefix if they used one
        username = username.replace("project-", "")
        # Remove any brackets like <project-123@domain.com>
        username = re.sub(r'[<>]', '', username)
        
        project_id = username.strip()

    if not project_id:
        logger.warning("Could not extract project ID from 'to' address. Skipping.")
        return {"success": False, "reason": "Missing project ID in 'to' address"}
        
    db = get_db()
    try:
        # Validate that the project exists
        project = db.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not project:
            logger.warning(f"Project ID {project_id} not found in database. Skipping.")
            return {"success": False, "reason": "Invalid project ID"}
            
        # Process attachments
        attachments_processed = 0
        
        # In SendGrid, attachments are sent as fields named attachment1, attachment2, etc.
        # But we can just iterate over all values in the form that are UploadFiles
        for field_name, form_value in form_data.multi_items():
            # Check if this form field is a file
            if hasattr(form_value, "filename") and form_value.filename:
                # We only want PDFs for now based on our normal flow
                if form_value.filename.lower().endswith(".pdf"):
                    doc_id = str(uuid.uuid4())
                    
                    # Save the file (re-using the async save utility from upload router)
                    file_path = await save_upload_async(form_value)
                    
                    # Store in database. We'll default doc_type to "specification" 
                    # based on the current system, but could easily be "submittal"
                    doc_type = "specification" 
                    
                    db.execute("""
                        INSERT OR REPLACE INTO documents 
                        (id, project_id, filename, doc_type, upload_ts, file_path, status, page_count)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        doc_id,
                        project_id,
                        form_value.filename,
                        doc_type,
                        datetime.utcnow().isoformat(),
                        file_path,
                        "processing",
                        0
                    ))
                    db.commit()
                    logger.info(f"Email attachment saved as document: {doc_id}")
                    
                    # Submit to background processing queue
                    ingestion_queue.submit(
                        doc_id=doc_id,
                        doc_type=doc_type,
                        filename=form_value.filename,
                        coro_factory=lambda d=doc_id, f=file_path: _parse_spec_bg(d, f)
                    )
                    
                    attachments_processed += 1
                else:
                    logger.info(f"Skipped non-PDF attachment: {form_value.filename}")
                    
        return {
            "success": True, 
            "message": f"Processed {attachments_processed} PDF attachments for project {project_id}"
        }
        
    except Exception as e:
        logger.error(f"Error processing inbound email: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
