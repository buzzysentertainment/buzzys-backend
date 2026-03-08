from app.services.email_service import send_email_from_file

def handle_contract_received(booking: dict):
    # Build item list for the template
    items_raw = booking.get("items", [])
    item_names = [
        i.get("title") or i.get("name") or "Party Gear"
        for i in items_raw if isinstance(i, dict)
    ]
    display_items = ", ".join(item_names) if item_names else "Party Gear"

    # Data for the booking_confirmation.html template
    email_data = {
        "name": booking.get("name"),
        "date": booking.get("date"),
        "deliveryTime": booking.get("deliveryTime"),
        "pickupTime": booking.get("pickupTime"),
        "address": booking.get("address"),
        "total": booking.get("total"),
        "deposit": booking.get("deposit"),
        "remaining": booking.get("remaining"),
        "items": display_items
    }

    return send_email_from_file(
        to=[booking.get("email")],
        template_name="booking_confirmation.html",
        subject="Your Booking Is Confirmed!",
        params=email_data
    )
