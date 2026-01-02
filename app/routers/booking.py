from fastapi import APIRouter
from pydantic import BaseModel
from app.services.email_service import send_email
from app.services.firebase_setup import db

router = APIRouter(prefix="/book", tags=["booking"])

class Booking(BaseModel):
    name: str
    email: str
    phone: str
    date: str
    items: list
    total: float

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

@router.get("/all")
def get_all_bookings():
    docs = db.collection("bookings").stream()
    return [doc.to_dict() for doc in docs]
