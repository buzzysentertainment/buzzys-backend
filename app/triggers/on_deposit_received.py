import os
from app.services.email_service import send_email_template, generate_ics_content

def handle_deposit_received(booking: dict):
    template_id = os.getenv("RESEND_BOOKING_CONFIRMATION_TEMPLATE") # Use your main confirmation ID

    # Generate the calendar file content
    ics_content = generate_ics_content(booking)
    
    # Map the data to match your Resend Template variables exactly
    # If Resend uses {{name}}, use "name" here.
    data = {
        "name": booking.get("name"),
        "date": booking.get("date"),
        "total": booking.get("total") or booking.get("pricing_breakdown", {}).get("total"),
        "deposit": booking.get("deposit"),
        "remaining": booking.get("remaining"),
        "address": booking.get("address")
    }

    # Prepare the attachment for Resend
    attachments = [
        {
            "content": ics_content,
            "filename": "event-reminder.ics",
        }
    ]

    print(f"TRIGGER: Sending deposit confirmation to {booking.get('email')}")

    return send_email_template(
        to=booking.get("email"),
        template_id=template_id,
        data=data,
        attachments=attachments
    )