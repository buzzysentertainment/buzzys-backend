from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from app.services.email_service import send_email_template
from app.services.firebase_setup import db
from square.client import Client
from datetime import datetime, timedelta
import os
import uuid
import hmac
import hashlib
import base64

# --- ALL AUTOMATION TRIGGERS ---
from app.triggers.on_contract_received import handle_contract_received
from app.triggers.on_deposit_received import handle_deposit_received
from app.triggers.on_payment_declined import handle_payment_declined
from app.triggers.on_balance_paid import handle_balance_paid
from app.triggers.on_refund_issued import handle_refund_issued
from app.triggers.on_event_canceled import handle_event_canceled
from app.triggers.on_event_reminder import handle_event_reminder
from app.triggers.on_reengagement import send_anniversary_reminders

router = APIRouter(prefix="/book", tags=["booking"])

# ---------------------------------------------------------
# MODELS & SCHEMAS
# ---------------------------------------------------------

class Booking(BaseModel):
    name: str
    email: str
    phone: str
    date: str
    items: list
    total: float

# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def send_event_day_reminder(booking):
    """
    Manual trigger helper for sending a reminder for a specific booking.
    """
    try:
        handle_event_reminder(booking)
        return {"status": "success", "message": "Event reminder sent"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def calculate_totals(raw_subtotal, referral_type, damage_waiver_opt, distance_charge, staff_fee, is_tax_exempt):
    """
    Encapsulated logic for price calculations to ensure consistency.
    """
    # 1. Apply Discounts
    discount_amount = 0
    if referral_type == "Friend":
        discount_amount = raw_subtotal * 0.05
    elif referral_type == "Repeat":
        discount_amount = raw_subtotal * 0.10
        
    subtotal_after_discount = raw_subtotal - discount_amount
    
    # 2. Waiver Fee
    waiver_fee = round(subtotal_after_discount * 0.08, 2) if damage_waiver_opt else 0
    
    # 3. Tax
    taxable_amount = subtotal_after_discount + waiver_fee + distance_charge
    tax_total = round(taxable_amount * 0.07, 2) if not is_tax_exempt else 0
    
    # 4. Final Totals
    total_dollars = taxable_amount + tax_total + staff_fee
    deposit = round(total_dollars * 0.35, 2)
    remaining = round(total_dollars - deposit, 2)
    
    return {
        "subtotal": raw_subtotal,
        "discount": discount_amount,
        "waiver": waiver_fee,
        "tax": tax_total,
        "total": total_dollars,
        "deposit": deposit,
        "remaining": remaining
    }

# ---------------------------------------------------------
# CORE ROUTES
# ---------------------------------------------------------

@router.post("/check-availability")
async def check_availability(data: dict):
    """
    Checks if specific items are already booked for a given date.
    """
    target_date = data.get("date")
    requested_item_titles = data.get("items", []) 
    
    if not target_date:
        raise HTTPException(status_code=400, detail="Date is required")

    bookings_ref = db.collection("bookings")
    query = bookings_ref.where("date", "==", target_date)\
                        .where("status", "==", "active")\
                        .stream()
    
    for doc in query:
        existing_booking = doc.to_dict()
        # Skip failed payments so they don't block availability
        if existing_booking.get("paymentStatus") == "failed":
            continue

        existing_items = existing_booking.get("items", [])
        for item in existing_items:
            existing_title = item.get("title") or item.get("name")
            if existing_title in requested_item_titles:
                return {
                    "available": False, 
                    "conflict": existing_title
                }
                
    return {"available": True}

@router.post("/")
def create_booking(booking: Booking):
    """
    Initial entry point for a booking. This saves the record before payment.
    """
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

    # Admin Notification
    send_email_template(
        to="buzzysentertainment@gmail.com",
        template_id=os.getenv("RESEND_ADMIN_NEW_BOOKING_TEMPLATE"),
        data={
            "name": booking.name,
            "email": booking.email,
            "phone": booking.phone,
            "date": booking.date,
            "total": f"${total:.2f}",
            "deposit": f"${deposit:.2f}",
            "booking_id": booking_id,
            "items": ", ".join([str(i) for i in booking.items]),
            "remaining": f"${remaining:.2f}"
        }
    )

    return {"status": "success", "message": "Booking received", "booking_id": booking_id}

@router.get("/all")
def get_all_bookings():
    """
    Dashboard route to fetch and normalize all booking records.
    """
    docs = db.collection("bookings").stream()
    cleaned_bookings = []

    for doc in docs:
        b = doc.to_dict()
        
        # Normalize keys for frontend consistency
        if "customer_name" in b and not b.get("name"):
            b["name"] = b["customer_name"]
        if "eventDate" in b and not b.get("date"):
            b["date"] = b["eventDate"]

        if "pricing_breakdown" in b and isinstance(b["pricing_breakdown"], dict):
            if not b.get("total"):
                b["total"] = b["pricing_breakdown"].get("total", 0)

        # Normalize item strings for display
        if "items" in b and isinstance(b["items"], list):
            item_names = []
            for item in b["items"]:
                if isinstance(item, dict):
                    name = item.get("title") or item.get("name") or "Unknown Item"
                else:
                    name = str(item)
                item_names.append(name)
            b["display_items"] = ", ".join(item_names)
        else:
            b["display_items"] = "No items listed"

        cleaned_bookings.append(b)

    cleaned_bookings.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return cleaned_bookings

@router.post("/create-checkout")
def create_checkout(data: dict):
    """
    Generates a Square Payment Link and prepares the finalized booking record.
    """
    client = Client(
        access_token=os.getenv("SQUARE_ACCESS_TOKEN"),
        environment="production",
    )

    location_id = os.getenv("SQUARE_LOCATION_ID")
    redirect_url = "https://www.buzzys.org/booking-success"

    cart_items = data.get("cart", [])
    if not cart_items:
        raise HTTPException(status_code=400, detail="Cart is empty")

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
    
    # Process Item Titles and Subtotal
    item_summary_list = []
    raw_subtotal = 0
    for item in cart_items:
        price = float(item.get("price", 0))
        raw_subtotal += price
        title = item.get("title") or item.get("name", "Item")
        if item.get("overnight") is True:
            title += " (Overnight)"
        item_summary_list.append(title)
        
    # Run Price Calculation Logic
    pricing = calculate_totals(
        raw_subtotal, referral_type, damage_waiver_opt, 
        distance_charge, staff_fee, is_tax_exempt
    )
    
    booking_id = str(uuid.uuid4())
    address_input = data.get("address", "Address Not Provided")
    delivery_address_display = (
        f"{address_input.get('address_line_1', '')}, {address_input.get('locality', '')}" 
        if isinstance(address_input, dict) else address_input
    )

    time_slot = data.get("timeSlot", "")
    time_period = data.get("timePeriod", "")

    line_items = [
        {
            "name": "Total Due Today (35% Deposit)",
            "quantity": "1",
            "base_price_money": {"amount": int(pricing["deposit"] * 100), "currency": "USD"},
        },
        {
            "name": f"Remaining Balance Due on Event Date (${pricing['remaining']:.2f})",
            "quantity": "1",
            "base_price_money": {"amount": 0, "currency": "USD"},
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
                f"Items: {', '.join(item_summary_list)} | "
                f"Date: {booking_date} | "
                f"Address: {delivery_address_display} | "
                f"Total: ${pricing['total']:.2f} | "
                f"Signed: {signature}"
            ),
        },
        "checkout_options": {
            "redirect_url": redirect_url,
            "ask_for_shipping_address": False,
            "enable_tipping": True,
            "merchant_support_email": "buzzysentertainment@gmail.com"           
        },
    }

    result = client.checkout.create_payment_link(body)

    if "errors" in result.body:
        print("SQUARE ERRORS:", result.body['errors'])
        raise HTTPException(status_code=500, detail="Square checkout failed")

    payment_link = result.body.get("payment_link", {})
    checkout_url = payment_link.get("url")

    booking_record = {
        "booking_id": booking_id,
        "name": customer_name,
        "email": customer_email,
        "phone": customer_phone,
        "date": booking_date,
        "items": cart_items,
        "signature": signature,
        "damageWaiver": damage_waiver_opt,
        "referral_type": referral_type,
        "pricing_breakdown": pricing,
        "deposit": pricing["deposit"],
        "remaining": pricing["remaining"],
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

    # Admin Email Alert
    send_email_template(
        to=["buzzysentertainment@gmail.com", "kandy.stamey@gmail.com"],
        template_id=os.getenv("RESEND_ADMIN_CHECKOUT_STARTED_TEMPLATE"),
        data={
            "name": customer_name,
            "date": booking_date,
            "total": pricing["total"],
            "deposit": pricing["deposit"],
            "remaining": pricing["remaining"],
            "checkout_url": checkout_url
        }
    )

    return {"checkoutUrl": checkout_url}

# ---------------------------------------------------------
# LIFECYCLE AUTOMATION
# ---------------------------------------------------------

@router.post("/automate-lifecycle")
def automate_lifecycle():
    """
    Automated processing for:
    1. Autopay (2 days before event)
    2. Reminders (Day of event)
    3. Reengagement (Day after event)
    """
    today_dt = datetime.utcnow()
    today_str = today_dt.strftime("%Y-%m-%d")
    target_date_autopay = (today_dt + timedelta(days=2)).strftime("%Y-%m-%d")
    yesterday_str = (today_dt - timedelta(days=1)).strftime("%Y-%m-%d")
    
    client = Client(access_token=os.getenv("SQUARE_ACCESS_TOKEN"), environment="production")
    
    # --- 1. AUTOPAY BLOCK ---
    autopay_docs = db.collection("bookings")\
            .where("date", "==", target_date_autopay)\
            .where("paymentStatus", "==", "deposit_paid")\
            .stream()
    
    autopay_results = []
    for doc in autopay_docs:
        booking = doc.to_dict()
        cust_id = booking.get("square_customer_id")
        src_id = booking.get("square_source_id") 
        remaining = booking.get("remaining", 0)
        
        if cust_id and src_id and remaining > 0:
            try:
                payment_body = {
                    "source_id": src_id,
                    "idempotency_key": str(uuid.uuid4()),
                    "amount_money": {
                        "amount": int(float(remaining) * 100), 
                        "currency": "USD"
                    },
                    "customer_id": cust_id,
                    "note": f"Autopay Final Balance | Booking: {booking.get('booking_id')}"
                }
                result = client.payments.create_payment(payment_body)
                
                if "errors" not in result.body:
                    doc.reference.update({"paymentStatus": "balance_paid"})
                    booking["paymentStatus"] = "balance_paid"
                    handle_balance_paid(booking)
                    autopay_results.append(f"SUCCESS: {booking.get('booking_id')}")
                else:
                    handle_payment_declined(booking)
                    autopay_results.append(f"FAILED (Square Error): {booking.get('booking_id')}")
            except Exception as e:
                print(f"Autopay Exception: {e}")
                handle_payment_declined(booking)

    # --- 2. TODAY REMINDERS BLOCK ---
    today_docs = db.collection("bookings").where("date", "==", today_str).where("status", "==", "active").stream()
    reminders_sent = []
    for doc in today_docs:
        booking = doc.to_dict()
        handle_event_reminder(booking)
        reminders_sent.append(booking.get("booking_id"))
                
    # --- 3. REENGAGEMENT BLOCK ---
    yesterday_docs = db.collection("bookings").where("date", "==", yesterday_str).stream()
    reengagement_sent = []
    for doc in yesterday_docs:
        booking = doc.to_dict()
        # Only reengage if the event actually happened
        if booking.get("paymentStatus") in ["deposit_paid", "balance_paid"]:
            send_anniversary_reminders(booking) 
            reengagement_sent.append(booking.get("booking_id"))

    return {
        "status": "success", 
        "autopay_count": len(autopay_results),
        "autopay_details": autopay_results,
        "reminders": reminders_sent, 
        "reengagement": reengagement_sent
    }

# ---------------------------------------------------------
# UPDATE & INDIVIDUAL ACTIONS
# ---------------------------------------------------------

@router.put("/{booking_id}")
def update_booking(booking_id: str, data: dict):
    """
    Update a booking record and trigger status-change workflows.
    """
    doc_ref = db.collection("bookings").document(booking_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    old_data = doc.to_dict()
    new_data = {**old_data, **data}
    doc_ref.update(new_data)
    
    # Trigger: Contract Received
    if old_data.get("contractStatus") != "received" and new_data.get("contractStatus") == "received":
        handle_contract_received(new_data)
    
    # Trigger: Event Canceled
    if old_data.get("status") != "canceled" and new_data.get("status") == "canceled":
        handle_event_canceled(new_data)
        
    return {"status": "success", "updated": new_data}

@router.post("/{booking_id}/send-reminder")
def send_individual_reminder(booking_id: str):
    """
    Manually trigger an event reminder email for a specific booking.
    """
    doc_ref = db.collection("bookings").document(booking_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Booking not found")
    return send_event_day_reminder(doc.to_dict())

# ---------------------------------------------------------
# WEBHOOKS
# ---------------------------------------------------------

@router.post("/webhooks/square")
async def square_webhook(request: Request):
    """
    Square Webhook Listener for Payments and Invoices.
    """
    # 1. Signature Verification
    square_signature = request.headers.get("x-square-hmacsha256-signature")
    webhook_signature_key = os.getenv("SQUARE_WEBHOOK_SIGNATURE_KEY")
    raw_body = await request.body()
    body_text = raw_body.decode("utf-8")
    
    if webhook_signature_key and square_signature:
        computed_hash = hmac.new(webhook_signature_key.encode("utf-8"), msg=body_text.encode("utf-8"), digestmod=hashlib.sha256).digest()
        computed_signature = base64.b64encode(computed_hash).decode("utf-8")
        if computed_signature != square_signature:
            raise HTTPException(status_code=400, detail="Invalid signature")

    payload = await request.json()
    event_type = payload.get("type", "")
    data_object = payload.get("data", {}).get("object", {})
    
    # 2. Handle Payment Updates (Initial Deposit / Card Capture)
    if event_type == "payment.updated":
        payment = data_object.get("payment", {})
        status = payment.get("status")
        client = Client(access_token=os.getenv("SQUARE_ACCESS_TOKEN"), environment="production")
        
        customer_id = payment.get("customer_id")
        source_id = payment.get("source_id")
        order_id = payment.get("order_id")
        booking_id = None
        
        # Retrieve Order to find the BookingID from the Note field
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
        
        if booking_id:
            doc_ref = db.collection("bookings").document(booking_id)
            doc = doc_ref.get()
            if doc.exists:
                booking = doc.to_dict()
                if status == "COMPLETED" and booking.get("paymentStatus") != "deposit_paid":
                    # Crucial: Store SourceID for future Autopay
                    doc_ref.update({
                        "paymentStatus": "deposit_paid",
                        "square_customer_id": customer_id,
                        "square_source_id": source_id
                    })                    
                    booking["paymentStatus"] = "deposit_paid"
                    handle_deposit_received(booking)
                elif status in ("FAILED", "CANCELED"):
                    doc_ref.update({"paymentStatus": "failed"})
                    booking["paymentStatus"] = "failed"
                    handle_payment_declined(booking)

    # 3. Handle Invoice Updates (Manual Balance Payments)
    if event_type == "invoice.updated":
        invoice = data_object.get("invoice", {})
        status = invoice.get("status")
        invoice_id = invoice.get("id")
        
        query = db.collection("bookings").where("invoice_id", "==", invoice_id).limit(1).stream()
        booking_doc = None
        for d in query:
            booking_doc = d
            break
            
        if booking_doc:
            booking = booking_doc.to_dict()
            doc_ref = db.collection("bookings").document(booking["booking_id"])
            if status == "PAID":
                doc_ref.update({"paymentStatus": "balance_paid"})
                booking["paymentStatus"] = "balance_paid"
                handle_balance_paid(booking)
            elif status in ("CANCELED", "REFUNDED"):
                remaining = float(booking.get("remaining", 0))
                handle_refund_issued(booking, amount=remaining)
    
    return {"status": "ok"}