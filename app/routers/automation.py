from fastapi import APIRouter
from datetime import datetime, timedelta
from app.services.firebase_setup import db
from app.triggers.on_review_request import handle_review_request

router = APIRouter(prefix="/automation", tags=["automation"])


@router.get("/run-daily")
def run_daily_automations():
    """
    DAILY AUTOMATION RUNNER
    -----------------------
    This endpoint is meant to be triggered once per day by a cron job.

    It handles:
    - Review Request emails (for events completed yesterday)
    """

    today = datetime.utcnow().date()
    yesterday = today - timedelta(days=1)
    yesterday_str = yesterday.strftime("%m/%d/%Y")

    # Query bookings completed yesterday
    query = (
        db.collection("bookings")
        .where("status", "==", "completed")
        .where("date", "==", yesterday_str)
        .stream()
    )

    processed = 0

    for doc in query:
        booking = doc.to_dict()

        # Skip if already sent
        if booking.get("reviewRequested") is True:
            continue

        # Send review request email
        handle_review_request(booking)

        # Mark as sent
        doc.reference.update({"reviewRequested": True})

        processed += 1

    return {
        "status": "success",
        "reviewRequestsSent": processed,
        "dateProcessed": yesterday_str
    }
