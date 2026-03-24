from fastapi import APIRouter, Depends, HTTPException
from app.auth import verify_admin_token
from app.services.firebase_setup import db

router = APIRouter()

# Aligned with HomepageSettings.jsx and AdminSettings.jsx
DEFAULT_HOMEPAGE = {
    "heroTitle": "Buzzy's Inflatable Rentals",
    "heroSubtitle": "Best bounce houses in town!",
    "heroButtonText": "Book Now",
    "heroImage": "",
    "announcement": "Now booking for Summer 2026!",
    "showAnnouncement": True,
    "showFeatured": True,
    "featuredItems": []
}

@router.get("/homepage")
def get_homepage(user=Depends(verify_admin_token)):
    try:
        doc = db.collection("settings").document("homepage").get()
        if not doc.exists:
            # Initialize Firestore with defaults if empty
            db.collection("settings").document("homepage").set(DEFAULT_HOMEPAGE)
            return DEFAULT_HOMEPAGE
        
        # Return the data directly to simplify frontend setPreviewData(res.data)
        return doc.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/homepage/update")
def update_homepage(data: dict, user=Depends(verify_admin_token)):
    try:
        # merge=True protects any fields you might add later (like SEO tags)
        db.collection("settings").document("homepage").set(data, merge=True)
        return {"success": True, "updated_data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Firestore error: {str(e)}")