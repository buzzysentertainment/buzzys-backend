import uuid
from fastapi import APIRouter, UploadFile, File, Depends
from app.auth import verify_admin_token
from app.services.firebase_setup import db, bucket

router = APIRouter()

@router.get("/media")
def list_media(user=Depends(verify_admin_token)):
    doc = db.collection("settings").document("media").get()
    if not doc.exists:
        db.collection("settings").document("media").set({"files": []})
        return {"files": []}
    return {"files": doc.to_dict().get("files", [])}

@router.post("/media/upload")
def upload_media(file: UploadFile = File(...), user=Depends(verify_admin_token)):
    file_id = str(uuid.uuid4())
    blob = bucket.blob(f"media/{file_id}-{file.filename}")
    blob.upload_from_file(file.file, content_type=file.content_type)
    blob.make_public()

    entry = {
        "id": file_id,
        "name": file.filename,
        "url": blob.public_url,
    }

    doc = db.collection("settings").document("media")
    current = doc.get().to_dict() or {"files": []}
    current["files"].append(entry)
    doc.set(current)

    return {"file": entry}

@router.delete("/media/{file_id}")
def delete_media(file_id: str, user=Depends(verify_admin_token)):
    doc = db.collection("settings").document("media")
    data = doc.get().to_dict() or {"files": []}

    updated = [f for f in data["files"] if f["id"] != file_id]
    doc.set({"files": updated})

    return {"success": True}

@router.post("/media/{file_id}/rename")
def rename_media(file_id: str, payload: dict, user=Depends(verify_admin_token)):
    new_name = payload.get("name")

    doc = db.collection("settings").document("media")
    data = doc.get().to_dict() or {"files": []}

    for f in data["files"]:
        if f["id"] == file_id:
            f["name"] = new_name

    doc.set(data)
    return {"success": True}
