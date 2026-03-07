import os
from app.services.email_service import send_email_from_file

def handle_event_reminder(booking: dict):
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

    return send_email_from_file(
        to=[booking.get("customerEmail")],
        template_name="event_reminder.html",
        subject="Your Event Reminder",
        params=data
    )
