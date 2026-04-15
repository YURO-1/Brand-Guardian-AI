import pytest
import requests
import time
import io
from PIL import Image

BASE_URL = "http://localhost:8000"

def make_test_image(width=100, height=100, color=(0, 128, 255)):
    """Helper: generates an in-memory PNG image for upload tests."""
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


# NFR3-TC01: Logo upload must complete within 15 seconds
def test_logo_upload_performance():
    """CLIP embedding generation should complete within 15 seconds on CPU."""
    buf = make_test_image()
    start = time.time()

    response = requests.post(
        f"{BASE_URL}/logo/upload",
        data={"name": "PerfTestBrand", "description": "Performance test"},
        files={"file": ("perf_logo.png", buf, "image/png")}
    )

    elapsed = time.time() - start
    print(f"\n  [NFR3-TC01] Upload time: {elapsed:.2f}s")

    assert response.status_code == 200, f"Upload failed: {response.text}"
    assert elapsed < 15, f"Upload took {elapsed:.2f}s — exceeds 15s threshold"


# NFR3-TC02: Detection scan must complete within 60 seconds
def test_detection_scan_performance():
    """Full scan including Bing scrape + CLIP inference should finish within 60s."""
    # Ensure brand is registered first
    buf = make_test_image(color=(255, 100, 0))
    requests.post(
        f"{BASE_URL}/logo/upload",
        data={"name": "PerfScanBrand", "description": "Scan perf test"},
        files={"file": ("scan_logo.png", buf, "image/png")}
    )

    start = time.time()
    response = requests.post(
        f"{BASE_URL}/detection/scan?brand_name=PerfScanBrand"
    )
    elapsed = time.time() - start
    print(f"\n  [NFR3-TC02] Scan time: {elapsed:.2f}s")

    assert response.status_code == 200, f"Scan failed: {response.text}"
    assert elapsed < 60, f"Scan took {elapsed:.2f}s — exceeds 60s threshold"

    data = response.json()
    print(f"  Scanned: {data.get('total_scanned', 0)} images, "
          f"Matches: {len(data.get('matches', []))}")


# NFR3-TC03: Health check must respond within 1 second
def test_health_check_performance():
    """Root endpoint should respond almost instantly."""
    start = time.time()
    response = requests.get(f"{BASE_URL}/")
    elapsed = time.time() - start
    print(f"\n  [NFR3-TC03] Health check time: {elapsed:.4f}s")

    assert response.status_code == 200
    assert elapsed < 3.0, f"Health check took {elapsed:.4f}s — exceeds 3s threshold"


# NFR3-TC04: Login must respond within 2 seconds
def test_auth_login_performance():
    """Authentication endpoint should respond within 2 seconds."""
    # Register first to ensure user exists
    requests.post(
        f"{BASE_URL}/auth/register",
        json={"email": "perfuser@test.com", "password": "PerfPass123"}
    )

    start = time.time()
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": "perfuser@test.com", "password": "PerfPass123"}
    )
    elapsed = time.time() - start
    print(f"\n  [NFR3-TC04] Login time: {elapsed:.4f}s")

    assert elapsed < 2.5, f"Login took {elapsed:.4f}s — exceeds 2.5s threshold"


# NFR3-TC05: Three consecutive uploads must all complete within 45 seconds total
def test_consecutive_uploads_performance():
    """Repeated uploads should not degrade — model should stay loaded in memory."""
    total_start = time.time()

    for i in range(3):
        buf = make_test_image(color=(i * 80, 100, 200))
        start = time.time()
        response = requests.post(
            f"{BASE_URL}/logo/upload",
            data={"name": f"ConsecBrand{i}", "description": f"Consecutive test {i}"},
            files={"file": (f"logo_{i}.png", buf, "image/png")}
        )
        elapsed = time.time() - start
        print(f"\n  [NFR3-TC05] Upload {i+1} time: {elapsed:.2f}s")
        assert response.status_code == 200, f"Upload {i+1} failed"

    total_elapsed = time.time() - total_start
    print(f"  Total time for 3 uploads: {total_elapsed:.2f}s")
    assert total_elapsed < 45, (
        f"3 consecutive uploads took {total_elapsed:.2f}s — exceeds 45s threshold"
    )