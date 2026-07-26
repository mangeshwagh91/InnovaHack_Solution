import os
import sys
import pytest
from fastapi.testclient import TestClient

# Add parent directory to path so it can import main
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Set up an in-memory database for testing before importing the app
os.environ["DATABASE_PATH"] = ":memory:"

from main import app
from database.schema import init_db
from database.connection import get_db

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    init_db()

client = TestClient(app)

import uuid

def test_vendor_registration_and_login():
    # 1. Register a new vendor
    unique_email = f"testvendor_{uuid.uuid4()}@example.com"
    register_data = {
        "company_name": "Test Vendor LLC",
        "email": unique_email,
        "password": "securepassword123"
    }
    
    response = client.post("/api/auth/register/vendor", json=register_data)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["company_name"] == "Test Vendor LLC"
    assert data["email"] == unique_email
    assert "id" in data
    
    vendor_id = data["id"]
    
    # Verify password was hashed (not stored in plain text)
    db = get_db()
    row = db.execute("SELECT password_hash FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
    db.close()
    
    assert row is not None
    assert row["password_hash"] != "securepassword123"
    assert row["password_hash"].startswith("$2b$") # bcrypt hash prefix
    
    # 2. Login with correct credentials
    login_data = {
        "email": unique_email,
        "password": "securepassword123"
    }
    
    response = client.post("/api/auth/login", json=login_data)
    assert response.status_code == 200, response.text
    login_result = response.json()
    
    assert "access_token" in login_result
    assert login_result["token_type"] == "bearer"
    assert login_result["vendor_id"] == vendor_id
    assert not login_result["access_token"].startswith("mock-jwt")

    # 3. Login with incorrect credentials
    bad_login_data = {
        "email": unique_email,
        "password": "wrongpassword"
    }
    response = client.post("/api/auth/login", json=bad_login_data)
    assert response.status_code == 401


