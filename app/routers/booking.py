from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from app.root_schema import normalize_payload, validate_payload, build_square_metadata, build_resend_params
from app.services.google_calendar import create_booking_event, update_booking_event
from app.services.email_service import send_email_template, send_email_from_file
from app.services.firebase_setup import db
from svix.webhooks import Webhook, WebhookVerificationError
from square.client import Client
from square.utilities.webhooks_helper import is_valid_webhook_event_signature
from datetime import datetime, timedelta
import os
import uuid

# --- ALL AUTOMATION TRIGGERS ---
from app.triggers.on_contract_received import handle_contract_received
from app.triggers.on_deposit_received import handle_deposit_received
from app.triggers.on_payment_declined import handle_payment_declined
from app.triggers.on_balance_paid import handle_balance_paid
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
    mileageFee: float = 0
    distance: float = 0
    referralType: str = "None"
    damageWaiver: bool = False

# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def calculate_totals(raw_subtotal, referral_type, damage_waiver_opt, distance_charge, staff_fee, is_tax_exempt, promo_discount=0, promo_percent=0):
    """
    Standardized pricing engine to ensure math is identical between 
    the frontend, Square link, and the Firebase record.
    """
    # 1. Apply Discounts
    referral_discount_amount = 0
    if referral_type == "Friend":
        referral_discount_amount = raw_subtotal * 0.05
    elif referral_type == "Repeat":
        referral_discount_amount = raw_subtotal * 0.10
        
    percent_discount_amount = raw_subtotal * (promo_percent / 100)   
    total_discounts = referral_discount_amount + promo_discount + percent_discount_amount

    subtotal_after_discount = max(0, raw_subtotal - total_discounts)
    
    # 2. Waiver Fee (8% of equipment subtotal)
    waiver_fee = round(subtotal_after_discount * 0.08, 2) if damage_waiver_opt else 0
    
    # 3. Tax (7% on equipment + waiver + distance)
    taxable_amount = subtotal_after_discount + waiver_fee + distance_charge
    tax_total = round(taxable_amount * 0.07, 2) if not is_tax_exempt else 0
    
    # 4. Final Split
    total_dollars = round(taxable_amount + tax_total + staff_fee, 2)
    deposit = round(total_dollars * 0.35, 2)
    remaining = round(total_dollars - deposit, 2)
    
    return {
        "subtotal": raw_subtotal,
        "referral_discount": referral_discount_amount,
        "promo_discount": promo_discount + percent_discount_amount,
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
    target_date = data.get("date") or data.get("eventDate")
    requested_item_titles = data.get("items") or []

    if not target_date:
        raise HTTPException(status_code=400, detail="Date is required")

    bookings_ref = db.collection("bookings")
    query = bookings_ref.where("date", "==", target_date).where("status", "==", "active").stream()
    
    for doc in query:
        existing_booking = doc.to_dict()
        if existing_booking.get("paymentStatus") == "failed":
            continue

        existing_items = existing_booking.get("items", [])
        for item in existing_items:
            existing_title = item.get("title") or item.get("name")
            if existing_title in requested_item_titles:
                return {"available": False, "conflict": existing_title}
                
    return {"available": True}

@router.post("/validate-coupon")
async def validate_coupon(data: dict):   
    code = data.get("code", "").upper().strip()
    if not code:
        raise HTTPException(status_code=400, detail="No code provided")
    
    promo_ref = db.collection("promo_codes").document(code).get()   
    if not promo_ref.exists:
        return {"valid": False, "message": "Invalid promo code."}
    
    promo = promo_ref.to_dict()
    if "expiry" in promo:
        if datetime.utcnow() > promo["expiry"].replace(tzinfo=None):
            return {"valid": False, "message": "This code has expired."}
            
    return {
        "valid": True,
        "amountOff": promo.get("amount", 0),
        "percentOff": promo.get("percent", 0),
        "description": promo.get("description", "Discount Applied!")
    }

@router.post("/create-checkout")
async def create_checkout(data: dict):
    """
    Refined checkout flow: Creates Square customer, calculates exact pricing,
    saves pending record, and generates a Payment Link.
    """
    client = Client(access_token=os.getenv("SQUARE_ACCESS_TOKEN"), environment="production")
    canonical = normalize_payload(data)
    booking_id = str(uuid.uuid4())
    
    # 1. Identity Extraction
    customer_name = data.get("customerName") or data.get("name") or canonical.get("name") or "Valued Customer"
    customer_email = data.get("customerEmail") or data.get("email") or canonical.get("email") or ""
    customer_phone = data.get("customerPhone") or data.get("phone") or canonical.get("phone") or ""
    booking_date = data.get("eventDate") or data.get("date") or canonical.get("date") or ""

    # 2. Address Handling
    raw_addr = data.get("address") or {}
    if isinstance(raw_addr, dict):
        addr_line_1 = raw_addr.get("address_line_1", "")
        city = raw_addr.get("locality", data.get("city", ""))
        delivery_address_display = f"{addr_line_1}, {city}"
        sq_address = {
            "address_line_1": addr_line_1,
            "locality": city,
            "postal_code": raw_addr.get("postal_code", data.get("zip", ""))
        }
    else:
        delivery_address_display = str(raw_addr)
        sq_address = {"address_line_1": delivery_address_display}

    # 3. Pricing Calculation
    cart_items = data.get("cart") or data.get("items") or []
    raw_subtotal = sum(float(i.get("price", 0)) for i in cart_items)
    
    pricing = calculate_totals(
        raw_subtotal,
        data.get("referralType", "None"),
        data.get("damageWaiver", False),
        float(data.get("mileageFee", 0)),
        float(data.get("staffFee", 0)),
        data.get("isTaxExempt", False),
        promo_discount=float(data.get("discount", 0)),
        promo_percent=float(data.get("percentOff", 0))
    )

    # 4. Create Square Customer (Required for Autopay/Card Capture)
    cust_res = client.customers.create_customer({
        "given_name": customer_name,
        "email_address": customer_email,
        "phone_number": customer_phone,
        "address": sq_address
    })
    if "errors" in cust_res.body:
        raise HTTPException(status_code=400, detail="Square Customer creation failed")
    sq_cust_id = cust_res.body['customer']['id']

    # 5. Create Payment Link for Deposit
    item_summary = ", ".join([i.get("title") or i.get("name", "Item") for i in cart_items])
    
    body = {
        "idempotency_key": str(uuid.uuid4()),
        "order": {
            "location_id": os.getenv("SQUARE_LOCATION_ID"),
            "customer_id": sq_cust_id,
            "line_items": [{
                "name": "Buzzy's Party Rental Deposit (35%)",
                "quantity": "1",
                "base_price_money": {"amount": int(pricing["deposit"] * 100), "currency": "USD"}
            }],
            "metadata": { 
                "booking_id": booking_id,
                "mileageFee": str(data.get("mileageFee", 0)) 
            },
            "note": f"BookingID: {booking_id} | Date: {booking_date} | Items: {item_summary}"
        },
        "checkout_options": {
            "redirect_url": "https://www.buzzys.org/booking-success",
            "allow_tipping": True,
            "enable_tipping": True
        }
    }

    checkout_res = client.checkout.create_payment_link(body)
    if "errors" in checkout_res.body:
        raise HTTPException(status_code=500, detail="Square Link Generation Failed")

    checkout_url = checkout_res.body["payment_link"]["url"]

    # 6. Save Final Booking Record
    booking_record = {
        "booking_id": booking_id,
        "name": customer_name,
        "email": customer_email,
        "phone": customer_phone,
        "date": booking_date,
        "items": cart_items,
        "address": delivery_address_display,
        "pricing_breakdown": pricing,
        "deposit": pricing["deposit"],
        "remaining": pricing["remaining"],
        "saveCardForAutopay": data.get("saveCardForAutopay", False),
        "checkout_url": checkout_url,
        "square_customer_id": sq_cust_id,
        "created_at": datetime.utcnow().isoformat(),
        "paymentStatus": "pending",
        "status": "active"
    }

    db.collection("bookings").document(booking_id).set(booking_record)

    # 7. Admin Alert
    send_email_from_file(
        to=["buzzysentertainment@gmail.com", "kandy.stamey@gmail.com"],
        template_name="admin_checkout_started.html",
        subject="Customer Started Checkout",
        params={**booking_record, "total": f"${pricing['total']:.2f}"}
    )

    return {"checkoutUrl": checkout_url}

# ---------------------------------------------------------
# WEBHOOKS
# ---------------------------------------------------------

@router.post("/webhooks/square")
async def square_webhook(request: Request):
    square_signature = request.headers.get("x-square-hmacsha256-signature")
    webhook_secret = os.getenv("SQUARE_WEBHOOK_SIGNATURE_KEY")
    notification_url = "https://buzzys-backend.onrender.com/book/webhooks/square"
    
    raw_body = await request.body()
    if not is_valid_webhook_event_signature(raw_body.decode("utf-8"), square_signature, webhook_secret, notification_url):
        raise HTTPException(status_code=400, detail="Invalid signature")

    payload = await request.json()
    event_type = payload.get("type")
    data_object = payload.get("data", {}).get("object", {})

    if event_type == "payment.updated":
        payment = data_object.get("payment", {})
        if payment.get("status") == "COMPLETED":
            client = Client(access_token=os.getenv("SQUARE_ACCESS_TOKEN"), environment="production")
            order_res = client.orders.retrieve_order(payment.get("order_id"))
            order = order_res.body.get("order", {})
            
            # Extract booking_id from metadata OR manual note parsing
            booking_id = order.get("metadata", {}).get("booking_id")
            if not booking_id and "BookingID:" in order.get("note", ""):
                booking_id = order["note"].split("BookingID:")[1].split("|")[0].strip()

            if booking_id:
                doc_ref = db.collection("bookings").document(booking_id)
                booking = doc_ref.get().to_dict()
                
                if booking and booking.get("paymentStatus") != "deposit_paid":
                    update_payload = {
                        "paymentStatus": "deposit_paid",
                        "square_source_id": payment.get("source_id"),
                        "square_order_id": payment.get("order_id")
                    }
                    doc_ref.update(update_payload)
                    booking.update(update_payload)
                    
                    handle_deposit_received(booking)
                    try:
                        create_booking_event(booking)
                    except Exception as e:
                        print(f"Calendar Sync Error: {e}")

    return {"status": "ok"}

@router.post("/automate-lifecycle")
def automate_lifecycle(request: Request):
    if request.headers.get("X-Cron-Auth") != os.getenv("CRON_SECRET_KEY"):
        raise HTTPException(status_code=403)
        
    today_dt = datetime.utcnow()
    target_autopay = (today_dt + timedelta(days=2)).strftime("%Y-%m-%d")
    
    client = Client(access_token=os.getenv("SQUARE_ACCESS_TOKEN"), environment="production")
    
    # 1. Autopay (2 days before)
    autopay_docs = db.collection("bookings")\
        .where("date", "==", target_autopay)\
        .where("paymentStatus", "==", "deposit_paid")\
        .where("saveCardForAutopay", "==", True).stream()

    for doc in autopay_docs:
        b = doc.to_dict()
        if b.get("square_customer_id") and b.get("square_source_id"):
            res = client.payments.create_payment({
                "source_id": b["square_source_id"],
                "customer_id": b["square_customer_id"],
                "idempotency_key": str(uuid.uuid4()),
                "amount_money": {"amount": int(b["remaining"] * 100), "currency": "USD"},
                "note": f"Autopay Final Balance - Booking {b['booking_id']}"
            })
            if "errors" not in res.body:
                doc.reference.update({"paymentStatus": "balance_paid"})
                handle_balance_paid(b)
            else:
                handle_payment_declined(b)

    # 2. Event Reminders (Day of)
    today_str = today_dt.strftime("%Y-%m-%d")
    reminder_docs = db.collection("bookings").where("date", "==", today_str).where("status", "==", "active").stream()
    for doc in reminder_docs:
        handle_event_reminder(doc.to_dict())

    return {"status": "success"}

@router.get("/all")
def get_all_bookings():
    docs = db.collection("bookings").stream()
    cleaned = []
    for doc in docs:
        b = doc.to_dict()
        b["id"] = doc.id
        cleaned.append(b)
    cleaned.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return cleaned