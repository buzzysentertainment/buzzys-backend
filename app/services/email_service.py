import os
import resend
from dotenv import load_dotenv
from app.root_schema import normalize_payload, validate_payload, build_square_metadata
from app.services.firebase_setup import db

load_dotenv()
resend.api_key = os.getenv("RESEND_API_KEY")

# -------------------------------------------------
# Firestore Lookup
# -------------------------------------------------
def get_booking_by_id(booking_id: str):
    try:
        doc = db.collection("bookings").document(booking_id).get()
        if doc.exists:
            return doc.to_dict()
        else:
            print(f"FIRESTORE: No booking found for ID {booking_id}")
            return None
    except Exception as e:
        print(f"FIRESTORE LOOKUP ERROR: {e}")
        return None


# -------------------------------------------------
# ICS Generator
# -------------------------------------------------
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


# -------------------------------------------------
# Fully Backed-Up Email Service
# -------------------------------------------------
def send_email_template(to, template_id=None, data=None, html_content=None, attachments=None):
    try:
        data = data or {}

        # -------------------------------------------------
        # 1. Firestore Backup Lookup
        # -------------------------------------------------
        booking_id = data.get("booking_id")
        booking = None

        if booking_id:
            booking = get_booking_by_id(booking_id)

            if booking:
                # List of all fields we want to back up
                backup_fields = [
                    "name", "email", "date", "remaining", "deposit", "total",
                    "address", "phone", "deliveryTime", "pickupTime",
                    "status", "paymentStatus", "referral_type",
                    "saveCardForAutopay", "signature", "items", "pricing_breakdown"
                ]

                # Merge missing fields from Firestore
                for field in backup_fields:
                    if not data.get(field):
                        data[field] = booking.get(field)

                # Fix missing "to"
                if not to:
                    to = booking.get("email")

        # -------------------------------------------------
        # 2. Final Safety Check for "to"
        # -------------------------------------------------
        if not to or str(to).lower() in ["undefined", "none", "null", ""]:
            print(f"ABORTING EMAIL: Invalid recipient ({to})")
            return {"status": "error", "message": "Missing or invalid recipient email"}

        recipients = to if isinstance(to, list) else [to]

        # -------------------------------------------------
        # 3. Build Resend Params
        # -------------------------------------------------
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

        # -------------------------------------------------
        # 4. Send Email
        # -------------------------------------------------
        response = resend.Emails.send(params)
        print(f"RESEND SUCCESS: Sent to {recipients}")
        return {"status": "success", "response": response}

    except Exception as e:
        print(f"CRITICAL EMAIL ERROR: {str(e)}")
        return {"status": "error", "message": str(e)}
def send_email_from_file(to, template_name, subject, params):
    try:
        # 1. Load HTML file
        template_path = os.path.join("app", "email_templates", template_name)
        with open(template_path, "r") as f:
            html = f.read()

        # 2. Replace {{variables}}
        for key, value in params.items():
            html = html.replace(f"{{{{{key}}}}}", str(value))

        # 3. Build Resend payload
        recipients = to if isinstance(to, list) else [to]

        payload = {
            "from": "Buzzy’s Inflatables <bookings@buzzys.org>",
            "to": recipients,
            "subject": subject,
            "html": html
        }

        # 4. Send email
        response = resend.Emails.send(payload)
        print(f"RESEND SUCCESS (file template): Sent to {recipients}")
        return {"status": "success", "response": response}

    except Exception as e:
        print(f"CRITICAL EMAIL ERROR (file template): {str(e)}")
        return {"status": "error", "message": str(e)}
