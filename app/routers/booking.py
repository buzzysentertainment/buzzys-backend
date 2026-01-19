from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from app.services.email_service import send_email
from app.services.firebase_setup import db
from square.client import Client
from datetime import datetime
import os
import uuid
import hmac
import hashlib
import base64

# Automation triggers
from app.triggers.on_contract_received import handle_contract_received
from app.triggers.on_deposit_received import handle_deposit_received
from app.triggers.on_payment_declined import handle_payment_declined
from app.triggers.on_balance_paid import handle_balance_paid
from app.triggers.on_refund_issued import handle_refund_issued
from app.triggers.on_event_canceled import handle_event_canceled

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
# Create Booking
# -------------------------
@router.post("/")
def create_booking(booking: Booking):
    total = float(booking.total)
    deposit = round(total * 0.35, 2)
    remaining = round(total - deposit, 2)

    booking_id = str(uuid.uuid4())

    booking_data = booking.dict()
    booking_data["deposit"] = deposit
    booking_data["remaining"] = remaining
    booking_data["created_at"] = datetime.utcnow().isoformat()
    booking_data["booking_id"] = booking_id
    booking_data["paymentStatus"] = "pending"
    booking_data["contractStatus"] = "pending"
    booking_data["status"] = "active"

    db.collection("bookings").document(booking_id).set(booking_data)

    # Customer confirmation email
    send_email(
        to=booking.email,
        subject="Your Buzzy’s Booking Confirmation",
        html=(
            f"<h1>Thanks {booking.name}!</h1>"
            f"<p>Your booking for {booking.date} is confirmed.</p>"
            f"<p>Total: ${total:.2f}<br>"
            f"Deposit (35%): ${deposit:.2f}<br>"
            f"Remaining: ${remaining:.2f}</p>"
        ),
    )

    # Admin alert
    send_email(
        to="admin@buzzys.org",
        subject="New Booking Received",
        html=(
            f"<p>New booking from {booking.name} on {booking.date}.</p>"
            f"<p>Total: ${total:.2f} | Deposit: ${deposit:.2f}</p>"
        ),
    )

    return {"status": "success", "message": "Booking received", "booking_id": booking_id}


# -------------------------
# Get All Bookings
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
        environment="production",
    )

    location_id = os.getenv("SQUARE_LOCATION_ID")
    redirect_url = "https://www.buzzys.org/booking-success"

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

    total_dollars = sum(
        float(item.get("price", 0)) * int(item.get("quantity", 1))
        for item in cart_items
    )
    deposit = round(total_dollars * 0.35, 2)
    remaining = round(total_dollars - deposit, 2)

    booking_id = str(uuid.uuid4())

    line_items = [
        {
            "name": "Total Due Today (35% Deposit)",
            "quantity": "1",
            "base_price_money": {
                "amount": int(deposit * 100),
                "currency": "USD",
            },
        },
        {
            "name": f"Remaining Balance Due on Event Date (${remaining:.2f})",
            "quantity": "1",
            "base_price_money": {
                "amount": 0,
                "currency": "USD",
            },
        },
    ]

    body = {
        "idempotency_key": str(uuid.uuid4()),
        "order": {
            "idempotency_key": str(uuid.uuid4()),
            "location_id": location_id,
            "line_items": line_items,
            "note": (
                f"BookingID: {booking_id} | "
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
            ),
        },
        "checkout_options": {
            "redirect_url": redirect_url,
            "ask_for_shipping_address": True,
            "pre_populate_shipping_address": delivery_address,
        },
    }

    result = client.checkout.create_payment_link(body)

    if "errors" in result.body:
        raise HTTPException(status_code=500, detail="Square checkout failed")

    payment_link = result.body.get("payment_link", {})
    checkout_url = payment_link.get("url")

    if not checkout_url:
        raise HTTPException(status_code=500, detail="Square did not return a checkout URL")

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
        "paymentStatus": "pending",
        "contractStatus": "pending",
        "status": "active",
    }

    db.collection("bookings").document(booking_id).set(booking_record)

    send_email(
        to="admin@buzzys.org",
        subject="New Booking Checkout Started",
        html=(
            f"<p>New booking started by {customer_name} for {booking_date}.</p>"
            f"<p>Total: ${total_dollars:.2f}<br>"
            f"Deposit (35%): ${deposit:.2f}<br>"
            f"Remaining: ${remaining:.2f}</p>"
            f"<p>Checkout Link: <a href='{checkout_url}'>{checkout_url}</a></p>"
        ),
    )

    response = {"checkoutUrl": checkout_url}
    return response


# -------------------------
# Update Booking
# -------------------------
@router.put("/{booking_id}")
def update_booking(booking_id: str, data: dict):
    doc_ref = db.collection("bookings").document(booking_id)
    doc = doc_ref.get()

    if not doc.exists:
        raise HTTPException(status_code=404, detail="Booking not found")

    old_data = doc.to_dict()
    new_data = {**old_data, **data}

    doc_ref.update(new_data)

    # Contract Received automation
    if (
        old_data.get("contractStatus") != "received"
        and new_data.get("contractStatus") == "received"
    ):
        handle_contract_received(new_data)

    # Event Canceled automation
    if old_data.get("status") != "canceled" and new_data.get("status") == "canceled":
        handle_event_canceled(new_data)

    return {"status": "success", "updated": new_data}


# -------------------------
# Square Webhook
# -------------------------
@router.post("/webhooks/square")
async def square_webhook(request: Request):
    square_signature = request.headers.get("x-square-hmacsha256-signature")
    webhook_signature_key = os.getenv("SQUARE_WEBHOOK_SIGNATURE_KEY")

    raw_body = await request.body()
    body_text = raw_body.decode("utf-8")

    if webhook_signature_key:
        computed_hash = hmac.new(
            webhook_signature_key.encode("utf-8"),
            msg=body_text.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        computed_signature = base64.b64encode(computed_hash).decode("utf-8")

        if computed_signature != square_signature:
            raise HTTPException(status_code=400, detail="Invalid signature")

    payload = await request.json()
    event_type = payload.get("type", "")
    data_object = payload.get("data", {}).get("object", {})

    print("SQUARE WEBHOOK RECEIVED:", event_type)

    # Handle payment updates
    if event_type == "payment.updated":
        payment = data_object.get("payment", {})
        status = payment.get("status")
        amount_money = payment.get("amount_money", {}) or {}
        total_amount = amount_money.get("amount")
        total_amount_dollars = (total_amount or 0) / 100.0

        client = Client(
            access_token=os.getenv("SQUARE_ACCESS_TOKEN"),
            environment="production",
        )

        order_id = payment.get("order_id")
        booking_id = None

        if order_id:
            try:
                order_result = client.orders.retrieve_order(order_id=order_id)
                if "errors" not in order_result.body:
                    order = order_result.body.get("order", {})
                    note = order.get("note", "") or ""
                    if "BookingID:" in note:
                        part = note.split("BookingID:")[1]
                        booking_id = part.split("|")[0].strip()
            except Exception as e:
                print("FAILED TO RETRIEVE ORDER:", e)

        if not booking_id:
            print("No booking_id found for payment webhook")
            return {"status": "ignored"}

        doc_ref = db.collection("bookings").document(booking_id)
        doc = doc_ref.get()
        if not doc.exists:
            print("Booking not found for webhook booking_id:", booking_id)
            return {"status": "ignored"}

        booking = doc.to_dict()

        # Deposit Received
        if status == "COMPLETED" and booking.get("paymentStatus") != "deposit_paid":
            doc_ref.update({"paymentStatus": "deposit_paid"})
            booking["paymentStatus"] = "deposit_paid"
            handle_deposit_received(booking)

        # Payment Declined
        elif status in ("FAILED", "CANCELED"):
            doc_ref.update({"paymentStatus": "failed"})
            booking["paymentStatus"] = "failed"
            handle_payment_declined(booking)

    # Handle invoice updates
    if event_type == "invoice.updated":
        invoice = data_object.get("invoice", {})
        status = invoice.get("status")
        invoice_id = invoice.get("id")

        query = (
            db.collection("bookings")
            .where("invoice_id", "==", invoice_id)
            .limit(1)
            .stream()
        )

        booking_doc = None
        for d in query:
            booking_doc = d
            break

        if not booking_doc:
            print("No booking found for invoice_id:", invoice_id)
            return {"status": "ignored"}

        booking = booking_doc.to_dict()
        doc_ref = db.collection("bookings").document(booking["booking_id"])

        # Balance Paid
        if status == "PAID":
            doc_ref.update({"paymentStatus": "balance_paid"})
            booking["paymentStatus"] = "balance_paid"
            handle_balance_paid(booking)

        # Refund Issued
        if status in ("CANCELED", "REFUNDED"):
            remaining = float(booking.get("remaining", 0))
            handle_refund_issued(booking, amount=remaining)

    return {"status": "ok"}
