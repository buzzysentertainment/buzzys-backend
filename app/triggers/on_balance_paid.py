import os
from app.services.email_service import send_email_from_file

def handle_balance_paid(booking: dict):
    data = {
        "customer_name": booking.get("name"),
        "event_date": booking.get("date"),
        "total_amount": booking.get("total"),
        "deposit_amount": booking.get("deposit"),
        "remaining_amount": booking.get("remaining"),
        "booking_id": booking.get("booking_id")
    }

    return send_email_from_file(
        to=[booking.get("email")],
        template_name="balance_paid.html",
        subject="Your Final Balance Is Paid",
        params=data
    )
