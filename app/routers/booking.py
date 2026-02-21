from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from app.services.email_service import send_email_template
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
from app.triggers.on_event_reminder import handle_event_reminder

router = APIRouter(prefix="/book", tags=["booking"])

# -------------------------
# Event Reminder Helper
# -------------------------
def send_event_day_reminder(booking):
    try:
        handle_event_reminder(booking)
        return {"status": "success", "message": "Event reminder sent"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


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

    send_email_template(
        to=booking.email,
        template_id=os.getenv("RESEND_BOOKING_CONFIRMATION_TEMPLATE"),
        data={
            "name": booking.name,
            "date": booking.date,
            "total": total,
            "deposit": deposit,
            "remaining": remaining
        }
    )

    send_email_template(
        to="admin@buzzys.org",
        template_id=os.getenv("RESEND_ADMIN_NEW_BOOKING_TEMPLATE"),
        data={
            "name": booking.name,
            "date": booking.date,
            "total": total,
            "deposit": deposit,
            "remaining": remaining
        }
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
# Send Reminder for a Single Booking
# -------------------------
@router.post("/{booking_id}/send-reminder")
def send_reminder(booking_id: str):
    doc_ref = db.collection("bookings").document(booking_id)
    doc = doc_ref.get()

    if not doc.exists:
        raise HTTPException(status_code=404, detail="Booking not found")

    booking = doc.to_dict()
    return send_event_day_reminder(booking)


# -------------------------
# Send Reminders for All Events Happening Today
# -------------------------
@router.post("/send-today-reminders")
def send_today_reminders():
    today = datetime.utcnow().strftime("%Y-%m-%d")

    docs = (
        db.collection("bookings")
        .where("date", "==", today)
        .where("status", "==", "active")
        .stream()
    )

    sent = []
    for doc in docs:
        booking = doc.to_dict()
        send_event_day_reminder(booking)
        sent.append(booking.get("booking_id"))

    return {"status": "success", "reminders_sent": sent}


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

    # Aligning frontend fields with backend logic
    customer_name = data.get("customerName") or data.get("name", "Valued Customer")
    customer_email = data.get("customerEmail") or data.get("email", "")
    customer_phone = data.get("customerPhone") or data.get("phone", "")
    booking_date = data.get("eventDate") or data.get("date", "")
    
    referral_type = data.get("referralType", "None") 
    is_tax_exempt = data.get("isTaxExempt", False)
    damage_waiver_opt = data.get("damageWaiver", False)
    signature = data.get("signature", "Electronic Signature")
    
    distance_charge = float(data.get("distanceCharge", 0))
    staff_fee = float(data.get("staffFee", 0))
    
    raw_subtotal = sum(float(item.get("price", 0)) for item in cart_items)
    
    # Referral Discounts
    discount_amount = 0
    if referral_type == "Friend":
        discount_amount = raw_subtotal * 0.05
    elif referral_type == "Repeat":
        discount_amount = raw_subtotal * 0.10
        
    subtotal_after_discount = raw_subtotal - discount_amount
    waiver_fee = round(subtotal_after_discount * 0.08, 2) if damage_waiver_opt else 0
    
    taxable_amount = subtotal_after_discount + waiver_fee + distance_charge
    tax_total = round(taxable_amount * 0.07, 2) if not is_tax_exempt else 0
    
    total_dollars = taxable_amount + tax_total + staff_fee
    
    deposit = round(total_dollars * 0.35, 2)
    remaining = round(total_dollars - deposit, 2)
    
    booking_id = str(uuid.uuid4())
    
    # ADDRESS SAFETY FIX: Check if it's a string (new cart) or dict (old cart)
    address_input = data.get("address", "Address Not Provided")
    if isinstance(address_input, dict):
        delivery_address_display = f"{address_input.get('address_line_1', '')}, {address_input.get('locality', '')}"
        pre_populate_address = address_input
    else:
        delivery_address_display = address_input
        pre_populate_address = {"address_line_1": address_input}

    time_slot = data.get("timeSlot", "")
    time_period = data.get("timePeriod", "")

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
                f"Date: {booking_date} | "
                f"Address: {delivery_address_display} | "
                f"Total: ${total_dollars:.2f} | "
                f"Signed: {signature}"
            ),
        },
        "checkout_options": {
            "redirect_url": redirect_url,
            "ask_for_shipping_address": False, # Set to False since we have the address
            "enable_tipping": True,
        },
    }

    result = client.checkout.create_payment_link(body)

    if "errors" in result.body:
        print("SQUARE ERRORS:", result.body['errors'])
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
        "signature": signature,
        "damageWaiver": damage_waiver_opt,
        "pricing_breakdown": {
            "subtotal": raw_subtotal,
            "discount": discount_amount,
            "waiver": waiver_fee,
            "tax": tax_total,
            "distance": distance_charge,
            "staff": staff_fee,
            "total": total_dollars
        },
        "deposit": deposit,
        "remaining": remaining,
        "address": delivery_address_display,
        "timeSlot": time_slot,
        "timePeriod": time_period,
        "checkout_url": checkout_url,
        "created_at": datetime.utcnow().isoformat(),
        "paymentStatus": "pending",
        "contractStatus": "pending",
        "status": "active",
    }

    db.collection("bookings").document(booking_id).set(booking_record)

    send_email_template(
        to=["buzzysentertainment@gmail.com", "kandy.stamey@gmail.com"],
        template_id=os.getenv("RESEND_ADMIN_CHECKOUT_STARTED_TEMPLATE"),
        data={
            "name": customer_name,
            "date": booking_date,
            "total": total_dollars,
            "deposit": deposit,
            "remaining": remaining,
            "checkout_url": checkout_url
        }
    )

    return {"checkoutUrl": checkout_url}


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

    if (
        old_data.get("contractStatus") != "received"
        and new_data.get("contractStatus") == "received"
    ):
        handle_contract_received(new_data)

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

    if event_type == "payment.updated":
        payment = data_object.get("payment", {})
        status = payment.get("status")
        
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
            return {"status": "ignored"}

        doc_ref = db.collection("bookings").document(booking_id)
        doc = doc_ref.get()
        if not doc.exists:
            return {"status": "ignored"}

        booking = doc.to_dict()

        if status == "COMPLETED" and booking.get("paymentStatus") != "deposit_paid":
            doc_ref.update({"paymentStatus": "deposit_paid"})
            booking["paymentStatus"] = "deposit_paid"
            handle_deposit_received(booking)

        elif status in ("FAILED", "CANCELED"):
            doc_ref.update({"paymentStatus": "failed"})
            booking["paymentStatus"] = "failed"
            handle_payment_declined(booking)

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
            return {"status": "ignored"}

        booking = booking_doc.to_dict()
        doc_ref = db.collection("bookings").document(booking["booking_id"])

        if status == "PAID":
            doc_ref.update({"paymentStatus": "balance_paid"})
            booking["paymentStatus"] = "balance_paid"
            handle_balance_paid(booking)

        if status in ("CANCELED", "REFUNDED"):
            remaining = float(booking.get("remaining", 0))
            handle_refund_issued(booking, amount=remaining)

    return {"status": "ok"}