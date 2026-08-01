import os
from datetime import datetime, timedelta, timezone

import stripe
from google.cloud import firestore

from app.services.firebase_setup import db


DEPOSIT_AMOUNT = 75.00
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")


def authoritative_remaining_balance(booking: dict) -> float:
    """Return the contractual total less the fixed, paid deposit."""
    pricing = booking.get("pricing_breakdown") or {}
    total = pricing.get("total")
    if total is None:
        total = booking.get("total")

    if total is not None:
        return round(max(0, float(total) - DEPOSIT_AMOUNT), 2)

    # Historical records may only have a saved remaining balance.
    return round(max(0, float(booking.get("remaining") or 0)), 2)


def invoice_due_timestamp(event_date_text: str) -> int:
    """Set the due date two days before the event without using a past time."""
    event_date = datetime.strptime(event_date_text, "%Y-%m-%d").date()
    desired_date = event_date - timedelta(days=2)
    desired_due = datetime.combine(
        desired_date,
        datetime.max.time().replace(microsecond=0),
        tzinfo=timezone.utc,
    )
    now = datetime.now(timezone.utc)

    # Stripe requires a future due_date. Last-minute bookings are due shortly
    # after the invoice is issued instead of failing invoice creation.
    if desired_due <= now:
        desired_due = now + timedelta(hours=1)

    return int(desired_due.timestamp())


def ensure_remaining_invoice(booking: dict, doc_ref=None) -> dict:
    """Idempotently create, send, and persist a booking's Stripe invoice."""
    booking_id = booking.get("booking_id") or booking.get("id")
    customer_id = booking.get("stripe_customer_id")
    event_date = booking.get("date") or booking.get("eventDate")
    remaining = authoritative_remaining_balance(booking)

    if not booking_id:
        raise ValueError("Booking is missing booking_id")
    if not customer_id:
        raise ValueError("Booking is missing stripe_customer_id")
    if not event_date:
        raise ValueError("Booking is missing event date")
    if remaining <= 0:
        return {"status": "not_required", "amount": remaining}

    doc_ref = doc_ref or db.collection("bookings").document(booking_id)
    invoice_id = booking.get("stripe_remaining_invoice_id")

    if invoice_id:
        invoice = stripe.Invoice.retrieve(invoice_id)
    else:
        stripe.InvoiceItem.create(
            customer=customer_id,
            amount=int(round(remaining * 100)),
            currency="usd",
            description=f"Remaining Balance for Inflatable Rental on {event_date}",
            metadata={"booking_id": booking_id, "payment_type": "remaining_balance"},
            idempotency_key=f"booking-{booking_id}-remaining-item",
        )
        invoice = stripe.Invoice.create(
            customer=customer_id,
            collection_method="send_invoice",
            due_date=invoice_due_timestamp(event_date),
            description=f"Remaining balance after ${DEPOSIT_AMOUNT:.2f} deposit",
            footer="Your $75 deposit has been applied. Thank you for booking with us!",
            metadata={"booking_id": booking_id, "payment_type": "remaining_balance"},
            idempotency_key=f"booking-{booking_id}-remaining-invoice",
        )
        invoice_id = invoice.id
        doc_ref.update({
            "remaining": remaining,
            "stripe_remaining_invoice_id": invoice_id,
            "stripe_invoice_amount": remaining,
            "stripe_invoice_status": invoice.status,
            "stripe_invoice_created_at": firestore.SERVER_TIMESTAMP,
            "stripe_invoice_error": firestore.DELETE_FIELD,
        })

    if invoice.status == "paid":
        doc_ref.update({
            "paymentStatus": "balance_paid",
            "stripe_invoice_status": "paid",
            "remainingBalance": 0,
        })
        return {"status": "paid", "invoice_id": invoice.id, "amount": remaining}

    if invoice.status == "draft":
        invoice = stripe.Invoice.send_invoice(
            invoice.id,
            idempotency_key=f"booking-{booking_id}-send-remaining-invoice",
        )

    doc_ref.update({
        "stripe_remaining_invoice_id": invoice.id,
        "stripe_hosted_invoice_url": invoice.hosted_invoice_url,
        "stripe_invoice_pdf": invoice.invoice_pdf,
        "stripe_invoice_amount": remaining,
        "stripe_invoice_status": invoice.status,
        "stripe_invoice_sent_at": firestore.SERVER_TIMESTAMP,
        "stripe_invoice_error": firestore.DELETE_FIELD,
    })
    return {
        "status": invoice.status,
        "invoice_id": invoice.id,
        "hosted_invoice_url": invoice.hosted_invoice_url,
        "amount": remaining,
    }


def record_invoice_failure(booking_id: str, error: Exception):
    db.collection("bookings").document(booking_id).update({
        "stripe_invoice_status": "failed",
        "stripe_invoice_error": str(error)[:1000],
        "stripe_invoice_last_attempt_at": firestore.SERVER_TIMESTAMP,
    })


def update_booking_from_invoice(invoice, payment_status: str):
    metadata = invoice.get("metadata") or {}
    booking_id = metadata.get("booking_id")
    if not booking_id:
        return None

    updates = {
        "stripe_remaining_invoice_id": invoice.get("id"),
        "stripe_invoice_status": invoice.get("status") or payment_status,
        "stripe_invoice_updated_at": firestore.SERVER_TIMESTAMP,
    }
    if payment_status == "balance_paid":
        updates.update({
            "paymentStatus": "balance_paid",
            "remainingBalance": 0,
            "stripe_invoice_paid_at": firestore.SERVER_TIMESTAMP,
        })
    elif payment_status == "payment_failed":
        updates.update({
            "paymentStatus": "deposit_paid",
            "stripe_invoice_failed_at": firestore.SERVER_TIMESTAMP,
        })

    doc_ref = db.collection("bookings").document(booking_id)
    doc_ref.update(updates)
    booking = doc_ref.get().to_dict() or {}
    booking["id"] = booking_id
    return booking
