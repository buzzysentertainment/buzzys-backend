from fastapi import APIRouter, Depends
from app.auth import verify_admin_token
from app.services.firebase_setup import db

router = APIRouter()

DEFAULT_THEME = {
    "primaryColor": "#ffcc00",
    "secondaryColor": "#000000",
    "buttonStyle": "rounded",
    "fontFamily": "Poppins",
}

@router.get("/theme")
def get_theme(user=Depends(verify_admin_token)):
    doc = db.collection("settings").document("theme").get()
    if not doc.exists:
        db.collection("settings").document("theme").set(DEFAULT_THEME)
        return {"theme": DEFAULT_THEME}
    return {"theme": doc.to_dict()}

@router.post("/theme/update")
def update_theme(data: dict, user=Depends(verify_admin_token)):
    db.collection("settings").document("theme").set(data, merge=True)
    return {"success": True}
