import os
import uuid
from square.client import Client
from app.services.email_service import send_email_template, generate_ics_content
# from app.main import db  # Ensure your firestore 'db' is imported here

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
    # We take the 'remaining' amount and convert to cents for Square
    remaining_cents = int(float(booking.get("remaining", 0)) * 100)
    
    invoice_body = {
        "invoice": {
            "location_id": os.getenv("SQUARE_LOCATION_ID"),
            "order_id": booking.get("order_id"),
            "primary_recipient": {
                "customer_id": booking.get("square_customer_id") # Must exist in Firebase
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
        # Create the Draft
        create_result = client.invoices.create_invoice(body=invoice_body)
        
        if create_result.is_success():
            invoice = create_result.body["invoice"]
            
            # --- 3. PUBLISH TO GET THE LIVE LINK ---
            publish_result = client.invoices.publish_invoice(
                invoice_id=invoice["id"],
                body={
                    "version": invoice["version"],
                    "idempotency_key": str(uuid.uuid4())
                }
            )
            
            if publish_result.is_success():
                pay_link = publish_result.body["invoice"]["public_url"]
                
                # --- 4. SAVE TO FIREBASE ---
                # This allows your 2-day reminder script to find the link later
                # db.collection("bookings").document(booking.get("booking_id")).update({
                #    "invoice_url": pay_link,
                #    "invoice_id": invoice["id"]
                # })
                print(f"SUCCESS: Invoice published for {booking.get('booking_id')}")

    except Exception as e:
        print(f"SQUARE INVOICE ERROR: {str(e)}")

    # --- 5. SEND CONFIRMATION EMAIL ---
    template_id = os.getenv("RESEND_BOOKING_CONFIRMATION_TEMPLATE")
    ics_content = generate_ics_content(booking)
    
    # We add the pay_link to the data so the customer has it immediately
    email_data = {
        "name": booking.get("name"),
        "date": booking.get("date"),
        "total": booking.get("total"),
        "deposit": booking.get("deposit"),
        "remaining": booking.get("remaining"),
        "address": booking.get("address"),
        "pay_link": pay_link 
    }

    attachments = [{"content": ics_content, "filename": "event-reminder.ics"}]

    return send_email_template(
        to=booking.get("email"),
        template_id=template_id,
        data=email_data,
        attachments=attachments
    )