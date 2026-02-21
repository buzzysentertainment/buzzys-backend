import os
import resend
from dotenv import load_dotenv

load_dotenv()

resend.api_key = os.getenv("RESEND_API_KEY")

def generate_ics_content(booking_data):
    """Formats booking info into a standard calendar file string."""
    date_clean = booking_data.get("date", "").replace("-", "")
    
    # Standard ICS format (UTC format: YYYYMMDDTHHMMSSZ)
    ics_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Buzzys Entertainment//Booking//EN",
        "BEGIN:VEVENT",
        f"DTSTART:{date_clean}T120000Z", # Default 12pm
        f"DTEND:{date_clean}T160000Z",   # Default 4pm
        f"SUMMARY:Buzzy's Party: {booking_data.get('name', 'Customer')}",
        f"DESCRIPTION:Remaining Balance: ${booking_data.get('remaining', 0)}",
        f"LOCATION:{booking_data.get('address', 'TBD')}",
        "END:VEVENT",
        "END:VCALENDAR"
    ]
    return "\n".join(ics_lines)
    
def send_email_template(to, template_id: str, data: dict, attachments=None):
    """
    Updated logic to handle multiple recipients and calendar attachments.
    """
    try:
        # LOGIC 1: Ensure 'to' is always a list for Resend
        recipients = to if isinstance(to, list) else [to]

        # Build the basic email parameters
        params = {
            "from": "Buzzy’s Inflatables <no-reply@buzzys.org>",
            "to": recipients,
            "template_id": template_id,
            "data": data
        }

        # LOGIC 2: Only add attachments to the request if they exist
        if attachments:
            params["attachments"] = attachments

        response = resend.Emails.send(params)
        return {"status": "success", "response": response}

    except Exception as e:
        # LOGIC 3: Print the error to your Render terminal for debugging
        print(f"CRITICAL EMAIL ERROR: {str(e)}")
        return {"status": "error", "message": str(e)}