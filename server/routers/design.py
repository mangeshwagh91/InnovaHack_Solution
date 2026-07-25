import asyncio
from typing import List
from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse

router = APIRouter()

@router.post("/convert", summary="Simulate AI 2D to 3D Conversion")
async def convert_2d_to_3d(file: UploadFile = File(...)):
    """
    Simulates an AI pipeline reading a 2D floorplan and returning 
    structured JSON of 3D wall coordinates and dimensions.
    """
    # 1. Simulate ML inference time (e.g., OpenCV contour detection + SAM2 segmenting)
    await asyncio.sleep(2)
    
    # 2. Return a hardcoded "detected" floor plan. 
    # In a real app, this would be the output of your ML model.
    # Format: [x, y, z] position, [width, height, depth] dimensions
    
    # Let's create a basic data centre layout with an outer shell and some internal walls/racks
    walls = [
        # Outer walls
        {"id": "w1", "position": [0, 1.5, -5], "size": [10, 3, 0.2]},
        {"id": "w2", "position": [0, 1.5, 5], "size": [10, 3, 0.2]},
        {"id": "w3", "position": [-5, 1.5, 0], "size": [0.2, 3, 10]},
        {"id": "w4", "position": [5, 1.5, 0], "size": [0.2, 3, 10]},
        
        # Internal walls / dividers
        {"id": "w5", "position": [-2, 1.5, -2], "size": [0.2, 3, 6]},
        {"id": "w6", "position": [2, 1.5, 2], "size": [0.2, 3, 6]},
    ]
    
    # Server Racks / PDUs (detected objects)
    objects = [
        {"id": "rack1", "type": "rack", "position": [-3.5, 1, -3], "size": [0.8, 2, 1.2]},
        {"id": "rack2", "type": "rack", "position": [-3.5, 1, -1], "size": [0.8, 2, 1.2]},
        {"id": "rack3", "type": "rack", "position": [-3.5, 1, 1], "size": [0.8, 2, 1.2]},
        {"id": "pdu1", "type": "pdu", "position": [3.5, 1, 3], "size": [1, 2, 1]},
        {"id": "hvac1", "type": "hvac", "position": [0, 1, -4.5], "size": [2, 2, 0.8]},
    ]

    return JSONResponse({
        "status": "success",
        "message": "AI successfully processed the 2D blueprint into 3D structures.",
        "filename": file.filename,
        "data": {
            "walls": walls,
            "objects": objects,
            "roomSize": [10, 10]
        }
    })
