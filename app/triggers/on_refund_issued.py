from app.services.email_service import send_email
from app.email_templates.refund_issued import refund_issued_template

def handle_refund_issued(booking: dict, amount: float):
    html = refund_issued_template(
        customer_name=booking["name"],
        amount=amount
    )

    return send_email(
        to=booking["email"],
        subject="Your Refund Has Been Processed",
        html=html
    )
