import pytest
import requests
import json
import os
import io
from PIL import Image

BASE_URL = "http://localhost:8000"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_PATH = os.path.join(BASE_DIR, "data", "detections_history.json")

def make_test_image(color=(255, 0, 0)):
    img = Image.new("RGB", (150, 150), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

def register_brand(name, color=(255, 0, 0)):
    buf = make_test_image(color=color)
    res = requests.post(
        f"{BASE_URL}/logo/upload",
        data={"name": name, "description": "UAT risk test brand"},
        files={"file": ("logo.png", buf, "image/png")}
    )
    assert res.status_code == 200, f"Brand registration failed: {res.text}"


# UAT1-TC01: Scan results contain more than one risk level
def test_risk_levels_are_differentiated():
    """Brand owner should see varied risk levels, not all Medium."""
    register_brand("UAT1RiskBrand", color=(200, 100, 50))
    res = requests.post(
        f"{BASE_URL}/detection/scan?brand_name=UAT1RiskBrand",
        timeout=90
    )
    assert res.status_code == 200, f"Scan failed: {res.text}"
    matches = res.json().get("matches", [])

    if len(matches) < 2:
        pytest.skip("Not enough matches returned to evaluate differentiation")

    risk_levels = set(m["risk"] for m in matches)
    print(f"\n  [UAT1-TC01] Risk levels found: {risk_levels}")
    assert len(risk_levels) > 1, (
        f"All results returned the same risk level: {risk_levels}. "
        "System is not differentiating threat severity."
    )


# UAT1-TC02: Higher confidence % should map to higher or equal risk label
def test_confidence_score_aligns_with_risk():
    """Confidence percentages should be consistent with risk labels."""
    register_brand("UAT1AlignBrand", color=(100, 200, 50))
    res = requests.post(
        f"{BASE_URL}/detection/scan?brand_name=UAT1AlignBrand",
        timeout=90
    )
    assert res.status_code == 200
    matches = res.json().get("matches", [])

    if not matches:
        pytest.skip("No matches returned for alignment test")

    risk_order = {"Low": 1, "Medium": 2, "High": 3}

    highs  = [int(m["confidence"].replace("%","")) for m in matches if m["risk"] == "High"]
    mediums = [int(m["confidence"].replace("%","")) for m in matches if m["risk"] == "Medium"]
    lows   = [int(m["confidence"].replace("%","")) for m in matches if m["risk"] == "Low"]

    print(f"\n  [UAT1-TC02] High scores: {highs}, Medium: {mediums}, Low: {lows}")

    if highs and lows:
        assert min(highs) > max(lows), (
            "A Low-risk result has a higher confidence than a High-risk result — miscalibration detected"
        )
    if mediums and lows:
        assert min(mediums) >= max(lows) - 5, (
            "A Low-risk result has a significantly higher score than a Medium result"
        )


# UAT1-TC03: The highest scoring result should not be labelled Low
def test_highest_score_not_labelled_low():
    """The most similar image found should be High or Medium, never Low."""
    register_brand("UAT1TopBrand", color=(50, 50, 200))
    res = requests.post(
        f"{BASE_URL}/detection/scan?brand_name=UAT1TopBrand",
        timeout=90
    )
    assert res.status_code == 200
    matches = res.json().get("matches", [])

    if not matches:
        pytest.skip("No matches returned")

    sorted_matches = sorted(
        matches,
        key=lambda m: int(m["confidence"].replace("%", "")),
        reverse=True
    )
    top_match = sorted_matches[0]
    print(f"\n  [UAT1-TC03] Top match: {top_match['confidence']} — {top_match['risk']}")
    assert top_match["risk"] in ["Medium", "High"], (
        f"Highest confidence result was labelled '{top_match['risk']}' — expected Medium or High"
    )


# UAT1-TC04: No result should have a confidence below the minimum threshold (38%)
def test_low_similarity_images_excluded():
    """Irrelevant images should be filtered out — nothing below 38% should appear."""
    register_brand("UAT1FilterBrand", color=(150, 150, 0))
    res = requests.post(
        f"{BASE_URL}/detection/scan?brand_name=UAT1FilterBrand",
        timeout=90
    )
    assert res.status_code == 200
    matches = res.json().get("matches", [])

    for match in matches:
        score = int(match["confidence"].replace("%", ""))
        print(f"\n  [UAT1-TC04] Checking score {score}% for URL: {match['url'][:60]}")
        assert score >= 38, (
            f"Result with {score}% confidence appeared — below the 38% minimum threshold"
        )


# UAT1-TC05: Detection history matches what was shown on screen
def test_risk_label_persists_in_history():
    """Every result shown to the user should be saved with the same risk label."""
    register_brand("UAT1HistBrand", color=(80, 160, 200))
    res = requests.post(
        f"{BASE_URL}/detection/scan?brand_name=UAT1HistBrand",
        timeout=90
    )
    assert res.status_code == 200
    matches = res.json().get("matches", [])

    if not matches:
        pytest.skip("No matches to verify in history")

    assert os.path.exists(HISTORY_PATH), "Detection history file was not created"
    with open(HISTORY_PATH, "r") as f:
        history = json.load(f)

    saved_urls = {entry["url"]: entry["risk"] for entry in history}

    for match in matches:
        url = match["url"]
        assert url in saved_urls, f"Match URL not found in history: {url}"
        assert saved_urls[url] == match["risk"], (
            f"Risk label mismatch for {url}: "
            f"shown '{match['risk']}' but saved '{saved_urls[url]}'"
        )
    print(f"\n  [UAT1-TC05] All {len(matches)} matches verified in history")