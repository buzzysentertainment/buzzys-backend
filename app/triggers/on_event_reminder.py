import os
from app.services.email_service import send_email_template

def handle_event_reminder(booking: dict):
    template_id = os.getenv("RESEND_EVENT_REMINDER_TEMPLATE_ID")

    data = {
        "customer_name": booking.get("customerName"),
        "balance_due": booking.get("balance"),
        "arrival_time": booking.get("setupStart"),
        "rental_items": booking.get("rentals"),
        "event_street": booking.get("eventStreet"),
        "event_city": booking.get("eventCity"),
        "event_datetime": booking.get("fullEventTimeText"),
        "booking_id": booking.get("booking_id")
    }

    return send_email_template(
        to=booking.get("customerEmail"),
        template_id=template_id,
        data=data
    )
