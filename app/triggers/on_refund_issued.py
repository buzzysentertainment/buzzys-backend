import os
from app.services.email_service import send_email_template

def handle_refund_issued(booking: dict, amount: float):
    template_id = os.getenv("RESEND_REFUND_ISSUED_TEMPLATE_ID")

    data = {
        "customer_name": booking.get("customerName"),
        "event_date": booking.get("eventDate"),
        "refund_amount": amount
    }

    return send_email_template(
        to=booking.get("customerEmail"),
        template_id=template_id,
        data=data
    )
