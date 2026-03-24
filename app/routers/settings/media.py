import uuid
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from app.auth import verify_admin_token
from app.services.firebase_setup import db, bucket
from google.cloud import firestore # Needed for ArrayUnion/Remove

router = APIRouter()

@router.get("/media")
def list_media(user=Depends(verify_admin_token)):
    doc = db.collection("settings").document("media").get()
    if not doc.exists:
        return {"files": []}
    return {"files": doc.to_dict().get("files", [])}

@router.post("/media/upload")
def upload_media(file: UploadFile = File(...), user=Depends(verify_admin_token)):
    try:
        file_id = str(uuid.uuid4())
        # Path in Firebase Storage
        blob = bucket.blob(f"media/{file_id}-{file.filename}")
        blob.upload_from_file(file.file, content_type=file.content_type)
        blob.make_public()

        entry = {
            "id": file_id,
            "name": file.filename,
            "url": blob.public_url,
        }

        # Use ArrayUnion to add only this file without fetching the whole list
        doc_ref = db.collection("settings").document("media")
        doc_ref.update({"files": firestore.ArrayUnion([entry])})

        return {"file": entry}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/media/{file_id}")
def delete_media(file_id: str, user=Depends(verify_admin_token)):
    doc_ref = db.collection("settings").document("media")
    data = doc_ref.get().to_dict() or {"files": []}
    
    # Find the specific object to remove (Firestore needs the whole object for ArrayRemove)
    file_to_remove = next((f for f in data["files"] if f["id"] == file_id), None)
    
    if file_to_remove:
        doc_ref.update({"files": firestore.ArrayRemove([file_to_remove])})
        # Optional: You could also delete the actual file from bucket here
        # bucket.blob(f"media/{file_id}-{file_to_remove['name']}").delete()

    return {"success": True}