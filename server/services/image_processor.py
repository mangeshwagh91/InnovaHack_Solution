"""
Image Processing Service — DCPI.
Handles basic image validation and base64 encoding for LLM vision APIs.
"""
import base64
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def encode_image_to_base64(file_path: str) -> Optional[str]:
    """Reads an image file and returns its base64 encoded string."""
    if not os.path.exists(file_path):
        logger.error(f"Image not found: {file_path}")
        return None
        
    try:
        with open(file_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to encode image {file_path}: {e}")
        return None
