import os
from app.services.email_service import send_email_template

def handle_review_request(booking: dict):
    template_id = os.getenv("RESEND_REVIEW_REQUEST_TEMPLATE_ID")

    data = {
        "customer_name": booking.get("customerName"),
        "event_date": booking.get("eventDate"),
        "review_link": booking.get("reviewLink")
    }

    return send_email_template(
        to=booking.get("customerEmail"),
        template_id=template_id,
        data=data
    )
