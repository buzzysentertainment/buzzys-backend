from fastapi import APIRouter, Depends
from app.auth import verify_admin_token
from app.services.firebase_setup import db

router = APIRouter()

# Default pricing structure (matches your prices.js)
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
# GET PRICING (admin only) — WITH AUTO‑REPAIR
# -------------------------------------------------
@router.get("/pricing")
def get_pricing(user=Depends(verify_admin_token)):
    doc_ref = db.collection("settings").document("pricing")
    doc = doc_ref.get()

    # Load existing data if present
    data = doc.to_dict() if doc.exists else None

    # If missing entirely OR missing items → rebuild full structure
    if not data or "items" not in data or not isinstance(data.get("items"), dict):
        doc_ref.set(DEFAULT_PRICING)
        return {"pricing": DEFAULT_PRICING}

    repaired = False

    # Ensure all top-level fields exist
    for key, value in DEFAULT_PRICING.items():
        if key not in data:
            data[key] = value
            repaired = True

    # Ensure items object exists
    if "items" not in data or not isinstance(data["items"], dict):
        data["items"] = DEFAULT_PRICING["items"]
        repaired = True

    # Ensure each inflatable/add-on exists
    for item_key, item_value in DEFAULT_PRICING["items"].items():
        if item_key not in data["items"]:
            data["items"][item_key] = item_value
            repaired = True

    # Write repaired version back to Firestore
    if repaired:
        doc_ref.set(data)

    return {"pricing": data}


# -------------------------------------------------
# UPDATE PRICING (admin only)
# -------------------------------------------------
@router.put("/pricing")
def update_pricing(data: dict, user=Depends(verify_admin_token)):
    """
    Accepts full or partial pricing updates.
    merge=True ensures only changed fields are overwritten.
    """
    db.collection("settings").document("pricing").set(data, merge=True)
    return {"success": True}
