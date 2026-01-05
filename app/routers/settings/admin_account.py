from fastapi import APIRouter, Depends, HTTPException
from app.auth import verify_admin_token, hash_password, verify_password
from app.services.firebase_setup import db

router = APIRouter()

DEFAULT_ACCOUNT = {
    "email": "",
    "enable2FA": False,
}

@router.get("/account")
def get_account(user=Depends(verify_admin_token)):
    doc = db.collection("settings").document("admin_account").get()
    if not doc.exists:
        db.collection("settings").document("admin_account").set(DEFAULT_ACCOUNT)
        return {"account": DEFAULT_ACCOUNT}
    return {"account": doc.to_dict()}

@router.post("/account/update")
def update_account(data: dict, user=Depends(verify_admin_token)):
    doc_ref = db.collection("settings").document("admin_account")

    # Handle password change
    if data.get("currentPassword"):
        admin_doc = doc_ref.get().to_dict() or DEFAULT_ACCOUNT
        stored_hash = admin_doc.get("passwordHash")

        if stored_hash and not verify_password(data["currentPassword"], stored_hash):
            raise HTTPException(status_code=400, detail="Incorrect current password")

        if data.get("newPassword"):
            new_hash = hash_password(data["newPassword"])
            doc_ref.set({"passwordHash": new_hash}, merge=True)

    # Update other fields
    doc_ref.set({
        "email": data.get("email"),
        "enable2FA": data.get("enable2FA"),
    }, merge=True)

    return {"success": True}
