from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.email_service import send_email
from app.services.firebase_setup import db
from square.client import Client
from datetime import datetime
import os
import uuid

router = APIRouter(prefix="/book", tags=["booking"])

# -------------------------
# Booking Model (existing)
# -------------------------
class Booking(BaseModel):
    name: str
    email: str
    phone: str
    date: str
    items: list
    total: float


# -------------------------
# Create Booking (existing, kept for compatibility)
# -------------------------
@router.post("/")
def create_booking(booking: Booking):
    # Calculate deposit + remaining
    total = float(booking.total)
    deposit = round(total * 0.35, 2)
    remaining = round(total - deposit, 2)

    # Save booking to Firestore
    booking_data = booking.dict()
    booking_data["deposit"] = deposit
    booking_data["remaining"] = remaining
    booking_data["created_at"] = datetime.utcnow().isoformat()
    booking_data["booking_id"] = str(uuid.uuid4())

    db.collection("bookings").add(booking_data)

    # Send confirmation email
    send_email(
        to=booking.email,
        subject="Your Buzzy’s Booking Confirmation",
        html=(
            f"<h1>Thanks {booking.name}!</h1>"
            f"<p>Your booking for {booking.date} is confirmed.</p>"
            f"<p>Total: ${total:.2f}<br>"
            f"Deposit (35%): ${deposit:.2f}<br>"
            f"Remaining: ${remaining:.2f}</p>"
        )
    )

    # Send admin alert
    send_email(
        to="admin@buzzys.org",
        subject="New Booking Received",
        html=(
            f"<p>New booking from {booking.name} on {booking.date}.</p>"
            f"<p>Total: ${total:.2f} | Deposit: ${deposit:.2f}</p>"
        )
    )

    return {"status": "success", "message": "Booking received"}


# -------------------------
# Get All Bookings (admin dashboard)
# -------------------------
@router.get("/all")
def get_all_bookings():
    docs = db.collection("bookings").stream()
    return [doc.to_dict() for doc in docs]


# -------------------------
# Create Square Checkout Link
# -------------------------
@router.post("/create-checkout")
def create_checkout(data: dict):
    client = Client(
        access_token=os.getenv("SQUARE_ACCESS_TOKEN"),
        environment="production"
    )

    location_id = os.getenv("SQUARE_LOCATION_ID")
    redirect_url = "https://www.buzzys.org/booking-success"

    # -------------------------
    # Extract core data from frontend
    # -------------------------
    cart_items = data.get("cart", [])
    if not cart_items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    customer_name = data.get("name", "")
    customer_email = data.get("email", "")
    customer_phone = data.get("phone", "")
    booking_date = data.get("date", "")

    delivery_address = data.get("address", {})
    time_slot = data.get("timeSlot", "")
    time_period = data.get("timePeriod", "")

    # -------------------------
    # Calculate totals + deposit
    # -------------------------
    total_dollars = sum(
        float(item.get("price", 0)) * int(item.get("quantity", 1))
        for item in cart_items
    )
    deposit = round(total_dollars * 0.35, 2)
    remaining = round(total_dollars - deposit, 2)

    # -------------------------
    # Build line items (Square requires cents)
    # -------------------------
    line_items = []
    for item in cart_items:
        line_items.append({
            "name": item.get("name", "Item"),
            "quantity": str(item.get("quantity", 1)),
            "base_price_money": {
                "amount": int(float(item.get("price", 0)) * 100),  # dollars → cents
                "currency": "USD"
            }
        })

    # -------------------------
    # Build Square order body
    # -------------------------
    body = {
        "idempotency_key": str(uuid.uuid4()),
        "order": {
            "idempotency_key": str(uuid.uuid4()),
            "location_id": location_id,
            "line_items": line_items,
            "note": (
                f"Customer: {customer_name} | "
                f"Email: {customer_email} | "
                f"Phone: {customer_phone} | "
                f"Date: {booking_date} | "
                f"Delivery Address: {delivery_address.get('address_line_1', '')}, "
                f"{delivery_address.get('locality', '')}, "
                f"{delivery_address.get('administrative_district_level_1', '')} "
                f"{delivery_address.get('postal_code', '')} | "
                f"Time Slot: {time_slot} | "
                f"Time Period: {time_period} | "
                f"Total: ${total_dollars:.2f} | "
                f"Deposit (35%): ${deposit:.2f} | "
                f"Remaining: ${remaining:.2f}"
            )
        },
        "checkout_options": {
            "redirect_url": redirect_url,
            "ask_for_shipping_address": True,
            "pre_populate_shipping_address": delivery_address
        }
    }

    print("SENDING TO SQUARE:", body)

    # -------------------------
    # Create payment link with Square
    # -------------------------
    result = client.checkout.create_payment_link(body)

    if "errors" in result.body:
        print("SQUARE ERROR:", result.body["errors"])
        raise HTTPException(status_code=500, detail="Square checkout failed")

    payment_link = result.body.get("payment_link", {})
    checkout_url = payment_link.get("url")

    if not checkout_url:
        print("SQUARE RESPONSE MISSING URL:", result.body)
        raise HTTPException(status_code=500, detail="Square did not return a checkout URL")

    # -------------------------
    # Save full booking to Firestore for admin
    # -------------------------
    booking_id = str(uuid.uuid4())
    booking_record = {
        "booking_id": booking_id,
        "name": customer_name,
        "email": customer_email,
        "phone": customer_phone,
        "date": booking_date,
        "items": cart_items,
        "total": total_dollars,
        "deposit": deposit,
        "remaining": remaining,
        "address": delivery_address,
        "timeSlot": time_slot,
        "timePeriod": time_period,
        "checkout_url": checkout_url,
        "created_at": datetime.utcnow().isoformat(),
    }

    db.collection("bookings").add(booking_record)

    # -------------------------
    # Send admin email (optional but powerful)
    # -------------------------
    try:
        send_email(
            to="admin@buzzys.org",
            subject="New Booking Checkout Started",
            html=(
                f"<p>New booking started by {customer_name} for {booking_date}.</p>"
                f"<p>Total: ${total_dollars:.2f}<br>"
                f"Deposit (35%): ${deposit:.2f}<br>"
                f"Remaining: ${remaining:.2f}</p>"
                f"<p>Time Slot: {time_slot}<br>"
                f"Time Period: {time_period}</p>"
                f"<p>Checkout Link: <a href='{checkout_url}'>{checkout_url}</a></p>"
            )
        )
    except Exception as e:
        print("Failed to send admin email:", e)

    # -------------------------
    # Return checkout URL to frontend
    # -------------------------
    return {"checkoutUrl": checkout_url}
