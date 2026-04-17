import os
import json
import time
import re
import requests
from fastapi import APIRouter, Request, HTTPException
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()
WHOIS_API_KEY = os.getenv("WHOIS_API_KEY")

router = APIRouter(tags=["Takedown"])

# --- SETUP PATHS ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "../../"))
TAKEDOWN_HISTORY_PATH = os.path.join(BASE_DIR, "data", "takedowns_history.json")

def save_takedown_to_history(url, email, is_abuse, source):
    os.makedirs(os.path.dirname(TAKEDOWN_HISTORY_PATH), exist_ok=True)
    history = []
    if os.path.exists(TAKEDOWN_HISTORY_PATH):
        try:
            with open(TAKEDOWN_HISTORY_PATH, "r") as f:
                history = json.load(f)
        except:
            history = []

    entry = {
        "target_url": url,
        "contact_email": email,
        "is_official_abuse": is_abuse,
        "source": source,
        "timestamp": time.time(),
        "date_str": time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "success" if email and "@" in str(email) else "failed"
    }
    history.append(entry)
    try:
        with open(TAKEDOWN_HISTORY_PATH, "w") as f:
            json.dump(history, f, indent=4)
    except Exception as e:
        print(f"Failed to log history: {e}")

def clean_domain(url: str) -> str:
    """Reliably extract the bare registrable domain from any URL or raw domain string."""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    netloc = parsed.netloc.split(":")[0]  # strip port
    parts = netloc.split(".")
    # Collapse subdomains — take only last two parts (e.g. www.manilaonsale.com -> manilaonsale.com)
    domain = ".".join(parts[-2:]) if len(parts) >= 2 else netloc
    return domain

def get_whois_data(domain: str) -> dict:
    """Query WhoisXML and return the full WhoisRecord dict."""
    if not WHOIS_API_KEY:
        return {}
    try:
        whois_url = (
            f"https://www.whoisxmlapi.com/whoisserver/WhoisService"
            f"?apiKey={WHOIS_API_KEY}&domainName={domain}&outputFormat=JSON"
        )
        response = requests.get(whois_url, timeout=10)
        data = response.json()
        return data.get("WhoisRecord", {})
    except Exception as e:
        print(f"WHOIS API Error: {e}")
        return {}

def extract_email_from_whois(record: dict) -> tuple[str | None, str]:
    """
    Walk through every useful WHOIS field to find a real email.
    Returns (email, source_label).
    """
    # Direct contact email on the record
    if record.get("contactEmail"):
        return record["contactEmail"], "WHOIS contactEmail"

    # Check all standard contact sections
    for section in ["registrant", "administrativeContact", "technicalContact", "billingContact"]:
        contact = record.get(section, {})
        if isinstance(contact, dict) and contact.get("email"):
            return contact["email"], f"WHOIS {section}"

    # Some APIs nest contacts in a list
    for contact in record.get("contacts", []):
        if isinstance(contact, dict) and contact.get("email"):
            return contact["email"], "WHOIS contacts[]"

    # Last resort — scrape any email-like string from the raw text
    raw_text = record.get("rawText", "")
    emails_found = re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", raw_text)
    # Filter out privacy-shield placeholder emails
    real_emails = [
        e for e in emails_found
        if not any(skip in e.lower() for skip in [
            "privacy", "whoisguard", "proxy", "protect", "redacted", "domainsbyproxy"
        ])
    ]
    if real_emails:
        return real_emails[0], "WHOIS rawText scrape"

    return None, ""

def get_hosting_abuse_email(domain: str) -> tuple[str | None, str]:
    """
    Resolve the domain to an IP, then look up the hosting provider's
    abuse contact via ipinfo.io — useful when WHOIS is privacy-shielded.
    """
    try:
        ip_resp = requests.get(f"https://ipinfo.io/{domain}/json", timeout=8)
        ip_data = ip_resp.json()
        org = ip_data.get("org", "")  # e.g. "AS16509 Amazon.com, Inc."
        ip = ip_data.get("ip", "")

        # Try abuse contact via RDAP/ipinfo abuse endpoint
        abuse_resp = requests.get(f"https://ipinfo.io/{ip}/json?token=", timeout=8)
        abuse_data = abuse_resp.json()
        abuse_email = abuse_data.get("abuse", {}).get("email")
        if abuse_email:
            return abuse_email, f"Host abuse contact ({org})"
    except Exception as e:
        print(f"IP/Host lookup failed: {e}")
    return None, ""

@router.get("/investigate")
async def investigate_site(url: str, request: Request):
    """Layered contact resolution: AI Crawler -> WHOIS (all fields + rawText) -> Host IP abuse -> Heuristic."""

    if not url.startswith("http"):
        url = "https://" + url

    detected_email = None
    source = "Initializing"
    domain = clean_domain(url)

    print(f"[Takedown] Investigating domain: {domain} (from URL: {url})")

    try:
        # --- LAYER 1: AI Contact Crawler ---
        if hasattr(request.app.state, "contact_crawler"):
            try:
                detected_email = await request.app.state.contact_crawler(url)
                if detected_email and "@" in str(detected_email):
                    source = "AI Contact Agent"
                    print(f"[Takedown] AI Crawler found: {detected_email}")
            except Exception as e:
                print(f"AI Crawler failed: {e}")

        # --- LAYER 2: WHOIS (deep field search + rawText scrape) ---
        if not detected_email or "@" not in str(detected_email):
            print(f"[Takedown] Trying WHOIS for: {domain}")
            record = get_whois_data(domain)
            detected_email, source = extract_email_from_whois(record)
            if detected_email:
                print(f"[Takedown] WHOIS found: {detected_email} via {source}")

        # --- LAYER 3: Hosting provider abuse contact via IP lookup ---
        if not detected_email or "@" not in str(detected_email):
            print(f"[Takedown] Trying host IP abuse lookup for: {domain}")
            detected_email, source = get_hosting_abuse_email(domain)
            if detected_email:
                print(f"[Takedown] Host abuse email found: {detected_email} via {source}")

        # --- LAYER 4: Heuristic guess using the CLEAN domain ---
        if not detected_email or "@" not in str(detected_email):
            detected_email = f"abuse@{domain}"
            source = "Heuristic Guess"
            print(f"[Takedown] Falling back to heuristic: {detected_email}")

        is_abuse = any(k in str(detected_email).lower() for k in ["abuse", "legal", "registrar", "copyright"])

        save_takedown_to_history(url, detected_email, is_abuse, source)

        return {
            "target_url": url,
            "domain_used": domain,
            "email": detected_email,
            "is_official_abuse": is_abuse,
            "source": source,
            "status": "success"
        }

    except Exception as e:
        print(f"Takedown Route Critical Error: {e}")
        return {
            "target_url": url,
            "email": f"abuse@{domain}",
            "is_official_abuse": False,
            "source": "Error Fallback",
            "status": "partial_success"
        }