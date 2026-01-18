from app.services.email_service import send_email
from app.email_templates.balance_paid import balance_paid_template

def handle_balance_paid(booking: dict):
    html = balance_paid_template(
        customer_name=booking["name"],
        event_date=booking["date"]
    )

    return send_email(
        to=booking["email"],
        subject="Remaining Balance Paid",
        html=html
    )
