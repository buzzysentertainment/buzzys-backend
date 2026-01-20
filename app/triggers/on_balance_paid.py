import os
from app.services.email_service import send_email_template

def handle_balance_paid(booking: dict):
    template_id = os.getenv("RESEND_BALANCE_PAID_TEMPLATE_ID")

    data = {
        "customer_name": booking.get("name"),
        "event_date": booking.get("date"),
        "total_amount": booking.get("total"),
        "deposit_amount": booking.get("deposit"),
        "remaining_amount": booking.get("remaining"),
        "booking_id": booking.get("booking_id")
    }

    return send_email_template(
        to=booking.get("email"),
        template_id=template_id,
        data=data
    )
