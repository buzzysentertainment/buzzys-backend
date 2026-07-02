from fastapi import APIRouter, Depends, HTTPException
from app.auth import verify_admin_token
from app.services.firebase_setup import db
from google.cloud import firestore
from datetime import datetime

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
        
        pricing = data.get("pricing_breakdown") or {}
        data["name"] = data.get("name") or data.get("customer_name") or "Unknown"
        data["date"] = data.get("date") or data.get("eventDate") or "TBD"
        data["total"] = pricing.get("total") or data.get("total") or 0
        data["status"] = data.get("status") or "Pending" 
        data["items"] = data.get("items") or []
        data["deposit"] = pricing.get("deposit") or data.get("deposit") or 0
        data["remaining"] = pricing.get("remaining") or data.get("remaining") or 0
        data["deliveryTime"] = data.get("deliveryTime") or "TBD"
        data["partyDate"] = data.get("date") or data.get("eventDate") or "TBD"
        data["pickupTime"] = data.get("pickupTime") or "TBD"
        
        items = data.get("items") or []
        item_names = []
        wet_dry = []
        overnight = False
        
        for item in items:
            title = item.get("title") or item.get("name") or "Unknown Item"
            item_names.append(title)
            
            mode = item.get("mode")
            if mode:
                wet_dry.append(mode)
                
            if item.get("overnight") is True:
                overnight = True
                
        data["itemNames"] = ", ".join(item_names)      
        data["wetDry"] = ", ".join(wet_dry) if wet_dry else "N/A"
        data["overnight"] = "Yes" if overnight else "No"
        
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
    
    data["phone"] = data.get("phone") or ""
    data["address"] = data.get("address") or data.get("location") or "Not provided" 
    data["date"] = data.get("date") or data.get("eventDate") or "TBD" 
    data["deliveryTime"] = data.get("deliveryTime") or "TBD" 
    data["pickupTime"] = data.get("pickupTime") or "TBD" 
    pricing = data.get("pricing_breakdown", {}) 
    data["total"] = pricing.get("total") or data.get("total") or 0
    data["deposit"] = pricing.get("deposit") or data.get("deposit") or 0 
    data["remaining"] = pricing.get("remaining") or data.get("remaining") or 0 
    data["items"] = data.get("items") or []
    data["adminNote"] = data.get("adminNote") or "" 
    data["status"] = data.get("status") or "Pending" 
    data["history"] = data.get("history", [])

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
    
    
@router.patch("/bookings/{booking_id}")
def patch_booking(booking_id: str, updates: dict, user=Depends(verify_admin_token)):
    doc_ref = db.collection("bookings").document(booking_id)
    doc_ref.update(updates)

    # Optional: append to history
    doc_ref.update({
        "history": firestore.ArrayUnion([{
            "type": "update",
            "changes": updates,
            "timestamp": firestore.SERVER_TIMESTAMP
        }])
    })

    return {"message": "Booking updated"}
    
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
    
@router.get("/settings/promotions")
def get_promotions_settings(user=Depends(verify_admin_token)):
    doc_ref = db.collection("siteSettings").document("promotions").get()
    if not doc_ref.exists:
        return {"enabled": False, "message": ""}

    data = doc_ref.to_dict()
    return {
        "enabled": data.get("enabled", False),
        "message": data.get("message", "")
    }
# -------------------------
# CREATE NEW BOOKING (In-Person / Admin Manual)
# -------------------------
@router.post("/bookings")
def create_new_booking(booking_data: dict, user=Depends(verify_admin_token)):
    try:
        raw_date = booking_data.get("date") or booking_data.get("eventDate") or ""
        if not raw_date:
            raise HTTPException(status_code=400, detail="An event date is required.")
            
        booking_date = raw_date.split(" ")[0].strip()
        booking_data["date"] = booking_date
        booking_data["eventDate"] = booking_date
        
        requested_items = booking_data.get("items") or []
        requested_titles = [i.get("title") or i.get("name") for i in requested_items if i.get("title") or i.get("name")]
        
        # Pull all entries for this date to safely look for conflicts across active statuses
        bookings_ref = db.collection("bookings")
        date_query = bookings_ref.where("date", "==", booking_date).stream()
        
        for doc in date_query:
            existing = doc.to_dict()
            if existing.get("paymentStatus") == "failed":
                continue
            for existing_item in existing.get("items", []):
                existing_title = existing_item.get("title") or existing_item.get("name")
                if existing_title in requested_titles:
                   raise HTTPException(
                       status_code=400,
                       detail=f"Double-Booking Conflict! '{existing_title}' is already scheduled for {booking_date}."
                   )
        
        booking_data["status"] = booking_data.get("status") or "Active"
        booking_data["paymentStatus"] = booking_data.get("paymentStatus") or "confirmed"
        booking_data["createdAt"] = firestore.SERVER_TIMESTAMP
        booking_data["history"] = [{
            "type": "creation",
            "message": "Manual in-person order created by administrator.",
            "timestamp": datetime.utcnow().isoformat()
        }]

        new_doc_ref = db.collection("bookings").document()
        new_doc_ref.set(booking_data)
        
        return {
            "message": "In-person booking created successfully", 
            "id": new_doc_ref.id
        }
        
    except HTTPException as he:
        # Pass through the 400 double-booking messages cleanly
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create document: {str(e)}")
@router.put("/settings/promotions")
def update_promotions_settings(payload: dict, user=Depends(verify_admin_token)):
    enabled = payload.get("enabled", False)
    message = payload.get("message", "")

    db.collection("siteSettings").document("promotions").set({
        "enabled": enabled,
        "message": message,
        "updatedAt": firestore.SERVER_TIMESTAMP
    })

    return {"message": "Promotions updated"}
