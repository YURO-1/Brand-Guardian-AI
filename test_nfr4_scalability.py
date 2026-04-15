import pytest
import requests
import json
import os
import time
import io
import threading
from PIL import Image

BASE_URL = "http://localhost:8000"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGOS_DB = os.path.join(BASE_DIR, "logos_db.json")
HISTORY_PATH = os.path.join(BASE_DIR, "data", "detections_history.json")

def make_test_image(color=(100, 100, 100)):
    img = Image.new("RGB", (100, 100), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


# NFR4-TC01: Brand lookup performance with 50 brands in database
def test_large_logos_db_lookup():
    """System should handle a populated logos_db without slow lookups."""
    # Seed 50 brands directly into logos_db
    fake_embedding = [0.01] * 512
    db = {}
    if os.path.exists(LOGOS_DB):
        with open(LOGOS_DB, "r") as f:
            try: db = json.load(f)
            except: db = {}

    for i in range(50):
        db[f"ScaleBrand_{i}"] = {"embedding": fake_embedding, "description": f"Scale test brand {i}"}

    with open(LOGOS_DB, "w") as f:
        json.dump(db, f)

    # Now time a real upload (which reads and writes the db)
    buf = make_test_image(color=(200, 50, 50))
    start = time.time()
    response = requests.post(
        f"{BASE_URL}/logo/upload",
        data={"name": "LookupTestBrand", "description": "Lookup test"},
        files={"file": ("lookup.png", buf, "image/png")}
    )
    elapsed = time.time() - start
    print(f"\n  [NFR4-TC01] Lookup + write with 50 brands: {elapsed:.2f}s")

    assert response.status_code == 200, "Upload should succeed with large db"
    assert elapsed < 6.0, f"Took {elapsed:.2f}s with 50 brands — exceeds 6s threshold"


# NFR4-TC02: Detection history write with 500 pre-existing entries
def test_large_history_write_performance():
    """Writing to detection history should stay fast even with 500 existing records."""
    os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)

    # Seed 500 fake history entries
    fake_history = [
        {
            "brand": f"Brand_{i}",
            "url": f"https://fake-site-{i}.com/image.jpg",
            "confidence": f"{40 + (i % 40)}%",
            "risk": ["Low", "Medium", "High"][i % 3],
            "timestamp": time.time() - i * 60,
            "date_str": "2024-01-01 12:00:00",
            "status": "detected"
        }
        for i in range(500)
    ]
    with open(HISTORY_PATH, "w") as f:
        json.dump(fake_history, f)

    # Now trigger a real scan write by uploading + scanning
    buf = make_test_image(color=(0, 200, 100))
    requests.post(
        f"{BASE_URL}/logo/upload",
        data={"name": "HistoryScaleBrand", "description": "History scale test"},
        files={"file": ("hist.png", buf, "image/png")}
    )

    start = time.time()
    response = requests.post(
        f"{BASE_URL}/detection/scan?brand_name=HistoryScaleBrand"
    )
    elapsed = time.time() - start
    print(f"\n  [NFR4-TC02] Scan + history write with 500 records: {elapsed:.2f}s")

    assert response.status_code == 200
    # Verify history file is still valid JSON after write
    with open(HISTORY_PATH, "r") as f:
        updated = json.load(f)
    assert len(updated) >= 500, "History records should be preserved after new write"
    print(f"  History now has {len(updated)} records")


# NFR4-TC03: 5 concurrent upload requests
def test_concurrent_uploads():
    """Five simultaneous uploads should all succeed without corrupting the database."""
    results = []
    errors = []

    def upload_brand(index):
        try:
            buf = make_test_image(color=(index * 40, 100, 200))
            response = requests.post(
                f"{BASE_URL}/logo/upload",
                data={"name": f"ConcurrentBrand_{index}", "description": f"Concurrent {index}"},
                files={"file": (f"concurrent_{index}.png", buf, "image/png")}
            )
            results.append(response.status_code)
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=upload_brand, args=(i,)) for i in range(5)]

    start = time.time()
    for t in threads: t.start()
    for t in threads: t.join()
    elapsed = time.time() - start

    print(f"\n  [NFR4-TC03] 5 concurrent uploads completed in {elapsed:.2f}s")
    print(f"  Status codes: {results}")
    print(f"  Errors: {errors}")

    assert len(errors) == 0, f"Concurrent uploads produced errors: {errors}"
    assert all(s == 200 for s in results), f"Not all uploads succeeded: {results}"

    # Verify database is still valid JSON after concurrent writes
    assert os.path.exists(LOGOS_DB)
    with open(LOGOS_DB, "r") as f:
        db = json.load(f)
    assert isinstance(db, dict), "logos_db.json corrupted after concurrent writes"


# NFR4-TC04: 3 concurrent scan requests
def test_concurrent_scans():
    """Three simultaneous scans should all complete without 500 errors."""
    # Register a brand to scan against
    buf = make_test_image(color=(180, 60, 120))
    requests.post(
        f"{BASE_URL}/logo/upload",
        data={"name": "ConcurrentScanBrand", "description": "Concurrent scan test"},
        files={"file": ("scan_concurrent.png", buf, "image/png")}
    )

    results = []
    errors = []

    def run_scan(index):
        try:
            response = requests.post(
                f"{BASE_URL}/detection/scan?brand_name=ConcurrentScanBrand",
                timeout=90
            )
            results.append(response.status_code)
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=run_scan, args=(i,)) for i in range(3)]

    start = time.time()
    for t in threads: t.start()
    for t in threads: t.join()
    elapsed = time.time() - start

    print(f"\n  [NFR4-TC04] 3 concurrent scans completed in {elapsed:.2f}s")
    print(f"  Status codes: {results}")

    assert len(errors) == 0, f"Concurrent scans produced errors: {errors}"
    assert all(s == 200 for s in results), f"Not all scans succeeded: {results}"


# NFR4-TC05: History read time after 500 records
def test_history_read_performance_at_scale():
    """Reports endpoint should respond within 5 seconds even with large history."""
    # Ensure 500 records exist
    os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)
    fake_history = [
        {
            "brand": f"Brand_{i}",
            "url": f"https://fake-{i}.com/img.jpg",
            "confidence": f"{50 + (i % 30)}%",
            "risk": ["Low", "Medium", "High"][i % 3],
            "timestamp": time.time() - i,
            "date_str": "2024-06-01 10:00:00",
            "status": "detected"
        }
        for i in range(500)
    ]
    with open(HISTORY_PATH, "w") as f:
        json.dump(fake_history, f)

    start = time.time()
    response = requests.get(f"{BASE_URL}/reports/download-summary")
    elapsed = time.time() - start

    print(f"\n  [NFR4-TC05] Report generation with 500 history records: {elapsed:.2f}s")

    # 200 means report generated, 500 means it crashed under load
    assert response.status_code != 500, "Server crashed when generating report at scale"
    assert elapsed < 5.0, f"Report took {elapsed:.2f}s with 500 records — exceeds 5s"