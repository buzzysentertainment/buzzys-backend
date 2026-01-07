from fastapi import APIRouter
from pydantic import BaseModel
from app.services.email_service import send_email
from app.services.firebase_setup import db
from square.client import SquareClient
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
# Create Square Checkout Link (NEW)
# -------------------------
client = SquareClient(
    access_token=os.getenv("SQUARE_ACCESS_TOKEN"),
    environment="production"
)

@router.post("/create-checkout")
def create_checkout(data: dict):
    amount = int(data["amount"] * 100)  # convert dollars → cents
    redirect_url = data["redirectUrl"]

    body = {
        "idempotency_key": str(uuid.uuid4()),
        "order": {
            "location_id": os.getenv("SQUARE_LOCATION_ID"),
            "line_items": [
                {
                    "name": "Booking Deposit",
                    "quantity": "1",
                    "base_price_money": {
                        "amount": amount,
                        "currency": "USD"
                    }
                }
            ]
        },
        "redirect_url": redirect_url
    }

    result = client.checkout.create_checkout(
        location_id=os.getenv("SQUARE_LOCATION_ID"),
        body=body
    )

    return {"checkoutUrl": result.body["checkout"]["checkout_page_url"]}
