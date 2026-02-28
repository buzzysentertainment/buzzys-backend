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
    
def send_email_template(to, template_id=None, data=None, html_content=None, attachments=None):
    try:
        # FIX 1: Ensure 'to' is valid and not the string "undefined"
        if not to or str(to).lower() == "undefined":
            print(f"ABORTING EMAIL: Recipient 'to' is invalid ({to}).")
            return {"status": "error", "message": "Missing recipient email"}

        # Resend expects a list for the 'to' field
        recipients = to if isinstance(to, list) else [to]
        
        # Ensure data is a dictionary so we don't get "undefined"
        data = data or {}

        # FIX 2: Build the params correctly
        params = {
            "from": "Buzzy’s Inflatables <bookings@buzzys.org>", # Verified domain
            "to": recipients,
            "subject": data.get("subject", "Your Booking with Buzzy’s!"),
        }

        # FIX 3: Handle Template OR Manual HTML (to prevent those "undefined" logs)
        if template_id:
            params["template_id"] = template_id
            params["params"] = data
        elif html_content:
            params["html"] = html_content
        else:
            # Fallback if both are missing
            params["html"] = f"<p>Hi {data.get('name', 'Customer')}, thanks for booking!</p>"

        if attachments:
            params["attachments"] = attachments

        response = resend.Emails.send(params)
        print(f"RESEND SUCCESS: Sent to {recipients}")
        return {"status": "success", "response": response}

    except Exception as e:
        print(f"CRITICAL EMAIL ERROR: {str(e)}")
        return {"status": "error", "message": str(e)}