import os
from datetime import datetime, timedelta
from app.firebase_config import db
from app.services.email_service import send_email_template

def process_upcoming_balances():
    # 1. Target date is 2 days from now
    target_date = (datetime.utcnow() + timedelta(days=2)).strftime("%Y-%m-%d")
    
    # 2. Find active bookings with only a deposit paid for that date
    docs = (
        db.collection("bookings")
        .where("date", "==", target_date)
        .where("status", "==", "active")
        .where("paymentStatus", "==", "deposit_paid") 
        .stream()
    )

    sent_list = []
    for doc in docs:
        booking = doc.to_dict()
        pay_link = booking.get("invoice_url") or "https://www.buzzys.org/pay"
        
        send_email_template(
            to=booking["email"],
            template_id=os.getenv("RESEND_BALANCE_DUE_REMINDER_TEMPLATE"),
            data={
                "name": booking["name"],
                "remaining": f"${float(booking['remaining']):.2f}",
                "pay_link": pay_link,
                "date": booking["date"]
            }
        )
        sent_list.append(doc.id)

    return {"status": "success", "date_processed": target_date, "count": len(sent_list)}