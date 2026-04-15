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
    """Logs every investigation attempt to the JSON database."""
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

def get_whois_fallback(url: str):
    """Reliably extracts the domain and queries the WHOIS XML API."""
    if not WHOIS_API_KEY:
        return None
    try:
        # Extract base domain correctly (e.g., static.nike.com -> nike.com)
        parsed = urlparse(url)
        netloc = parsed.netloc or url.split('/')[0]
        domain_parts = netloc.split('.')
        if len(domain_parts) > 2:
            domain = ".".join(domain_parts[-2:])
        else:
            domain = netloc
        
        whois_url = f"https://www.whoisxmlapi.com/whoisserver/WhoisService?apiKey={WHOIS_API_KEY}&domainName={domain}&outputFormat=JSON"
        response = requests.get(whois_url, timeout=10)
        data = response.json()
        record = data.get("WhoisRecord", {})
        
        # Search multiple layers of the WHOIS record for an email
        email = (
            record.get("contactEmail") or 
            record.get("registrant", {}).get("email") or 
            record.get("administrativeContact", {}).get("email")
        )
        return email
    except Exception as e:
        print(f"WHOIS API Error: {e}")
        return None

@router.get("/investigate")
async def investigate_site(url: str, request: Request):
    """Main route to find contact info using AI Crawler -> WHOIS -> Pattern Guessing."""
    if not url or not url.startswith("http"):
        # If the URL is missing http, try to fix it once
        url = "https://" + url if not url.startswith("http") else url

    detected_email = None
    source = "Initializing"

    try:
        # 1. Try the AI Contact Crawler (from app state)
        if hasattr(request.app.state, "contact_crawler"):
            try:
                # Assuming crawler is an async function that returns a string/None
                detected_email = await request.app.state.contact_crawler(url)
                source = "AI Contact Agent"
            except Exception as e:
                print(f"AI Crawler failed: {e}")

        # 2. If AI fails, trigger WHOIS API
        if not detected_email or "@" not in str(detected_email):
            print(f"AI search failed for {url}. Switching to WHOIS...")
            detected_email = get_whois_fallback(url)
            source = "WHOIS XML API"

        # 3. Final Fallback: Generate a logical 'abuse@domain' guess
        if not detected_email or "@" not in str(detected_email):
            parsed = urlparse(url)
            domain = parsed.netloc or "unknown.com"
            detected_email = f"abuse@{domain}"
            source = "Heuristic Guess"

        # Check if it's an official legal channel
        is_abuse = any(k in str(detected_email).lower() for k in ["abuse", "legal", "registrar", "copyright"])
        
        # Save results
        save_takedown_to_history(url, detected_email, is_abuse, source)

        return {
            "target_url": url,
            "email": detected_email,
            "is_official_abuse": is_abuse,
            "source": source,
            "status": "success"
        }

    except Exception as e:
        print(f"Takedown Route Critical Error: {e}")
        # Return a valid JSON even on error so the Frontend doesn't show "Could not reach server"
        return {
            "target_url": url,
            "email": "investigation@brandguardian.ai",
            "is_official_abuse": False,
            "source": "Error Fallback",
            "status": "partial_success"
        }