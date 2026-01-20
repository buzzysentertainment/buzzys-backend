import os
from app.services.email_service import send_email_template

def handle_refund_issued(booking: dict, amount: float):
    template_id = os.getenv("RESEND_REFUND_ISSUED_TEMPLATE_ID")

    data = {
        "customer_name": booking.get("name"),
        "event_date": booking.get("date"),
        "refund_amount": amount,
        "total_amount": booking.get("total"),
        "booking_id": booking.get("booking_id")
    }

    return send_email_template(
        to=booking.get("email"),
        template_id=template_id,
        data=data
    )
