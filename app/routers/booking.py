from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.email_service import send_email
from app.services.firebase_setup import db
from square.client import Client
import os
import uuid

router = APIRouter(prefix="/book", tags=["booking"])

# -------------------------
# Booking Model
# -------------------------
class Booking(BaseModel):
    name: str
    email: str
    phone: str
    date: str
    items: list
    total: float

# -------------------------
# Create Booking (existing)
# -------------------------
@router.post("/")
def create_booking(booking: Booking):
    # Send confirmation email
    send_email(
        to=booking.email,
        subject="Your Buzzy’s Booking Confirmation",
        html=f"<h1>Thanks {booking.name}!</h1><p>Your booking for {booking.date} is confirmed.</p>"
    )

    # Send admin alert
    send_email(
        to="admin@buzzys.org",
        subject="New Booking Received",
        html=f"<p>New booking from {booking.name} on {booking.date}.</p>"
    )

    # Save booking to Firestore
    db.collection("bookings").add(booking.dict())

    return {"status": "success", "message": "Booking received"}

# -------------------------
# Get All Bookings (existing)
# -------------------------
@router.get("/all")
def get_all_bookings():
    docs = db.collection("bookings").stream()
    return [doc.to_dict() for doc in docs]

# -------------------------
# Create Square Checkout Link (UPDATED + ALIGNED)
# -------------------------
@router.post("/create-checkout")
def create_checkout(data: dict):
    client = Client(
        access_token=os.getenv("SQUARE_ACCESS_TOKEN"),
        environment="production"
    )

    location_id = os.getenv("SQUARE_LOCATION_ID")
    redirect_url = "https://www.buzzys.org/booking-success"

    # Extract cart items
    cart_items = data.get("cart", [])
    if not cart_items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    # Extract delivery address
    delivery_address = data.get("address", {})

    # Extract time slot + time period
    time_slot = data.get("timeSlot", "")
    time_period = data.get("timePeriod", "")

    # Build line items
    line_items = []
    for item in cart_items:
        line_items.append({
            "name": item.get("name", "Item"),
            "quantity": str(item.get("quantity", 1)),
            "base_price_money": {
                "amount": int(item.get("price", 0)),  # cents
                "currency": "USD"
            }
        })

    # Build request body for Square
    body = {
        "idempotency_key": str(uuid.uuid4()),  # REQUIRED
        "order": {
            "idempotency_key": str(uuid.uuid4()),  # REQUIRED
            "location_id": location_id,
            "line_items": line_items,
            "note": (
                f"Delivery Address: {delivery_address.get('address_line_1', '')}, "
                f"{delivery_address.get('locality', '')}, "
                f"{delivery_address.get('administrative_district_level_1', '')} "
                f"{delivery_address.get('postal_code', '')} | "
                f"Time Slot: {time_slot} | "
                f"Time Period: {time_period}"
            )
        },
        "checkout_options": {
            "redirect_url": redirect_url,
            "ask_for_shipping_address": True,
            "pre_populate_shipping_address": delivery_address
        }
    }

    print("SENDING TO SQUARE:", body)

    # Use the NEW endpoint (payment links)
    result = client.checkout.create_payment_link(body)

    # Handle Square errors
    if "errors" in result.body:
        print("SQUARE ERROR:", result.body["errors"])
        raise HTTPException(status_code=500, detail="Square checkout failed")

    # Return checkout URL
    return {"checkoutUrl": result.body["checkout"]["checkout_page_url"]}
