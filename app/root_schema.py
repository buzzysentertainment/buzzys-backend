# root_schema.py

import re
from datetime import datetime

# ---------------------------------------------------------
# ROOT SCHEMA (your full dictionary)
# ---------------------------------------------------------

ROOT = {
    "canonical": {
        "customer": {
            "name": {
                "type": "string",
                "required": True,
                "aliases": [
                    "customerName", "fullName", "name", "customer_name",
                    "buyer_name", "clientName"
                ],
                "description": "Full name of the customer placing the booking."
            },
            "email": {
                "type": "string",
                "required": True,
                "aliases": [
                    "customerEmail", "emailAddress", "email", "buyer_email",
                    "contactEmail"
                ],
                "description": "Customer email used for receipts and confirmations."
            },
            "phone": {
                "type": "string",
                "required": True,
                "aliases": [
                    "phoneNumber", "customerPhone", "contactPhone", "phone"
                ],
                "description": "Customer phone number for delivery coordination."
            },
            "address": {
                "type": "string",
                "required": True,
                "aliases": [
                    "deliveryAddress", "eventAddress", "address", "location",
                    "streetAddress"
                ],
                "description": "Delivery address for the event."
            }
        },

        "event": {
            "date": {
                "type": "string (YYYY-MM-DD)",
                "required": True,
                "aliases": [
                    "eventDate", "bookingDate", "selectedDate", "date",
                    "partyDate", "reservationDate"
                ],
                "description": "The date of the event."
            },
            "deliveryTime": {
                "type": "string",
                "required": False,
                "aliases": [
                    "dropoffTime", "startTime", "delivery_time", "delivery",
                    "setupTime"
                ],
                "description": "Time equipment should be delivered/set up."
            },
            "pickupTime": {
                "type": "string",
                "required": False,
                "aliases": [
                    "pickup_time", "endTime", "tearDownTime", "pickup"
                ],
                "description": "Time equipment should be picked up."
            },
            "overnight": {
                "type": "boolean",
                "required": False,
                "aliases": [
                    "overnightRental", "overnightStay", "overnight_flag",
                    "isOvernight"
                ],
                "description": "Whether the rental is kept overnight."
            }
        },

        "cart": {
            "items": {
                "type": "list",
                "required": True,
                "aliases": [
                    "cart", "cartItems", "selectedItems", "items",
                    "bookingItems", "orderItems"
                ],
                "description": "List of items the customer is booking."
            },
            "subtotal": {
                "type": "number",
                "required": True,
                "aliases": [
                    "totalBeforeDeposit", "baseTotal", "subtotal", "preDepositTotal"
                ],
                "description": "Total cost before deposit and fees."
            },
            "deposit": {
                "type": "number",
                "required": True,
                "aliases": [
                    "downPayment", "initialPayment", "depositAmount", "deposit"
                ],
                "description": "Deposit amount required to reserve the booking."
            },
            "remaining": {
                "type": "number",
                "required": True,
                "aliases": [
                    "remainingBalance", "balanceDue", "dueAtDelivery", "remaining"
                ],
                "description": "Remaining balance after deposit."
            },
            "waiverFee": {
                "type": "number",
                "required": False,
                "aliases": [
                    "damageWaiver", "insuranceFee", "waiver_fee", "waiverFee"
                ],
                "description": "Optional damage waiver fee."
            }
        },

        "square": {
            "checkout_url": {
                "type": "string",
                "required": false,
                "aliases": [
                    "checkoutUrl", "paymentLink", "squareCheckoutUrl",
                    "checkout_url"
                ],
                "description": "Square checkout link for deposit payment."
            },
            "transaction_id": {
                "type": "string",
                "required": False,
                "aliases": [
                    "transactionId", "squareTransactionId", "paymentId",
                    "txn_id"
                ],
                "description": "Square transaction ID returned after payment."
            },
            "order_id": {
                "type": "string",
                "required": False,
                "aliases": [
                    "orderId", "squareOrderId", "sq_order_id"
                ],
                "description": "Square order ID associated with the checkout."
            }
        },

        "calendar": {
            "event_id": {
                "type": "string",
                "required": False,
                "aliases": [
                    "googleEventId", "calendarEventId", "eventId"
                ],
                "description": "Google Calendar event ID created for the booking."
            }
        },

        "status": {
            "status": {
                "type": "string",
                "required": false,
                "aliases": [
                    "bookingStatus", "state", "reservationStatus", "status"
                ],
                "description": "Current status of the booking."
            },
            "note": {
                "type": "string",
                "required": False,
                "aliases": [
                    "adminNote", "internalNote", "note", "comments"
                ],
                "description": "Admin notes about the booking."
            }
        }
    },

    "normalization": {
        "date": [
            "convert Date object → YYYY-MM-DD",
            "replace '/' with '-'",
            "strip time if included",
            "validate format"
        ],
        "phone": [
            "remove spaces",
            "remove parentheses",
            "remove dashes",
            "ensure 10 digits"
        ],
        "name": [
            "strip leading/trailing spaces",
            "capitalize each word"
        ]
    },

    "outbound": {
        "firestore": {
            "name": "customerName",
            "email": "customerEmail",
            "phone": "customerPhone",
            "address": "address",
            "date": "date",
            "deliveryTime": "deliveryTime",
            "pickupTime": "pickupTime",
            "overnight": "overnight",
            "items": "items",
            "subtotal": "subtotal",
            "deposit": "deposit",
            "remaining": "remaining",
            "waiverFee": "waiverFee",
            "checkout_url": "checkoutUrl",
            "transaction_id": "transactionId",
            "order_id": "orderId",
            "event_id": "calendarEventId",
            "status": "status",
            "note": "note"
        },

        "square_metadata": {
            "event_date": "date",
            "customer_name": "name",
            "customer_email": "email",
            "cart_items": "items"
        },

        "resend": {
            "admin_checkout_started": [
                "name", "email", "phone", "date", "deliveryTime",
                "pickupTime", "overnight", "address", "subtotal",
                "deposit", "remaining", "waiverFee", "items",
                "checkout_url"
            ]
        },

        "calendar": {
            "summary": "Buzzy's Party: {name}",
            "description": "Remaining balance: ${remaining}",
            "location": "address",
            "start": "date + deliveryTime",
            "end": "date + pickupTime"
        }
    }
}

# ---------------------------------------------------------
# Normalization helper
# ---------------------------------------------------------

def apply_normalization_rules(field: str, value):
    if value is None:
        return None

    rules = ROOT.get("normalization", {})

    if field == "date":
        v = str(value).replace("/", "-")
        if "T" in v:
            v = v.split("T")[0]
        return v

    if field == "phone":
        return re.sub(r"[^\d]", "", str(value))

    if field == "name":
        v = str(value).strip()
        return " ".join(w.capitalize() for w in v.split())

    return value

# ---------------------------------------------------------
# normalize_payload
# ---------------------------------------------------------

def normalize_payload(data: dict) -> dict:
    canonical = {}

    for group, fields in ROOT["canonical"].items():
        for field, rules in fields.items():
            found = None
            for alias in rules["aliases"]:
                if alias in data:
                    found = data[alias]
                    break
            canonical[field] = apply_normalization_rules(field, found)

    return canonical

# ---------------------------------------------------------
# validate_payload
# ---------------------------------------------------------

def validate_payload(canonical: dict):
    missing = []

    for group, fields in ROOT["canonical"].items():
        for field, rules in fields.items():
            if rules.get("required") and not canonical.get(field):
                missing.append(field)

    return (len(missing) == 0, missing)

# ---------------------------------------------------------
# build_square_metadata
# ---------------------------------------------------------

def build_square_metadata(canonical: dict) -> dict:
    mapping = ROOT["outbound"]["square_metadata"]
    return {meta_key: canonical.get(canonical_key) for meta_key, canonical_key in mapping.items()}

# ---------------------------------------------------------
# build_resend_params
# ---------------------------------------------------------

def build_resend_params(canonical: dict, template_key: str) -> dict:
    fields = ROOT["outbound"]["resend"].get(template_key, [])
    return {field: canonical.get(field) for field in fields}

# ---------------------------------------------------------
# build_calendar_payload
# ---------------------------------------------------------

def build_calendar_payload(canonical: dict) -> dict:
    mapping = ROOT["outbound"]["calendar"]

    def resolve(expr: str):
        if "+ " in expr:
            left, right = expr.split("+")
            left = left.strip()
            right = right.strip()
            base = canonical.get(left)
            extra = canonical.get(right)
            if base and extra:
                return f"{base}T{extra}"
            return base or extra
        return canonical.get(expr)

    return {
        "summary": mapping["summary"].format(**canonical),
        "description": mapping["description"].format(**canonical),
        "location": canonical.get(mapping["location"]),
        "start": resolve(mapping["start"]),
        "end": resolve(mapping["end"]),
    }

# ---------------------------------------------------------
# build_firestore_doc (placeholder)
# ---------------------------------------------------------

def build_firestore_doc(canonical: dict) -> dict:
    return canonical
