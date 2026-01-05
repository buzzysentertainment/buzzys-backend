from fastapi import APIRouter, Depends
from app.auth import verify_admin_token
from app.services.firebase_setup import db

router = APIRouter()

DEFAULT_PRICING = {
    "taxRate": 0.09,
    "deliveryFee": 25,
    "weekendSurcharge": 15,
}

@router.get("/pricing")
def get_pricing(user=Depends(verify_admin_token)):
    doc = db.collection("settings").document("pricing").get()
    if not doc.exists:
        db.collection("settings").document("pricing").set(DEFAULT_PRICING)
        return {"pricing": DEFAULT_PRICING}
    return {"pricing": doc.to_dict()}

@router.post("/pricing/update")
def update_pricing(data: dict, user=Depends(verify_admin_token)):
    db.collection("settings").document("pricing").set(data, merge=True)
    return {"success": True}
