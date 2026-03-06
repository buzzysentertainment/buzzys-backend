import os
import resend
from dotenv import load_dotenv
from app.root_schema import normalize_payload, validate_payload, build_square_metadata
from app.firestore import get_booking_by_id  # <-- make sure this import exists

load_dotenv()

resend.api_key = os.getenv("RESEND_API_KEY")

def generate_ics_content(booking_data):
    date_clean = booking_data.get("date", "").replace("-", "")
    ics_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Buzzys Entertainment//Booking//EN",
        "BEGIN:VEVENT",
        f"DTSTART:{date_clean}T120000Z",
        f"DTEND:{date_clean}T160000Z",
        f"SUMMARY:Buzzy's Party: {booking_data.get('name', 'Customer')}",
        f"DESCRIPTION:Remaining Balance: ${booking_data.get('remaining', 0)}",
        f"LOCATION:{booking_data.get('address', 'TBD')}",
        "END:VEVENT",
        "END:VCALENDAR"
    ]
    return "\n".join(ics_lines)


def send_email_template(to, template_id=None, data=None, html_content=None, attachments=None):
    try:
        data = data or {}

        # 🔥 NEW: If booking_id exists, fetch full booking to fill missing fields
        booking_id = data.get("booking_id")
        if booking_id:
            booking = get_booking_by_id(booking_id)
            if booking:
                # Fill missing fields from Firestore
                data["name"] = data.get("name") or booking.get("name")
                data["email"] = data.get("email") or booking.get("email")
                data["date"] = data.get("date") or booking.get("date")
                data["remaining"] = data.get("remaining") or booking.get("remaining")
                data["deposit"] = data.get("deposit") or booking.get("deposit")
                data["total"] = data.get("total") or booking.get("total")

                # If 'to' is missing, use booking email
                if not to:
                    to = booking.get("email")

        # 🔥 FINAL SAFETY CHECK
        if not to or str(to).lower() == "undefined":
            print(f"ABORTING EMAIL: Recipient 'to' is invalid ({to}).")
            return {"status": "error", "message": "Missing recipient email"}

        recipients = to if isinstance(to, list) else [to]

        params = {
            "from": "Buzzy’s Inflatables <bookings@buzzys.org>",
            "to": recipients,
            "subject": data.get("subject", "Your Booking with Buzzy’s!"),
        }

        if template_id:
            params["template_id"] = template_id
            params["params"] = data
        elif html_content:
            params["html"] = html_content
        else:
            params["html"] = f"<p>Hi {data.get('name', 'Customer')}, thanks for booking!</p>"

        if attachments:
            params["attachments"] = attachments

        response = resend.Emails.send(params)
        print(f"RESEND SUCCESS: Sent to {recipients}")
        return {"status": "success", "response": response}

    except Exception as e:
        print(f"CRITICAL EMAIL ERROR: {str(e)}")
        return {"status": "error", "message": str(e)}
