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
    try:
        # SAFETY CHECK: If 'to' is missing or the string "undefined", stop the crash
        if not to or to == "undefined":
            print(f"ABORTING EMAIL: Recipient 'to' is {to}. Cannot send to nobody.")
            return {"status": "error", "message": "Missing recipient email"}

        # Ensure 'to' is a list (Resend requirement)
        recipients = to if isinstance(to, list) else [to]

        params = {
            "from": "Buzzy’s Inflatables <no-reply@buzzys.org>",
            "to": recipients,
            "template_id": template_id,
            "params": data  # Note: Resend Python SDK often uses 'params' for template data
        }

        if attachments:
            params["attachments"] = attachments

        response = resend.Emails.send(params)
        return {"status": "success", "response": response}

    except Exception as e:
        print(f"CRITICAL EMAIL ERROR: {str(e)}")
        return {"status": "error", "message": str(e)}