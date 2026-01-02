from fastapi import APIRouter, Depends, HTTPException
from app.auth import verify_admin_token
from app.services.firebase_setup import db

router = APIRouter(prefix="/admin", tags=["Admin"])


# -------------------------
# GET ALL BOOKINGS
# -------------------------
@router.get("/bookings")
def get_all_bookings(user=Depends(verify_admin_token)):
    bookings_ref = db.collection("bookings")
    docs = bookings_ref.stream()

    bookings = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        bookings.append(data)

    return {"bookings": bookings}


# -------------------------
# GET SINGLE BOOKING
# -------------------------
@router.get("/bookings/{booking_id}")
def get_booking(booking_id: str, user=Depends(verify_admin_token)):
    doc = db.collection("bookings").document(booking_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Booking not found")
    data = doc.to_dict()
    data["id"] = doc.id
    return data


# -------------------------
# UPDATE BOOKING (full update)
# -------------------------
@router.put("/bookings/{booking_id}")
def update_booking(booking_id: str, updated_data: dict, user=Depends(verify_admin_token)):
    db.collection("bookings").document(booking_id).update(updated_data)
    return {"message": "Booking updated successfully"}


# -------------------------
# UPDATE STATUS ONLY
# -------------------------
@router.patch("/bookings/{booking_id}/status")
def update_status(booking_id: str, status: str, user=Depends(verify_admin_token)):
    db.collection("bookings").document(booking_id).update({"status": status})
    return {"message": "Status updated"}


# -------------------------
# ADD ADMIN NOTE
# -------------------------
@router.post("/bookings/{booking_id}/note")
def add_note(booking_id: str, note: str, user=Depends(verify_admin_token)):
    doc_ref = db.collection("bookings").document(booking_id)
    doc_ref.update({"adminNote": note})
    return {"message": "Note added"}


# -------------------------
# DELETE BOOKING
# -------------------------
@router.delete("/bookings/{booking_id}")
def delete_booking(booking_id: str, user=Depends(verify_admin_token)):
    db.collection("bookings").document(booking_id).delete()
    return {"message": "Booking deleted"}


# -------------------------
# FILTER BY DATE
# -------------------------
@router.get("/bookings/date/{date}")
def filter_by_date(date: str, user=Depends(verify_admin_token)):
    # Firestore field is eventDate, not date
    bookings_ref = db.collection("bookings").where("eventDate", "==", date)
    docs = bookings_ref.stream()

    bookings = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        bookings.append(data)

    return {"bookings": bookings}


# -------------------------
# FILTER BY ITEM
# -------------------------
@router.get("/bookings/item/{item}")
def filter_by_item(item: str, user=Depends(verify_admin_token)):
    """
    Firestore cannot query inside arrays of maps unless the entire object matches.
    Your structure is:
        items: [ { title, image, price, mode } ]

    So instead of querying Firestore, we fetch all bookings and filter in Python.
    """

    docs = db.collection("bookings").stream()
    bookings = []

    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id

        # Check if ANY item title matches
        if "items" in data:
            for i in data["items"]:
                if i.get("title") == item:
                    bookings.append(data)
                    break

    return {"bookings": bookings}
