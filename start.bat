@echo off
echo ========================================================
echo Starting DataForge AI in Production Mode
echo ========================================================
set DISABLE_RELOAD=true
set HOST=0.0.0.0
set PORT=8000
cd server
echo Starting Uvicorn Server...
python -m uvicorn main:app --host %HOST% --port %PORT% --workers 4
