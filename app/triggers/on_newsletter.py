import os
from app.services.email_service import send_email_template

def handle_newsletter(email: str, data: dict):
    template_id = os.getenv("RESEND_NEWSLETTER_TEMPLATE_ID")

    return send_email_template(
        to=email,
        template_id=template_id,
        data=data
    )
