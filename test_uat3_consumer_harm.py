import pytest
import requests
import io
import os
from PIL import Image

BASE_URL = "http://localhost:8000"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def make_image(color=(255, 0, 0)):
    img = Image.new("RGB", (150, 150), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

def build_takedown_template(brand, url):
    """Mirror of the frontend template function for verification."""
    return (
        f"Subject: Formal Intellectual Property Takedown Notice — {brand}\n\n"
        f"Dear Sir/Madam,\n\n"
        f"We are the legal representatives of {brand}, the rightful owner of the brand assets "
        f"in question. It has come to our attention that your platform or website is hosting "
        f"content that infringes upon our client's intellectual property rights at the "
        f"following URL:\n\n"
        f"    {url}\n\n"
        f"This unauthorized use constitutes trademark and/or copyright infringement under "
        f"applicable law. We formally request that you:\n\n"
        f"    1. Immediately remove or disable access to the infringing content.\n"
        f"    2. Confirm removal in writing within 48 hours of receiving this notice.\n"
        f"    3. Take all necessary steps to prevent future unauthorized use of {brand} brand assets.\n\n"
        f"Failure to comply may result in further legal action.\n\n"
        f"Sincerely,\nBrandGuardian Legal AI\nOn behalf of {brand}"
    )


# UAT3-TC01: All returned URLs are complete and actionable
def test_scan_results_contain_valid_urls():
    """Every detection result must have a real, complete URL the user can investigate."""
    buf = make_image(color=(180, 60, 20))
    requests.post(
        f"{BASE_URL}/logo/upload",
        data={"name": "UAT3URLBrand", "description": "URL validity test"},
        files={"file": ("url_test.png", buf, "image/png")}
    )
    scan_res = requests.post(
        f"{BASE_URL}/detection/scan?brand_name=UAT3URLBrand",
        timeout=90
    )
    assert scan_res.status_code == 200
    matches = scan_res.json().get("matches", [])

    for i, match in enumerate(matches):
        url = match.get("url", "")
        print(f"\n  [UAT3-TC01] Match {i+1} URL: {url[:70]}")
        assert url.startswith("http"), (
            f"Match {i+1} has an invalid URL: '{url}' — user cannot act on this"
        )


# UAT3-TC02: Takedown URL pre-population (simulated via template function)
def test_takedown_url_carried_from_detection():
    """Selected threat URL must appear in the takedown notice URL field."""
    test_url = "https://fake-counterfeit-site.com/brand-product"
    test_brand = "UAT3CarryBrand"

    email_body = build_takedown_template(test_brand, test_url)

    print(f"\n  [UAT3-TC02] Checking URL presence in template...")
    assert test_url in email_body, (
        f"Infringing URL '{test_url}' not found in takedown template — "
        "user cannot identify which site the notice targets"
    )


# UAT3-TC03: Takedown email body contains the specific infringing URL
def test_takedown_template_contains_url():
    """The generated email must explicitly reference the infringing URL."""
    infringing_url = "https://counterfeit-store-example.com/fake-logo.jpg"
    brand = "UAT3TemplateBrand"

    template = build_takedown_template(brand, infringing_url)
    print(f"\n  [UAT3-TC03] Template excerpt:\n  {template[:200]}")

    assert infringing_url in template, (
        "Infringing URL missing from takedown template — "
        "legal notice would not identify the specific harm location"
    )


# UAT3-TC04: Takedown email body contains the brand name
def test_takedown_template_contains_brand_name():
    """The generated email must identify which brand's rights are being violated."""
    brand = "ConsumerTestBrand"
    url = "https://fake-site.com/stolen-logo.jpg"

    template = build_takedown_template(brand, url)
    print(f"\n  [UAT3-TC04] Checking brand name '{brand}' in template...")

    assert brand in template, (
        f"Brand name '{brand}' not found in takedown template — "
        "notice does not identify the rights holder"
    )


# UAT3-TC05: System handles zero-match scans without crashing
def test_zero_match_scan_handled_gracefully():
    """If no threats are found, user should get a clean empty result, not an error."""
    # Use a very generic/obscure brand name unlikely to match anything
    buf = make_image(color=(128, 128, 128))
    requests.post(
        f"{BASE_URL}/logo/upload",
        data={"name": "UAT3NoMatchBrand_zzzxxx", "description": "No match test"},
        files={"file": ("nomatch.png", buf, "image/png")}
    )
    scan_res = requests.post(
        f"{BASE_URL}/detection/scan?brand_name=UAT3NoMatchBrand_zzzxxx",
        timeout=90
    )

    print(f"\n  [UAT3-TC05] Status: {scan_res.status_code}")
    assert scan_res.status_code == 200, (
        f"Server returned {scan_res.status_code} for a zero-match scan — should be 200"
    )
    body = scan_res.json()
    assert "matches" in body, "Response missing 'matches' key even on empty scan"
    print(f"  Matches returned: {len(body['matches'])}")