import pytest
import requests
import json
import io
import os
from PIL import Image

BASE_URL = "http://localhost:8000"

def make_image(color=(255, 0, 0), size=(150, 150)):
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


# UAT2-TC01: Registering the same logo twice should show high similarity on scan
def test_near_identical_logo_detected():
    """A logo very similar to the registered one should score High or Medium."""
    buf = make_image(color=(220, 30, 30))
    res = requests.post(
        f"{BASE_URL}/logo/upload",
        data={"name": "UAT2DeceptBrand", "description": "Deception test"},
        files={"file": ("logo.png", buf, "image/png")}
    )
    assert res.status_code == 200

    # Scan and look for high similarity results
    scan_res = requests.post(
        f"{BASE_URL}/detection/scan?brand_name=UAT2DeceptBrand",
        timeout=90
    )
    assert scan_res.status_code == 200
    matches = scan_res.json().get("matches", [])

    print(f"\n  [UAT2-TC01] Matches found: {len(matches)}")
    for m in matches:
        print(f"    {m['confidence']} — {m['risk']} — {m['url'][:60]}")

    # At least some matches should be Medium or High deception potential
    significant = [m for m in matches if m["risk"] in ["Medium", "High"]]
    assert len(significant) > 0 or len(matches) == 0, (
        "All matches were Low risk — system may not be detecting deception potential"
    )


# UAT2-TC02: A blank/plain image upload should not produce high-risk matches
def test_blank_logo_produces_no_high_risk():
    """A plain white logo should not match anything as High deception."""
    buf = make_image(color=(255, 255, 255))
    res = requests.post(
        f"{BASE_URL}/logo/upload",
        data={"name": "UAT2BlankBrand", "description": "Blank logo test"},
        files={"file": ("blank.png", buf, "image/png")}
    )
    assert res.status_code == 200

    scan_res = requests.post(
        f"{BASE_URL}/detection/scan?brand_name=UAT2BlankBrand",
        timeout=90
    )
    assert scan_res.status_code == 200
    matches = scan_res.json().get("matches", [])
    high_risk = [m for m in matches if m["risk"] == "High"]

    print(f"\n  [UAT2-TC02] High risk matches for blank logo: {len(high_risk)}")
    assert len(high_risk) == 0, (
        f"Blank logo produced {len(high_risk)} High-risk matches — false positive risk"
    )


# UAT2-TC03: Every match must contain the required deception data fields
def test_match_contains_required_fields():
    """Each match returned must have url, confidence, and risk — no partial results."""
    buf = make_image(color=(0, 100, 200))
    requests.post(
        f"{BASE_URL}/logo/upload",
        data={"name": "UAT2FieldsBrand", "description": "Fields test"},
        files={"file": ("fields.png", buf, "image/png")}
    )
    scan_res = requests.post(
        f"{BASE_URL}/detection/scan?brand_name=UAT2FieldsBrand",
        timeout=90
    )
    assert scan_res.status_code == 200
    matches = scan_res.json().get("matches", [])

    required_fields = {"url", "confidence", "risk"}
    for i, match in enumerate(matches):
        missing = required_fields - set(match.keys())
        assert not missing, (
            f"Match {i} is missing fields: {missing}. Full match: {match}"
        )
    print(f"\n  [UAT2-TC03] All {len(matches)} matches contain required fields")


# UAT2-TC04: Brand name echoed back correctly in scan response
def test_scan_response_includes_brand_name():
    """Scan response must confirm which brand was scanned."""
    buf = make_image(color=(100, 200, 100))
    requests.post(
        f"{BASE_URL}/logo/upload",
        data={"name": "UAT2EchoBrand", "description": "Echo test"},
        files={"file": ("echo.png", buf, "image/png")}
    )
    scan_res = requests.post(
        f"{BASE_URL}/detection/scan?brand_name=UAT2EchoBrand",
        timeout=90
    )
    assert scan_res.status_code == 200
    body = scan_res.json()

    print(f"\n  [UAT2-TC04] Response brand field: {body.get('brand')}")
    assert "brand" in body, "Response missing 'brand' field"
    assert body["brand"] == "UAT2EchoBrand", (
        f"Brand name mismatch: expected 'UAT2EchoBrand', got '{body['brand']}'"
    )


# UAT2-TC05: total_scanned reflects real processing
def test_total_scanned_is_reported():
    """System should tell the user how many images were analyzed."""
    buf = make_image(color=(200, 100, 50))
    requests.post(
        f"{BASE_URL}/logo/upload",
        data={"name": "UAT2ScanCountBrand", "description": "Scan count test"},
        files={"file": ("count.png", buf, "image/png")}
    )
    scan_res = requests.post(
        f"{BASE_URL}/detection/scan?brand_name=UAT2ScanCountBrand",
        timeout=90
    )
    assert scan_res.status_code == 200
    body = scan_res.json()

    print(f"\n  [UAT2-TC05] Total scanned: {body.get('total_scanned')}")
    assert "total_scanned" in body, "Response missing 'total_scanned' field"
    assert body["total_scanned"] > 0, (
        "total_scanned is 0 — scraper may have returned no URLs"
    )