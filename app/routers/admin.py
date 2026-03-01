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
        
        # FIX: Normalize name and date so the Dashboard table isn't blank
        data["name"] = data.get("name") or data.get("customer_name") or "Unknown"
        data["date"] = data.get("date") or data.get("eventDate") or "TBD"
        
        # FIX: Pull total from the pricing breakdown map
        pricing = data.get("pricing_breakdown", {})
        data["total"] = pricing.get("total") or data.get("total") or 0
        
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
    
    # Normalize for the popup modal
    data["name"] = data.get("name") or data.get("customer_name") or "Unknown"
    data["date"] = data.get("date") or data.get("eventDate") or "TBD"
    
    pricing = data.get("pricing_breakdown", {})
    data["total"] = pricing.get("total") or data.get("total") or 0
    
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
    # Field is now 'date' to match your Emily records
    bookings_ref = db.collection("bookings").where("date", "==", date)
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
# -------------------------
# CALENDAR EVENTS (grouped by date)
# -------------------------
@router.get("/calendar")
def get_calendar_events(user=Depends(verify_admin_token)):
    docs = db.collection("bookings").stream()
    events_by_date = {}

    for doc in docs:
        data = doc.to_dict()
        
        # FIX: Check both "date" (new) and "eventDate" (old)
        date = data.get("date") or data.get("eventDate")

        if not date:
            continue

        if date not in events_by_date:
            events_by_date[date] = []

        # FIX: Pull total from pricing_breakdown map or top-level total
        pricing = data.get("pricing_breakdown", {})
        total_val = pricing.get("total") or data.get("total") or 0

        events_by_date[date].append({
            "id": doc.id,
            "name": data.get("name") or data.get("customer_name") or "Unknown",
            "email": data.get("email"),
            "phone": data.get("phone"),
            "items": data.get("items"),
            "total": total_val,
            "status": data.get("status"),
        })

    return {"events": events_by_date}
