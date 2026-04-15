from fastapi import APIRouter

router = APIRouter()

@router.post("/evaluate")
def evaluate_risk(confidence: int):

    if confidence >= 90:
        risk = "High"
    elif confidence >= 80:
        risk = "Medium"
    else:
        risk = "Low"

    return {"risk_level": risk}