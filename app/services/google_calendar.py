import os
import json
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from app.root_schema import build_calendar_payload

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CALENDAR_ID = "buzzysentertainment@gmail.com"  # Owner's Google Calendar email


def get_calendar_service():
    """
    Loads Google service account credentials from the Render environment variable
    GOOGLE_SERVICE_ACCOUNT_JSON instead of a local file.
    """

    # Load JSON string from environment
    service_account_info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])

    # Build credentials object
    creds = service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=SCOPES,
    )

    # Build Google Calendar API client
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

    # Convert MM/DD/YYYY → YYYY-MM-DD
    raw_date = booking.get("date")
    parsed = datetime.strptime(raw_date, "%m/%d/%Y")
    google_date = parsed.strftime("%Y-%m-%d")

    event_body = {
        "summary": summary,
        "location": location,
        "description": description,
        "start": {"date": google_date},
        "end": {"date": google_date},
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

    # Convert MM/DD/YYYY → YYYY-MM-DD
    raw_date = booking.get("date")
    parsed = datetime.strptime(raw_date, "%m/%d/%Y")
    google_date = parsed.strftime("%Y-%m-%d")

    event_body = {
        "summary": summary,
        "location": location,
        "description": description,
        "start": {"date": google_date},
        "end": {"date": google_date},
    }

    updated_event = service.events().update(
        calendarId=CALENDAR_ID,
        eventId=event_id,
        body=event_body
    ).execute()

    return updated_event.get("id")
