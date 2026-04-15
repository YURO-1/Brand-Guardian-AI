import os
import json
import shutil
import numpy as np
import torch
from fastapi import APIRouter, File, UploadFile, HTTPException, Form, Request
from PIL import Image

# --- NUMPY 2.x COMPATIBILITY PATCH ---
if not hasattr(np, "float"):
    np.float = float
if not hasattr(np, "int"):
    np.int = int

router = APIRouter(tags=["Logo Management"])

# 1. SETUP PATHS
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# Adjusted to ensure we find the root 'data' folder correctly
BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "../../")) 
UPLOAD_DIR = os.path.join(BASE_DIR, "data", "official_logos")
DB_PATH = os.path.join(BASE_DIR, "data", "logos_db.json")

# Ensure directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload")
async def upload_logo(
    request: Request, 
    name: str = Form(...),
    description: str = Form(""), 
    file: UploadFile = File(...)
):
    # Validation: Ensure it's an image
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an image.")

    # 1. Save the image file safely
    # Use a clean filename to avoid path traversal issues
    clean_filename = f"{name.replace(' ', '_')}_{file.filename}"
    file_location = os.path.join(UPLOAD_DIR, clean_filename)
    
    try:
        await file.seek(0)
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save image: {str(e)}")

    # 2. AI ENCODING: Call the Lazy Loader
    try:
        # CRITICAL FIX: Trigger the model loading if it's None
        if hasattr(request.app.state, "get_clip_model"):
            model, preprocess = request.app.state.get_clip_model()
        else:
            # Fallback if the helper isn't attached
            model = getattr(request.app.state, "model", None)
            preprocess = getattr(request.app.state, "preprocess", None)

        if model is None or preprocess is None:
            raise ValueError("AI Engine failed to initialize. Check server logs.")

        # Open image for AI processing
        img = Image.open(file_location).convert("RGB")
        
        # CLIP Preprocessing
        image_input = preprocess(img).unsqueeze(0).to("cpu") # Force CPU
        
        with torch.no_grad():
            # Use the model directly
            image_features = model.encode_image(image_input)
            # Normalize vector for cosine similarity math
            image_features /= image_features.norm(dim=-1, keepdim=True)
            
        # Convert tensor to list for JSON storage
        embedding = image_features.cpu().numpy().flatten().tolist()
        
    except Exception as e:
        # Clean up the file if AI processing fails
        if os.path.exists(file_location):
            os.remove(file_location)
        print(f"Embedding Error: {str(e)}") # Visible in your terminal
        raise HTTPException(status_code=500, detail=f"AI Embedding failed: {str(e)}")

    # 3. PERSISTENCE: Update JSON Database
    logos_db = {}
    if os.path.exists(DB_PATH):
        try:
            with open(DB_PATH, "r") as f:
                content = f.read()
                if content:
                    logos_db = json.loads(content)
        except Exception:
            logos_db = {}

    # Save entry
    from datetime import datetime
    logos_db[name] = {
        "original_filename": file.filename,
        "description": description,
        "path": file_location,
        "embedding": embedding,
        "registered_at": datetime.now().isoformat()
    }

    try:
        with open(DB_PATH, "w") as f:
            json.dump(logos_db, f, indent=4)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to write to database.")

    return {
        "status": "success",
        "message": f"Brand '{name}' registered and AI features extracted.",
        "brand_name": name
    }