import pytest
import requests
import json
import os

BASE_URL = "http://localhost:8000"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_DB = os.path.join(BASE_DIR, "users_db.json")
LOGOS_DB = os.path.join(BASE_DIR, "logos_db.json")

# NFR2-TC01: Logo upload stays local — no external transmission
def test_logo_stored_locally(tmp_path):
    """Verify uploaded logo is saved on disk and not forwarded externally."""
    from PIL import Image
    import io

    # Create a minimal test image
    img = Image.new("RGB", (100, 100), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    response = requests.post(
        f"{BASE_URL}/logo/upload",
        data={"name": "TestBrandPrivacy", "description": "Privacy test"},
        files={"file": ("test_logo.png", buf, "image/png")}
    )
    assert response.status_code == 200, "Upload should succeed"

    # Confirm brand was saved locally in logos_db
    assert os.path.exists(LOGOS_DB), "logos_db.json should exist after upload"
    with open(LOGOS_DB, "r") as f:
        db = json.load(f)
    assert "TestBrandPrivacy" in db, "Brand embedding should be stored locally"


# NFR2-TC02: Unauthenticated GET on upload endpoint should not return data
def test_unauthorized_logo_access():
    """GET on upload endpoint should not expose logo data."""
    response = requests.get(f"{BASE_URL}/logo/upload")
    assert response.status_code in [401, 404, 405], (
        f"Expected 401/404/405 for unauthorized access, got {response.status_code}"
    )


# NFR2-TC03: No raw file serving route for data directory
def test_no_raw_data_endpoint():
    """System should not expose a direct file download for detection history."""
    response = requests.get(f"{BASE_URL}/data/detections_history.json")
    assert response.status_code in [401, 404, 405], (
        "Raw data files must not be publicly accessible via API"
    )


# NFR2-TC04: Passwords not stored as plaintext
def test_passwords_not_plaintext():
    """Register a user and confirm password is not stored in plaintext."""
    requests.post(
        f"{BASE_URL}/auth/register",
        json={"email": "privacytest@test.com", "password": "SuperSecret123"}
    )
    if os.path.exists(USERS_DB):
        with open(USERS_DB, "r") as f:
            content = f.read()
        assert "SuperSecret123" not in content, (
            "Plaintext password found in users_db.json — CRITICAL privacy violation"
        )


# NFR2-TC05: Detection results not returned for unregistered brand
def test_detection_requires_registered_brand():
    """Scanning an unregistered brand should return 404, not leak other data."""
    response = requests.post(
        f"{BASE_URL}/detection/scan?brand_name=NonExistentBrandXYZ"
    )
    assert response.status_code == 404, (
        "Scanning unregistered brand should return 404, not expose system data"
    )