from fastapi import APIRouter, Depends
from app.auth import verify_admin_token
from app.services.firebase_setup import db

router = APIRouter()

DEFAULT_HOMEPAGE = {
    "heroTitle": "Welcome to Buzzy's Inflatables!",
    "heroSubtitle": "Fun for every event",
    "heroImage": "",
    "ctaText": "Book Now",
}

@router.get("/homepage")
def get_homepage(user=Depends(verify_admin_token)):
    doc = db.collection("settings").document("homepage").get()
    if not doc.exists:
        db.collection("settings").document("homepage").set(DEFAULT_HOMEPAGE)
        return {"homepage": DEFAULT_HOMEPAGE}
    return {"homepage": doc.to_dict()}

@router.post("/homepage/update")
def update_homepage(data: dict, user=Depends(verify_admin_token)):
    db.collection("settings").document("homepage").set(data, merge=True)
    return {"success": True}
