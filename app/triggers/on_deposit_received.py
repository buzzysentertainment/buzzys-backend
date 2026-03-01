import os
import uuid
from square.client import Client
from app.services.email_service import send_email_template, generate_ics_content
# from app.services.firebase_setup import db # Uncomment if you want to save the link back to DB

def handle_deposit_received(booking: dict):
    """
    Triggered when a deposit is paid. 
    1. Creates/Publishes a Square Invoice for the remaining balance.
    2. Updates Firebase with the new Invoice URL.
    3. Sends the Confirmation Email with the Calendar Invite.
    """
    
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

    pay_link = "https://www.buzzys.org/pay" # Safety Fallback
    
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
                print(f"SUCCESS: Invoice published for {booking.get('booking_id')}")

    except Exception as e:
        print(f"SQUARE INVOICE ERROR: {str(e)}")

    # --- 3. PREPARE ITEM LIST ---
    # This prevents the "undefined" error for items in Resend
    items_raw = booking.get("items", [])
    item_names = []
    for item in items_raw:
        if isinstance(item, dict):
            name = item.get("title") or item.get("name") or "Equipment"
        else:
            name = str(item)
        item_names.append(name)
    
    display_items = ", ".join(item_names) if item_names else "Party Gear"

    # --- 4. SEND CONFIRMATION EMAIL ---
    template_id = os.getenv("RESEND_BOOKING_CONFIRMATION_TEMPLATE")
    ics_content = generate_ics_content(booking)
    
    # Reach into pricing_breakdown for the total if it's nested there
    total_val = booking.get("pricing_breakdown", {}).get("total") or booking.get("total", 0)

    email_data = {
        "name": booking.get("name"),
        "date": booking.get("date"),
        "total": f"${float(total_val):.2f}",
        "deposit": f"${float(booking.get('deposit', 0)):.2f}",
        "remaining": f"${float(remaining_val):.2f}",
        "address": booking.get("address"),
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