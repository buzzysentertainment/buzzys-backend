import os
from app.services.email_service import send_email_template

def handle_balance_paid(booking: dict):
    template_id = os.getenv("RESEND_BALANCE_PAID_TEMPLATE_ID")

    data = {
        "customer_name": booking.get("customerName"),
        "event_date": booking.get("eventDate"),
        "remaining_amount": booking.get("remaining")
    }

    return send_email_template(
        to=booking.get("customerEmail"),
        template_id=template_id,
        data=data
    )
