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
# Create Square Checkout Link + Invoice
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
    booking_date = data.get("date", "")  # format: MM/DD/YYYY

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
    # Build line items for DEPOSIT ONLY
    # -------------------------
    line_items = [
        {
            "name": "Total Due Today (35% Deposit)",
            "quantity": "1",
            "base_price_money": {
                "amount": int(deposit * 100),  # charge ONLY the deposit
                "currency": "USD"
            }
        },
        {
            "name": f"Remaining Balance Due on Event Date (${remaining:.2f})",
            "quantity": "1",
            "base_price_money": {
                "amount": 0,  # informational only
                "currency": "USD"
            }
        }
    ]

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

    # -------------------------
    # Create Square Customer (for invoice)
    # -------------------------
    invoice_id = None
    invoice_url = None

    try:
        customer_body = {
            "idempotency_key": str(uuid.uuid4()),
            "given_name": customer_name,
            "email_address": customer_email,
            "phone_number": customer_phone
        }

        customer_result = client.customers.create_customer(customer_body)

        if "errors" in customer_result.body:
            print("SQUARE CUSTOMER ERROR:", customer_result.body["errors"])
        else:
            customer_id = customer_result.body["customer"]["id"]

            # -------------------------
            # Parse event date (MM/DD/YYYY → YYYY-MM-DD)
            # -------------------------
            try:
                event_date = datetime.strptime(booking_date, "%m/%d/%Y")
                square_due_date = event_date.strftime("%Y-%m-%d")
            except Exception as e:
                print("DATE PARSE ERROR:", e)
                square_due_date = datetime.utcnow().strftime("%Y-%m-%d")

            # -------------------------
            # Create invoice for remaining balance
            # -------------------------
            invoice_body = {
                "idempotency_key": str(uuid.uuid4()),
                "invoice": {
                    "location_id": location_id,
                    "customer_id": customer_id,
                    "title": "Remaining Balance for Buzzy’s Booking",
                    "description": f"Remaining balance for event on {booking_date}",
                    "payment_requests": [
                        {
                            "request_type": "BALANCE",
                            "due_date": square_due_date,
                            "tipping_enabled": False,
                            "fixed_amount_requested_money": {
                                "amount": int(remaining * 100),
                                "currency": "USD"
                            }
                        }
                    ]
                }
            }

            invoice_result = client.invoices.create_invoice(invoice_body)

            if "errors" in invoice_result.body:
                print("SQUARE INVOICE ERROR:", invoice_result.body["errors"])
            else:
                invoice_id = invoice_result.body["invoice"]["id"]
                invoice_version = invoice_result.body["invoice"]["version"]

                publish_result = client.invoices.publish_invoice(
                    invoice_id=invoice_id,
                    body={"version": invoice_version}
                )

                if "errors" in publish_result.body:
                    print("SQUARE INVOICE PUBLISH ERROR:", publish_result.body["errors"])
                else:
                    invoice_url = publish_result.body["invoice"].get("public_url")
                    print("INVOICE CREATED AND PUBLISHED:", invoice_id, invoice_url)

    except Exception as e:
        print("Failed to create or publish invoice:", e)

    # -------------------------
    # Attach invoice info to booking record (if created)
    # -------------------------
    if invoice_id:
        booking_record["invoice_id"] = invoice_id
    if invoice_url:
        booking_record["invoice_url"] = invoice_url

    # Save booking to Firestore
    db.collection("bookings").add(booking_record)

    # -------------------------
    # Send admin email
    # -------------------------
    try:
        admin_html = (
            f"<p>New booking started by {customer_name} for {booking_date}.</p>"
            f"<p>Total: ${total_dollars:.2f}<br>"
            f"Deposit (35%): ${deposit:.2f}<br>"
            f"Remaining: ${remaining:.2f}</p>"
            f"<p>Time Slot: {time_slot}<br>"
            f"Time Period: {time_period}</p>"
            f"<p>Checkout Link: <a href='{checkout_url}'>{checkout_url}</a></p>"
        )
        if invoice_url:
            admin_html += f"<p>Invoice Link (Remaining Balance): <a href='{invoice_url}'>{invoice_url}</a></p>"

        send_email(
            to="admin@buzzys.org",
            subject="New Booking Checkout Started",
            html=admin_html
        )
    except Exception as e:
        print("Failed to send admin email:", e)

    # -------------------------
    # Return checkout URL (and invoice URL if created)
    # -------------------------
    response = {"checkoutUrl": checkout_url}
    if invoice_url:
        response["invoiceUrl"] = invoice_url

    return response
