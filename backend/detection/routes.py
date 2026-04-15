import os
import json
import torch
import requests
import io
import time
import numpy as np
from PIL import Image
from fastapi import APIRouter, HTTPException, Request
from concurrent.futures import ThreadPoolExecutor

router = APIRouter(tags=["Detection"])

# 1. SETUP PATHS
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "logos_db.json")
HISTORY_PATH = os.path.join(BASE_DIR, "data", "detections_history.json")

os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)

# 🚀 SHARED SESSION
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) BrandGuardian-Bot/1.0",
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
})

def get_embedding_from_url(url, model, preprocess, device):
    """Downloads and processes a single image into an AI vector."""
    try:
        response = session.get(url, timeout=5, stream=True)
        content_type = response.headers.get('Content-Type', '')
        if 'image' not in content_type:
            return None

        image_bytes = response.content
        if len(image_bytes) < 8000: 
            return None

        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        image_input = preprocess(image).unsqueeze(0).to(device)
        
        with torch.no_grad():
            image_features = model.encode_image(image_input)
            image_features /= image_features.norm(dim=-1, keepdim=True)
            
        return image_features.cpu().numpy().flatten()
    except:
        return None

def save_detection_to_history(new_matches, brand_name):
    """Saves matches to a JSON file for the Report Generator."""
    history = []
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, "r") as f:
                history = json.load(f)
        except:
            history = []

    for match in new_matches:
        entry = {
            "brand": brand_name,
            "url": match["url"],
            "confidence": match["confidence"],
            "risk": match["risk"],
            "description": match.get("description", "No reasoning provided."),
            "timestamp": time.time(),
            "date_str": time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "detected"
        }
        history.append(entry)

    with open(HISTORY_PATH, "w") as f:
        json.dump(history, f, indent=4)

@router.post("/scan")
async def run_detection(brand_name: str, request: Request):
    """Main scanning endpoint optimized for Cloud."""
    start_time = time.time()
    
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="No logos registered.")
    
    with open(DB_PATH, "r") as f:
        try:
            logos_db = json.load(f)
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="Logos database is corrupted.")
    
    if brand_name not in logos_db:
        raise HTTPException(status_code=404, detail=f"Brand '{brand_name}' not found.")
    
    official_vec = np.array(logos_db[brand_name]["embedding"])
    norm = np.linalg.norm(official_vec)
    if norm > 0:
        official_vec = official_vec / norm

    scraper = request.app.state.scraper
    found_urls = scraper(brand_name) 
    
    if not found_urls:
        return {"message": "No images found.", "matches": [], "scan_time_seconds": round(time.time() - start_time, 2)}

    model = request.app.state.model
    preprocess = request.app.state.preprocess
    device = "cpu"

    # --- 🚀 MULTI-THREADED IMAGE ANALYSIS ---
    def process_and_compare(url):
        web_vec = get_embedding_from_url(url, model, preprocess, device)
        if web_vec is not None:
            similarity = float(np.dot(official_vec, web_vec))
            
            if similarity > 0.38:
                if similarity > 0.65:
                    risk = "High"
                elif similarity > 0.50:
                    risk = "Medium"
                else:
                    risk = "Low"

                # --- GENERATE AI REASONING (The "Intelligence" Step) ---
                # We use a placeholder here or call a small helper that triggers Gemini 
                # based on your brand name and the context of the find.
                reasoning = (
                    f"The AI detected a {similarity*100:.1f}% visual match for {brand_name}. "
                    f"In a {risk} risk context, this suggests unauthorized usage likely intended "
                    f"to leverage brand equity for deceptive purposes."
                )

                return {
                    "url": url,
                    "confidence": f"{round(similarity * 100)}%",
                    "risk_level": risk,      # Changed to match frontend select box
                    "description": reasoning # Added for the Reasoning Section
                }
        return None

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(process_and_compare, found_urls))
    
    matches = [r for r in results if r is not None]

    if matches:
        save_detection_to_history(matches, brand_name)

    return {
        "brand": brand_name,
        "total_scanned": len(found_urls),
        "matches": matches,
        "saved_to_history": len(matches),
        "scan_time_seconds": round(time.time() - start_time, 2)
    }