]from fastapi import APIRouter, Depends, HTTPException
from app.auth import verify_admin_token
from app.services.firebase_setup import db

router = APIRouter()

# Aligned with your AdminSettings.jsx defaults
DEFAULT_THEME = {
    "primary": "#ffb800",
    "secondary": "#ffe680",
    "accent": "#ff7f00",
    "background": "#ffffff",
    "card": "#f7f7f7",
    "text": "#000000",
    "radius": 12,
}

@router.get("/theme")
def get_theme(user=Depends(verify_admin_token)):
    try:
        doc = db.collection("settings").document("theme").get()
        if not doc.exists:
            # Initialize with defaults if empty
            db.collection("settings").document("theme").set(DEFAULT_THEME)
            return DEFAULT_THEME
        return doc.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/theme/update")
def update_theme(data: dict, user=Depends(verify_admin_token)):
    try:
        # merge=True prevents overwriting fields if you add more later
        db.collection("settings").document("theme").set(data, merge=True)
        return {"success": True, "updated_data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Firestore error: {str(e)}")