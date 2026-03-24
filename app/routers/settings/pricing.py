from fastapi import APIRouter, Depends, HTTPException
from app.auth import verify_admin_token
from app.services.firebase_setup import db

router = APIRouter()

# -------------------------------------------------
# MASTER PRICING SCHEMA (Source of Truth)
# -------------------------------------------------
DEFAULT_PRICING = {
    "taxRate": 0.09,
    "deliveryFee": 25,
    "weekendSurcharge": 15,

    "items": {
        # SLIDES
        "volcano19": { "dry": 390, "wet": 415 },
        "funSplash15": { "dry": 275, "wet": 325 },
        "rainbowRush18": { "dry": 375, "wet": 425 },
        "dolphin16": { "dry": 350, "wet": 400 },

        # COMBOS
        "doubleJumbo": { "dry": 320, "wet": 355 },
        "primaryCombo": { "dry": 270, "wet": 320 },
        "princessCombo": { "dry": 270, "wet": 320 },
        "whitePrincess": { "dry": 290, "wet": 340 },

        # BOUNCE HOUSES
        "primaryBounce": { "dry": 270, "wet": 320 },

        # OBSTACLE COURSES
        "funRunObstacle": { "dry": 370, "wet": 420 },

        # ADD‑ONS
        "softPlay": { "price": 320 },
        "foamBlaster": { "price": 275, "extra6Hours": 125 },
        "snowCone": { "price": 90, "extraSyrup": 25 }
    }
}

# -------------------------------------------------
# GET PRICING — WITH AUTO‑REPAIR
# -------------------------------------------------
@router.get("/pricing")
def get_pricing(user=Depends(verify_admin_token)):
    try:
        doc_ref = db.collection("settings").document("pricing")
        doc = doc_ref.get()

        # Load existing data or start fresh
        data = doc.to_dict() if doc.exists else None

        # Rebuild full structure if the document is missing or corrupted
        if not data or "items" not in data or not isinstance(data.get("items"), dict):
            doc_ref.set(DEFAULT_PRICING)
            return {"pricing": DEFAULT_PRICING}

        repaired = False

        # Check for missing top-level keys (taxRate, deliveryFee, etc.)
        for key, value in DEFAULT_PRICING.items():
            if key not in data:
                data[key] = value
                repaired = True

        # Check for missing individual inflatables/add-ons
        for item_key, item_value in DEFAULT_PRICING["items"].items():
            if item_key not in data["items"]:
                data["items"][item_key] = item_value
                repaired = True

        # If we had to fix anything, update the database silently
        if repaired:
            doc_ref.set(data)

        return {"pricing": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pricing Retrieval Error: {str(e)}")

# -------------------------------------------------
# UPDATE PRICING
# -------------------------------------------------
@router.put("/pricing")
def update_pricing(data: dict, user=Depends(verify_admin_token)):
    """
    Accepts full or partial pricing updates.
    merge=True ensures only changed fields are overwritten.
    """
    if not data:
        raise HTTPException(status_code=400, detail="Pricing update cannot be empty.")

    try:
        db.collection("settings").document("pricing").set(data, merge=True)
        return {"success": True, "message": "Pricing structure updated."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pricing Update Error: {str(e)}")