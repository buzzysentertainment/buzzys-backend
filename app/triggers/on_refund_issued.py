from app.services.email_service import send_email

def handle_refund_issued(booking: dict, amount: float):
    """
    Triggered when a refund is issued.
    Sends a refund confirmation email.
    """
    customer = booking.get("customerName")
    event_date = booking.get("eventDate")

    html = (
        f"<h2>Refund Issued</h2>"
        f"<p>Hi {customer},</p>"
        f"<p>A refund of <strong>${amount:.2f}</strong> has been issued "
        f"for your event on <strong>{event_date}</strong>.</p>"
        f"<p>If you have questions, feel free to reach out.</p>"
    )

    return send_email(
        to=booking.get("customerEmail"),
        subject="Refund Issued",
        html=html
    )
