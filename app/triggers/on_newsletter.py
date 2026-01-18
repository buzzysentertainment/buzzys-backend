from app.services.email_service import send_email
from app.email_templates.newsletter import newsletter_template

def send_newsletter(to_email: str, title: str, body_html: str):
    html = newsletter_template(title, body_html)

    return send_email(
        to=to_email,
        subject=title,
        html=html
    )
