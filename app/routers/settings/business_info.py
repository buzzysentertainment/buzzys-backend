from fastapi import APIRouter, Depends
from app.auth import verify_admin_token
from app.services.firebase_setup import db

router = APIRouter()

DEFAULT_INFO = {
    "businessName": "Buzzy's Inflatables",
    "phone": "",
    "email": "",
    "address": "",
    "hours": "",
}

@router.get("/business-info")
def get_info(user=Depends(verify_admin_token)):
    doc = db.collection("settings").document("business_info").get()
    if not doc.exists:
        db.collection("settings").document("business_info").set(DEFAULT_INFO)
        return {"info": DEFAULT_INFO}
    return {"info": doc.to_dict()}

@router.post("/business-info/update")
def update_info(data: dict, user=Depends(verify_admin_token)):
    db.collection("settings").document("business_info").set(data, merge=True)
    return {"success": True}
