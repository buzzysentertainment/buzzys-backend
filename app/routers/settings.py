from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from app.auth import verify_admin_token
from app.services.firebase_setup import db

router = APIRouter(prefix="/admin/settings", tags=["Admin Settings"])

# --- DATA MODELS (The Schema) ---

class SiteSettings(BaseModel):
    # Theme
    primary: str = "#ff7ac4"
    secondary: str = "#ffd166"
    accent: str = "#7bdff2"
    background: str = "#ffffff"
    card: str = "#f9f9ff"
    text: str = "#222222"
    radius: int = 12
    
    # Homepage
    heroTitle: str = "Buzzy's Inflatable Rentals"
    heroSubtitle: str = "Best bounce houses in town!"
    heroButtonText: str = "Book Now"
    heroImage: str = ""
    announcement: str = ""
    showAnnouncement: bool = True
    showFeatured: bool = True
    featuredItems: List[str] = []

# --- ROUTES ---

@router.get("/all", response_model=SiteSettings)
def get_all_settings(admin=Depends(verify_admin_token)):
    """Fetches the global site configuration from Firestore."""
    try:
        doc_ref = db.collection("settings").document("site_config")
        doc = doc_ref.get()
        
        if doc.exists:
            return doc.to_dict()
        
        # If no config exists, return the default model values
        return SiteSettings().dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch settings: {str(e)}")

@router.put("/all")
def update_all_settings(settings: SiteSettings, admin=Depends(verify_admin_token)):
    """Overwrites the site configuration with the new draft from the frontend."""
    try:
        doc_ref = db.collection("settings").document("site_config")
        # Save the validated data
        doc_ref.set(settings.dict(), merge=True)
        return {"status": "success", "message": "Site configuration published live."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database write failed: {str(e)}")