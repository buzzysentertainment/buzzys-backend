from fastapi import APIRouter
from app.services.email_service import send_email

router = APIRouter(prefix="/test-email", tags=["email"])

@router.get("/")
def test_email():
    return send_email(
        to="your-email@example.com",
        subject="Test Email from Buzzy’s Backend",
        html="<h1>Hello Emma!</h1><p>Your backend email system works.</p>"
    )