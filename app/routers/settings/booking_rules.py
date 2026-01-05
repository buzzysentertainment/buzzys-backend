from fastapi import APIRouter, Depends
from app.auth import verify_admin_token
from app.services.firebase_setup import db

router = APIRouter()

DEFAULT_RULES = {
    "blackoutDates": [],
    "maxBookingsPerDay": 3,
    "earliestStart": "08:00",
    "latestEnd": "10:00",
    "depositPercent": 35,
    "cancellationPolicy": "",
}

@router.get("/booking-rules")
def get_rules(user=Depends(verify_admin_token)):
    doc = db.collection("settings").document("booking_rules").get()
    if not doc.exists:
        db.collection("settings").document("booking_rules").set(DEFAULT_RULES)
        return {"rules": DEFAULT_RULES}
    return {"rules": doc.to_dict()}

@router.post("/booking-rules/update")
def update_rules(data: dict, user=Depends(verify_admin_token)):
    db.collection("settings").document("booking_rules").set(data, merge=True)
    return {"success": True}
