import os
import json
from datetime import datetime
import pytz
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CALENDAR_ID = "buzzysentertainment@gmail.com"  # Owner's Google Calendar email


def get_calendar_service():
    """
    Loads Google service account credentials from the environment variable
    GOOGLE_SERVICE_ACCOUNT_JSON instead of a local file.
    """
    service_account_info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    creds = service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=SCOPES,
    )
    return build("calendar", "v3", credentials=creds)


def build_event_times(booking):
    """
    Combine booking date + delivery/pickup times into proper ISO datetimes.
    """
    tz = pytz.timezone("America/Chicago")  # adjust to your client’s timezone
    raw_date = booking.get("date")  # e.g. "05/20/2026"
    start_time = booking.get("deliveryTime", "10:00 AM")
    end_time = booking.get("pickupTime", "6:00 PM")

    # Parse MM/DD/YYYY + time → datetime
    start_dt = tz.localize(datetime.strptime(f"{raw_date} {start_time}", "%m/%d/%Y %I:%M %p"))
    end_dt = tz.localize(datetime.strptime(f"{raw_date} {end_time}", "%m/%d/%Y %I:%M %p"))

    return start_dt.isoformat(), end_dt.isoformat()


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

    # Build proper start/end times
    start, end = build_event_times(booking)

    event_body = {
        "summary": summary,
        "location": location,
        "description": description,
        "start": {"dateTime": start},
        "end": {"dateTime": end},
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

    # Build proper start/end times
    start, end = build_event_times(booking)

    event_body = {
        "summary": summary,
        "location": location,
        "description": description,
        "start": {"dateTime": start},
        "end": {"dateTime": end},
    }

    updated_event = service.events().update(
        calendarId=CALENDAR_ID,
        eventId=event_id,
        body=event_body
    ).execute()

    return updated_event.get("id")
