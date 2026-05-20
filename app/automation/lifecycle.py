from datetime import datetime, timedelta
import stripe
from app.services.firebase_setup import db
from app.triggers.on_balance_paid import handle_balance_paid
from app.triggers.on_payment_declined import handle_payment_declined
from app.root_schema import normalize_payload

# -----------------------------
# DATE NORMALIZATION
# -----------------------------
def normalize_date(raw):
    if not raw:
        return None

    raw = str(raw).strip()

    # Already canonical YYYY-MM-DD
    if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
        return raw

    # ISO formats
    if "T" in raw:
        return raw[:10]

    # MM/DD/YYYY
    try:
        return datetime.strptime(raw, "%m/%d/%Y").strftime("%Y-%m-%d")
    except:
        pass

    # Month DD, YYYY
    try:
        return datetime.strptime(raw, "%B %d, %Y").strftime("%Y-%m-%d")
    except:
        pass

    return raw


# -----------------------------
# FETCH + CANONICAL NORMALIZATION
# -----------------------------
def get_all_normalized_bookings():
    docs = db.collection("bookings").stream()
    normalized = []

    for doc in docs:
        raw = doc.to_dict()
        raw["id"] = doc.id

        # Canonical normalization
        clean = normalize_payload(raw)

        # Normalize date formats
        clean["date"] = normalize_date(
            clean.get("date") or
            clean.get("eventDate") or
            clean.get("partyDate") or
            clean.get("event_date")
        )

        # Normalize paymentStatus
        status = (clean.get("paymentStatus") or "").lower()
        if status in ["depositpaid", "deposit-paid", "deposit_paid"]:
            clean["paymentStatus"] = "deposit_paid"

        # Normalize saveCardForAutopay
        save = clean.get("saveCardForAutopay") or clean.get("saveCard") or clean.get("autoPay")
        clean["saveCardForAutopay"] = str(save).lower() in ["true", "1", "yes"]

        # Normalize remaining balance
        clean["remaining"] = (
            clean.get("remaining") or
            clean.get("remainingBalance") or
            clean.get("remaining_due") or
            clean.get("balanceDue")
        )

        # Normalize Stripe IDs
        clean["stripe_customer_id"] = (
            clean.get("stripe_customer_id") or
            clean.get("stripeCustomerId") or
            clean.get("stripe_customer")
        )

        clean["stripe_payment_method_id"] = (
            clean.get("stripe_payment_method_id") or
            clean.get("stripePaymentMethodId") or
            clean.get("paymentMethodId")
        )

        normalized.append(clean)

    return normalized


# -----------------------------
# FIND BOOKINGS 2 DAYS AWAY
# -----------------------------
def find_bookings_for_autopay():
    today = datetime.utcnow()
    target = (today + timedelta(days=2)).strftime("%Y-%m-%d")

    bookings = get_all_normalized_bookings()

    return [
        b for b in bookings
        if b.get("date") == target
        and b.get("paymentStatus") == "deposit_paid"
        and b.get("saveCardForAutopay") is True
        and b.get("stripe_customer_id")
        and b.get("stripe_payment_method_id")
        and float(b.get("remaining", 0)) > 0
    ]


# -----------------------------
# STRIPE CHARGE
# -----------------------------
def charge_booking(b):
    try:
        stripe.PaymentIntent.create(
            amount=int(round(float(b["remaining"]) * 100)),
            currency="usd",
            customer=b["stripe_customer_id"],
            payment_method=b["stripe_payment_method_id"],
            off_session=True,
            confirm=True,
            description=f"Autopay Final Balance - Booking {b['booking_id']}",
            metadata={"booking_id": b["booking_id"]}
        )
        return True
    except Exception as e:
        print("Autopay failed:", e)
        return False


# -----------------------------
# FIRESTORE UPDATES
# -----------------------------
def update_firestore_success(b):
    db.collection("bookings").document(b["id"]).update({
        "paymentStatus": "balance_paid"
    })
    handle_balance_paid(b)

def update_firestore_failure(b):
    handle_payment_declined(b)


# -----------------------------
# MAIN LIFECYCLE RUNNER
# -----------------------------
def run_lifecycle():
    targets = find_bookings_for_autopay()

    for b in targets:
        if charge_booking(b):
            update_firestore_success(b)
        else:
            update_firestore_failure(b)
def find_overdue_autopay_bookings():
    today = datetime.utcnow().strftime("%Y-%m-%d")
    bookings = get_all_normalized_bookings()

    overdue = []
    for b in bookings:
        date = b.get("date")
        if not date:
            continue

        # Event already passed, but balance unpaid
        if date < today and b.get("paymentStatus") == "deposit_paid":
            overdue.append(b)

    return overdue
def run_overdue_autopay():
    overdue = find_overdue_autopay_bookings()

    for b in overdue:
        if charge_booking(b):
            update_firestore_success(b)
        else:
            update_firestore_failure(b)
def find_missing_card_bookings():
    bookings = get_all_normalized_bookings()
    missing = []

    for b in bookings:
        if b.get("paymentStatus") == "deposit_paid" and not b.get("stripe_payment_method_id"):
            missing.append(b)

    return missing
def fix_old_dates():
    bookings = get_all_normalized_bookings()

    for b in bookings:
        normalized = normalize_date(b.get("date"))
        if normalized != b.get("date"):
            db.collection("bookings").document(b["id"]).update({"date": normalized})
def fix_remaining_fields():
    bookings = get_all_normalized_bookings()

    for b in bookings:
        if "remaining" not in b:
            continue

        db.collection("bookings").document(b["id"]).update({
            "remaining": float(b["remaining"])
        })
