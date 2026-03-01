import os
import uuid
from square.client import Client
from app.services.email_service import send_email_template, generate_ics_content

def handle_deposit_received(booking: dict):
    # --- 1. SQUARE SETUP ---
    client = Client(
        access_token=os.getenv("SQUARE_ACCESS_TOKEN"),
        environment="production" 
    )

    # --- 2. CREATE THE BALANCE INVOICE ---
    remaining_val = booking.get("remaining", 0)
    remaining_cents = int(float(remaining_val) * 100)
    
    invoice_body = {
        "invoice": {
            "location_id": os.getenv("SQUARE_LOCATION_ID"),
            "order_id": booking.get("order_id"),
            "primary_recipient": {
                "customer_id": booking.get("square_customer_id")
            },
            "payment_requests": [{
                "request_type": "BALANCE",
                "due_date": booking.get("date"),
                "amount_money": {
                    "amount": remaining_cents,
                    "currency": "USD"
                }
            }],
            "delivery_method": "SHARE_EXTERNALLY",
            "title": f"Remaining Balance - Event on {booking.get('date')}"
        },
        "idempotency_key": str(uuid.uuid4())
    }

    pay_link = "https://www.buzzys.org/pay" 
    
    try:
        create_result = client.invoices.create_invoice(body=invoice_body)
        if create_result.is_success():
            invoice = create_result.body["invoice"]
            publish_result = client.invoices.publish_invoice(
                invoice_id=invoice["id"],
                body={
                    "version": invoice["version"],
                    "idempotency_key": str(uuid.uuid4())
                }
            )
            if publish_result.is_success():
                pay_link = publish_result.body["invoice"]["public_url"]
    except Exception as e:
        print(f"SQUARE INVOICE ERROR: {str(e)}")

    # --- 3. PREPARE ITEM LIST ---
    items_raw = booking.get("items", [])
    item_names = [i.get("title") or i.get("name") or "Party Gear" for i in items_raw if isinstance(i, dict)]
    display_items = ", ".join(item_names) if item_names else "Party Gear"

    # --- 4. SEND CONFIRMATION EMAIL ---
    template_id = os.getenv("RESEND_BOOKING_CONFIRMATION_TEMPLATE")
    ics_content = generate_ics_content(booking)
    
    total_val = booking.get("pricing_breakdown", {}).get("total") or booking.get("total", 0)

    # UPDATED DICTIONARY TO MATCH YOUR RESEND TEMPLATE EXACTLY
    email_data = {
        "customer_name": booking.get("name"),
        "event_date": booking.get("date"),
        "total_amount": f"{float(total_val):.2f}",
        "deposit_amount": f"{float(booking.get('deposit', 0)):.2f}",
        "remaining_amount": f"{float(remaining_val):.2f}",
        "booking_id": booking.get("booking_id"), # Added this!
        "items": display_items,
        "pay_link": pay_link 
    }

    attachments = [{"content": ics_content, "filename": "event-reminder.ics"}]

    return send_email_template(
        to=booking.get("email"),
        template_id=template_id,
        data=email_data,
        attachments=attachments
    )