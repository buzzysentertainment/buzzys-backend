from app.services.email_service import send_email
from app.email_templates.review_request import review_request_template

def handle_review_request(booking: dict):
    review_link = "https://g.page/r/Cc9k0Q2xJtNfEBM/review"  # your actual Google review link

    html = review_request_template(
        customer_name=booking["name"],
        review_link=review_link
    )

    return send_email(
        to=booking["email"],
        subject="How Was Your Experience With Buzzy’s?",
        html=html
    )
