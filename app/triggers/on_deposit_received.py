from app.services.email_service import send_email_from_file, generate_ics_content
from app.services.firebase_setup import db

def handle_deposit_received(booking: dict):
    # The Stripe webhook creates the balance invoice before this confirmation.
    remaining_val = booking.get("remaining", 0)
    pay_link = booking.get("stripe_hosted_invoice_url") or "https://www.buzzys.org/pay"

    # --- 3. PREPARE ITEM LIST ---
    items_raw = booking.get("items", [])
    item_names = [
        i.get("title") or i.get("name") or "Party Gear"
        for i in items_raw if isinstance(i, dict)
    ]
    display_items = ", ".join(item_names) if item_names else "Party Gear"

    # --- 4. PREPARE EMAIL DATA ---
    ics_content = generate_ics_content(booking)

    total_val = (
        booking.get("pricing_breakdown", {}).get("total")
        or booking.get("total", 0)
    )

    email_data = {
        "customer_name": booking.get("name"),
        "event_date": booking.get("date"),
        "total_amount": f"{float(total_val):.2f}",
        "deposit_amount": f"{float(booking.get('deposit', 0)):.2f}",
        "remaining_amount": f"{float(remaining_val):.2f}",
        "booking_id": booking.get("booking_id"),
        "items": display_items,
        "pay_link": pay_link
    }

    attachments = [{
        "content": ics_content,
        "filename": "event-reminder.ics"
    }]

    # --- 5. SEND EMAIL USING FILE TEMPLATE ---
    email_res = send_email_from_file(
        to=[booking.get("email")],
        template_name="deposit_received.html",
        subject="Your Booking Is Confirmed!",
        params=email_data
    )

    # --- 6. SAVE EMAIL ID FOR RESEND WEBHOOK ---
    email_id = email_res.get("id")
    if email_id:
        db.collection("bookings").document(booking["booking_id"]).update({
            "last_email_id": email_id,
            "emailStatus": "Sent"
        })

    return email_res
