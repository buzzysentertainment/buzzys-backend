from app.services.email_service import send_email
from app.email_templates.contract_received import contract_received_template

def handle_contract_received(booking: dict):
    """
    Triggered when a customer marks their contract as received.
    Sends a confirmation email to the customer.
    """
    html = contract_received_template(
        customer_name=booking.get("customerName"),
        event_date=booking.get("eventDate"),
        event_name=booking.get("eventName")
    )

    return send_email(
        to=booking.get("customerEmail"),
        subject="We Received Your Contract",
        html=html
    )
