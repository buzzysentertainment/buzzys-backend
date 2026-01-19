import os
from app.services.email_service import send_email_template

def handle_contract_received(booking: dict):
    template_id = os.getenv("RESEND_CONTRACT_RECEIVED_TEMPLATE_ID")

    data = {
        "customer_name": booking.get("customerName"),
        "event_date": booking.get("eventDate"),
        "event_name": booking.get("eventName")
    }

    return send_email_template(
        to=booking.get("customerEmail"),
        template_id=template_id,
        data=data
    )
