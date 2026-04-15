import numpy as np
# --- CRITICAL FIX FOR PYTHON 3.13 & NUMPY 2.x ---
# This must remain at the top to prevent CLIP from crashing with a 500 error
if not hasattr(np, "float"):
    np.float = float
if not hasattr(np, "int"):
    np.int = int
if not hasattr(np, "bool"):
    np.bool = bool

import torch
import clip
import time
import os
import json
import re
import requests
import httpx  # Faster and lighter than Selenium for cloud
import gc     # Garbage collector to manually free RAM
from urllib.parse import urlparse 
from google import genai 
from google.genai import types
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import uvicorn

# 1. LOAD ENVIRONMENT VARIABLES
load_dotenv()
WHOIS_API_KEY = os.getenv("WHOIS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- IMPORT FIX FOR RENDER & LOCAL ---
try:
    from auth.routes import router as auth_router
    from logo.routes import router as logo_router
    from detection.routes import router as detection_router
    from risk.routes import router as risk_router
    from takedown.routes import router as takedown_router
    from reports.routes import router as reports_router
except ImportError:
    from backend.auth.routes import router as auth_router
    from backend.logo.routes import router as logo_router
    from backend.detection.routes import router as detection_router
    from backend.risk.routes import router as risk_router
    from backend.takedown.routes import router as takedown_router
    from backend.reports.routes import router as reports_router

app = FastAPI(title="BrandGuardian AI - Cloud Edition")

# Ensure data, temp, and upload directories exist
os.makedirs("data", exist_ok=True)
os.makedirs("temp_reports", exist_ok=True)
os.makedirs("uploads", exist_ok=True) # Added to prevent upload crash

# 2. ML MODEL LOADING (Memory Optimized / Lazy Loading)
app.state.model = None
app.state.preprocess = None
device = "cpu" 
MODEL_NAME = "ViT-B/32"

def get_clip_model():
    """
    Loads the CLIP model only when called. 
    """
    if app.state.model is None:
        print(f"--- Lazy Loading {MODEL_NAME} ---")
        gc.collect()  
        try:
            with torch.no_grad():
                # Force loading on CPU for compatibility and RAM management
                model, preprocess = clip.load(MODEL_NAME, device=device)
                model.eval()
                app.state.model = model
                app.state.preprocess = preprocess
            print("--- Model Loaded Successfully ---")
        except RuntimeError as e:
            if "SHA256 checksum" in str(e):
                print("⚠️ Checksum mismatch. Attempting manual bypass...")
                cache_dir = os.path.expanduser("~/.cache/clip")
                os.makedirs(cache_dir, exist_ok=True)
                model, preprocess = clip.load(MODEL_NAME, device=device, download_root=cache_dir)
                app.state.model = model
                app.state.preprocess = preprocess
            else:
                raise e
        gc.collect()
    return app.state.model, app.state.preprocess

# 3. GEMINI AI CONFIGURATION 
client = genai.Client(
    api_key=GEMINI_API_KEY,
    http_options={'api_version': 'v1'}
)
app.state.gemini_client = client

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. WHOIS FALLBACK LOGIC
def get_whois_contact(domain: str):
    if not WHOIS_API_KEY:
        return None
    try:
        whois_url = f"https://www.whoisxmlapi.com/whoisserver/WhoisService?apiKey={WHOIS_API_KEY}&domainName={domain}&outputFormat=JSON"
        response = requests.get(whois_url, timeout=10)
        data = response.json()
        record = data.get("WhoisRecord", {})
        email = (record.get("registrant", {}).get("email") or 
                 record.get("administrativeContact", {}).get("email"))
        return email if email else "abuse@registrar-not-found.com"
    except Exception as e:
        print(f"WHOIS API Error: {e}")
        return None

# 5. LIGHTWEIGHT CONTACT CRAWLER
async def find_contact_email_with_ai(target_url: str):
    parsed = urlparse(target_url)
    domain_parts = parsed.netloc.split('.')
    base_domain = ".".join(domain_parts[-2:]) if len(domain_parts) > 2 else parsed.netloc
    base_site = f"{parsed.scheme}://{base_domain}"
    
    combined_raw_text = ""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) BrandGuardian-Bot/1.0"}

    async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client_http:
        for url in [f"{base_site}/pages/contact", f"{base_site}/policies/legal-notice", base_site]:
            try:
                resp = await client_http.get(url)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    combined_raw_text += soup.get_text(separator=' ')
                    if "@" in combined_raw_text: break
            except: continue

    if not combined_raw_text:
        return get_whois_contact(base_domain) or "Manual search required"

    prompt = f"Extract the legal or abuse email for {base_domain} from this text: {combined_raw_text[:2500]}. Return ONLY the email."
    
    try:
        response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
        result = response.text.strip()
        if "@" in result: return result
    except:
        return get_whois_contact(base_domain) or "Manual search required"

# 6. LIGHTWEIGHT SCRAPER
def scrape_suspicious_images(brand_query: str):
    search_url = f"https://www.bing.com/images/search?q={brand_query}+official+store+sale"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        response = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        results = soup.find_all('a', class_='iusc') 
        
        urls = []
        for res in results:
            try:
                m_data = json.loads(res.get('m'))
                img_url = m_data.get('murl')
                if img_url and "bing.net" not in img_url:
                    urls.append(img_url)
            except: continue 
        return list(dict.fromkeys(urls))[:20] 
    except:
        return []

# 7. ATTACH HELPERS
app.state.get_clip_model = get_clip_model
app.state.scraper = scrape_suspicious_images
app.state.contact_crawler = find_contact_email_with_ai 

# 8. ROUTER INCLUSION 
app.include_router(auth_router, prefix="/auth")
app.include_router(logo_router, prefix="/logo")
app.include_router(detection_router, prefix="/detection")
app.include_router(risk_router, prefix="/risk")
app.include_router(takedown_router, prefix="/takedown")
app.include_router(reports_router, prefix="/reports")

@app.get("/")
def root():
    return {
        "status": "Active", 
        "environment": "Cloud-Optimized", 
        "model_status": "Ready (Lazy Load)" if app.state.model is None else "Loaded",
        "whois_loaded": WHOIS_API_KEY is not None
    }

if __name__ == "__main__":
    # KILL GHOST PROCESSES: 
    # Make sure you kill existing python tasks in your terminal before running this!
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, workers=1)