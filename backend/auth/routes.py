import json
import os
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr

router = APIRouter(tags=["Authentication"])


BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_FILE = os.path.join(BASE_DIR, "users_db.json")

class AuthRequest(BaseModel):
    
    email: EmailStr 
    password: str

def load_users():
    
    if not os.path.exists(DB_FILE):
        return {}
    
    try:
        with open(DB_FILE, "r") as f:
            
            content = f.read()
            if not content:
                return {}
            return json.loads(content)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

def save_users(users):
    with open(DB_FILE, "w") as f:
        json.dump(users, f, indent=4)

@router.post("/register")
async def register(data: AuthRequest):
    users = load_users()
    
    # Normalize email to lowercase to prevent "User@Gmail.com" vs "user@gmail.com" issues
    email_key = data.email.lower()

    if email_key in users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="User already exists"
        )

    users[email_key] = {
        "password": data.password
    }
    
    save_users(users)
    return {"message": "User registered successfully"}

@router.post("/login")
async def login(data: AuthRequest):
    users = load_users()
    email_key = data.email.lower()
    
    user = users.get(email_key)
    if not user or user["password"] != data.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid email or password"
        )

    return {
        "message": "Login successful",
        "user_email": email_key
    }