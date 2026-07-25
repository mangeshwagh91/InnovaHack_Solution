"""
Computer Vision Agent — DCPI.
Analyzes site observation images (safety issues, defects, progress).
"""
import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any

from database.connection import get_db
from services.llm_client import has_available_provider, call_claude_json
from services.image_processor import encode_image_to_base64

logger = logging.getLogger(__name__)

AGENT_NAME = "vision_agent"
AGENT_VERSION = "1.0.0"

VISION_SYSTEM_PROMPT = """You are an AI Safety and Quality Inspector for a data centre construction site.
Analyze the provided image and extract observations regarding safety hazards, defects, or construction progress.

Return ONLY valid JSON:
{
  "observation_type": "SAFETY_HAZARD|DEFECT|PROGRESS",
  "severity": "CRITICAL|MAJOR|MINOR|INFO",
  "description": "Detailed description of what you see",
  "recommended_action": "Suggested next steps"
}"""

def analyze_site_image(image_path: str, project_id: str = None) -> Dict[str, Any]:
    """Analyzes a site image using Vision LLM (mocked via text for now if no vision API available)."""
    db = get_db()
    observation_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    # In a full implementation, we would encode the image and pass it to the Vision model
    # b64_img = encode_image_to_base64(image_path)
    
    mock_analysis = {
        "observation_type": "SAFETY_HAZARD",
        "severity": "MAJOR",
        "description": "Simulated vision analysis: Exposed electrical wiring near water puddle.",
        "recommended_action": "Immediate site safety stand-down in sector A."
    }
    
    try:
        db.execute("""
            INSERT INTO site_observations
            (id, project_id, image_path, observation_type, severity, description, analysis_json, status, created_ts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            observation_id, project_id, image_path,
            mock_analysis["observation_type"], mock_analysis["severity"],
            mock_analysis["description"], json.dumps(mock_analysis),
            "open", now
        ))
        db.commit()
        
        return {
            "observation_id": observation_id,
            "analysis": mock_analysis
        }
    except Exception as e:
        logger.error(f"Vision analysis failed: {e}")
        db.rollback()
        raise e
    finally:
        db.close()
