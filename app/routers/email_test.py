from fastapi import APIRouter
from app.services.email_service import send_email_template
import os

router = APIRouter(prefix="/test-email", tags=["email"])

@router.get("/")
def test_email():
    template_id = os.getenv("RESEND_TEST_TEMPLATE_ID")

    return send_email_template(
        to="your-email@example.com",
        template_id=template_id,
        data={
            "message": "Your backend email system works with Resend templates."
        }
    )
