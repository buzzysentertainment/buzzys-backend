import os
from datetime import datetime, timedelta
from app.firebase_config import db
from app.services.email_service import send_email_template

def send_anniversary_reminders():
    # 1. Calculate the "Lookback" dates
    # We check for people who booked exactly 6 months ago AND 12 months ago
    six_months_ago = (datetime.utcnow() - timedelta(days=182)).strftime("%Y-%m-%d")
    one_year_ago = (datetime.utcnow() - timedelta(days=365)).strftime("%Y-%m-%d")
    
    target_dates = [six_months_ago, one_year_ago]
    sent_count = 0

    for date in target_dates:
        # 2. Query for completed bookings on those specific past dates
        docs = (
            db.collection("bookings")
            .where("date", "==", date)
            .where("status", "==", "completed") # Only repeat to happy past customers
            .stream()
        )

        for doc in docs:
            booking = doc.to_dict()
            
            # 3. Send the "Bee's Knees" fun email
            send_email_template(
                to=booking["email"],
                template_id=os.getenv("RESEND_REENGAGEMENT_TEMPLATE"),
                data={
                    "name": booking["name"],
                    "fun_message": "Got another event you'd like to be the 'bee's knees'? We've got you covered!"
                }
            )
            sent_count += 1

    return {"status": "success", "reengagements_sent": sent_count}