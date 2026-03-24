from fastapi import APIRouter, Depends, HTTPException
from app.auth import verify_admin_token
from app.services.firebase_setup import db

router = APIRouter()

# -------------------------------------------------
# MASTER BOOKING RULES (Source of Truth)
# -------------------------------------------------
DEFAULT_RULES = {
    "blackoutDates": [],          # List of ISO strings (YYYY-MM-DD)
    "maxBookingsPerDay": 3,      # Prevents logistics nightmares
    "earliestStart": "07:00",    # 24hr format
    "latestEnd": None,        
    "depositPercent": 35,        # 35% of total
    "cancellationPolicy": "No refunds. Cancellations will receive a credit for a future reschedule.",
    "allowOvernight": True,
}

# -------------------------------------------------
# GET RULES
# -------------------------------------------------
@router.get("/booking-rules")
def get_rules(user=Depends(verify_admin_token)):
    try:
        doc_ref = db.collection("settings").document("booking_rules")
        doc = doc_ref.get()

        if not doc.exists:
            # Initialize Firestore with defaults
            doc_ref.set(DEFAULT_RULES)
            return DEFAULT_RULES
        
        # Merge defaults into existing data to catch any new rule fields added to code
        data = doc.to_dict()
        for key, val in DEFAULT_RULES.items():
            if key not in data:
                data[key] = val
        
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rules Retrieval Error: {str(e)}")

# -------------------------------------------------
# UPDATE RULES
# -------------------------------------------------
@router.post("/booking-rules/update")
def update_rules(data: dict, user=Depends(verify_admin_token)):
    """
    Updates the business constraints. 
    Includes a basic safety check for the deposit percentage.
    """
    if not data:
        raise HTTPException(status_code=400, detail="No rule data provided.")

    # Safety Check: Don't let them set a 500% deposit or negative
    deposit = data.get("depositPercent")
    if deposit is not None and (deposit < 0 or deposit > 100):
        raise HTTPException(status_code=400, detail="Deposit must be between 0 and 100.")

    try:
        db.collection("settings").document("booking_rules").set(data, merge=True)
        return {"success": True, "message": "Booking rules updated."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rules Update Error: {str(e)}")