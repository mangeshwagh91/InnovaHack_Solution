"""
Authentication Router
Handles vendor registration and simple login for the hackathon.
"""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Form
from pydantic import BaseModel

from models.schemas import VendorRegister, VendorResponse, TokenResponse
from database.connection import get_db
from security import get_password_hash, verify_password, create_access_token

router = APIRouter()

class LoginRequest(BaseModel):
    email: str
    password: str

@router.post("/register/vendor", response_model=VendorResponse)
def register_vendor(vendor: VendorRegister):
    db = get_db()
    try:
        existing = db.execute("SELECT id FROM vendors WHERE email = ?", (vendor.email,)).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        vendor_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        # Hash the password for security
        hashed_password = get_password_hash(vendor.password)
        db.execute(
            "INSERT INTO vendors (id, company_name, email, password_hash, registered_at) VALUES (?, ?, ?, ?, ?)",
            (vendor_id, vendor.company_name, vendor.email, hashed_password, now)
        )
        db.commit()
        
        return {
            "id": vendor_id,
            "company_name": vendor.company_name,
            "email": vendor.email,
            "registered_at": now
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest):
    db = get_db()
    try:
        vendor = db.execute("SELECT id, password_hash FROM vendors WHERE email = ?", (request.email,)).fetchone()
        
        # Hackathon auto-register bypass: if vendor doesn't exist, just create them!
        if not vendor:
            vendor_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc).isoformat()
            hashed_password = get_password_hash(request.password)
            company_name = request.email.split("@")[0].upper() + " Corp"
            db.execute(
                "INSERT INTO vendors (id, company_name, email, password_hash, registered_at) VALUES (?, ?, ?, ?, ?)",
                (vendor_id, company_name, request.email, hashed_password, now)
            )
            db.commit()
            token = create_access_token(data={"sub": vendor_id})
            return {"access_token": token, "token_type": "bearer", "vendor_id": vendor_id}

        if not verify_password(request.password, vendor["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Generate a real JWT token
        token = create_access_token(data={"sub": vendor["id"]})
        return {"access_token": token, "token_type": "bearer", "vendor_id": vendor["id"]}
    finally:
        db.close()
