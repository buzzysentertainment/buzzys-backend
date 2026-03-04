from google.oauth2 import service_account
from googleapiclient.discovery import build
from app.root_schema import build_calendar_payload

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CALENDAR_ID = "buzzysentertainment@gmail.com"  # Owner's Google Calendar email

def get_calendar_service():
    creds = service_account.Credentials.from_service_account_file(
        "app/google-service-account.json",  # Path to your JSON file
        scopes=SCOPES,
    )
    return build("calendar", "v3", credentials=creds)

def create_booking_event(booking):
    service = get_calendar_service()

    summary = f"Buzzy’s Booking – {booking.get('name', 'Unknown')}"
    location = booking.get("address", "No address provided")

    description = (
        f"Items:\n" +
        "\n".join([f"- {i.get('title')}" for i in booking.get("items", [])]) +
        f"\n\nTotal: ${booking.get('total', 0)}\n"
        f"Phone: {booking.get('phone', '')}\n"
        f"Email: {booking.get('email', '')}\n"
        f"Status: {booking.get('status', 'Pending')}"
    )

    date = booking.get("date")

    event_body = {
        "summary": summary,
        "location": location,
        "description": description,
        "start": {"date": date},
        "end": {"date": date},
    }

    event = service.events().insert(calendarId=CALENDAR_ID, body=event_body).execute()
    return event.get("id")
    
def update_booking_event(event_id, booking):
    service = get_calendar_service()

    summary = f"Buzzy’s Booking – {booking.get('name', 'Unknown')}"
    location = booking.get("address", "No address provided")

    description = (
        f"Items:\n" +
        "\n".join([f"- {i.get('title')}" for i in booking.get("items", [])]) +
        f"\n\nTotal: ${booking.get('total', 0)}\n"
        f"Phone: {booking.get('phone', '')}\n"
        f"Email: {booking.get('email', '')}\n"
        f"Status: {booking.get('paymentStatus', 'Pending')}"
    )

    date = booking.get("date")

    event_body = {
        "summary": summary,
        "location": location,
        "description": description,
        "start": {"date": date},
        "end": {"date": date},
    }

    updated_event = service.events().update(
        calendarId=CALENDAR_ID,
        eventId=event_id,
        body=event_body
    ).execute()

    return updated_event.get("id")
