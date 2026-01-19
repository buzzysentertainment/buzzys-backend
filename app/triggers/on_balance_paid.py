from app.services.email_service import send_email

def handle_balance_paid(booking: dict):
    """
    Triggered when the remaining balance is paid.
    Sends a final payment confirmation email.
    """
    customer = booking.get("customerName")
    event_date = booking.get("eventDate")
    remaining = booking.get("remaining")

    html = (
        f"<h2>Final Payment Received</h2>"
        f"<p>Hi {customer},</p>"
        f"<p>Your remaining balance for the event on "
        f"<strong>{event_date}</strong> has been paid in full.</p>"
        f"<p>Amount Paid: <strong>${remaining:.2f}</strong></p>"
        f"<p>We look forward to your event!</p>"
    )

    return send_email(
        to=booking.get("customerEmail"),
        subject="Final Payment Received",
        html=html
    )
