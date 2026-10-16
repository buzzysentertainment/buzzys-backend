import asyncio
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

class FakeDocument:
    def __init__(self, data=None):
        self.data = data
        self.updates = []

    def get(self):
        return self

    def to_dict(self):
        return dict(self.data) if self.data is not None else None

    def update(self, payload):
        self.updates.append(payload)
        if self.data is not None:
            self.data.update(payload)

    def set(self, payload):
        self.data = dict(payload)


class FakeCollection:
    def __init__(self):
        self.documents = {}

    def document(self, document_id):
        return self.documents.setdefault(document_id, FakeDocument())


class FakeDatabase:
    def __init__(self):
        self.collections = {}

    def collection(self, name):
        return self.collections.setdefault(name, FakeCollection())


FAKE_DB = FakeDatabase()


class FakeBackgroundTasks:
    def __init__(self):
        self.tasks = []

    def add_task(self, function, *args, **kwargs):
        self.tasks.append((function, args, kwargs))

    async def __call__(self):
        for function, args, kwargs in self.tasks:
            function(*args, **kwargs)


def install_dependency_stubs():
    class FakeAPIRouter:
        def __init__(self, *args, **kwargs):
            pass

        def __getattr__(self, name):
            if name in {"get", "post", "put", "patch", "delete"}:
                return lambda *args, **kwargs: lambda function: function
            raise AttributeError(name)

    class FakeHTTPException(Exception):
        def __init__(self, status_code, detail):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    fastapi = types.ModuleType("fastapi")
    fastapi.APIRouter = FakeAPIRouter
    fastapi.BackgroundTasks = FakeBackgroundTasks
    fastapi.HTTPException = FakeHTTPException
    fastapi.Request = object
    sys.modules[fastapi.__name__] = fastapi

    pydantic = types.ModuleType("pydantic")
    pydantic.BaseModel = object
    sys.modules[pydantic.__name__] = pydantic

    stripe = types.ModuleType("stripe")
    stripe.Webhook = type("Webhook", (), {"construct_event": MagicMock()})
    stripe.Customer = type("Customer", (), {"create": MagicMock()})
    stripe.PaymentIntent = type("PaymentIntent", (), {"retrieve": MagicMock()})
    stripe.checkout = SimpleNamespace(
        Session=type("Session", (), {"create": MagicMock()})
    )
    sys.modules[stripe.__name__] = stripe

    svix = types.ModuleType("svix")
    svix_webhooks = types.ModuleType("svix.webhooks")
    svix_webhooks.Webhook = object
    svix_webhooks.WebhookVerificationError = Exception
    sys.modules[svix.__name__] = svix
    sys.modules[svix_webhooks.__name__] = svix_webhooks

    square = types.ModuleType("square")
    square_client = types.ModuleType("square.client")
    square_client.Client = object
    square_utilities = types.ModuleType("square.utilities")
    square_webhooks = types.ModuleType("square.utilities.webhooks_helper")
    square_webhooks.is_valid_webhook_event_signature = MagicMock()
    sys.modules[square.__name__] = square
    sys.modules[square_client.__name__] = square_client
    sys.modules[square_utilities.__name__] = square_utilities
    sys.modules[square_webhooks.__name__] = square_webhooks

    firebase = types.ModuleType("app.services.firebase_setup")
    firebase.db = FAKE_DB
    sys.modules[firebase.__name__] = firebase

    email = types.ModuleType("app.services.email_service")
    email.send_email_template = MagicMock()
    email.send_email_from_file = MagicMock()
    sys.modules[email.__name__] = email

    lifecycle = types.ModuleType("app.automation.lifecycle")
    for name in ("run_lifecycle", "run_overdue_autopay", "fix_old_dates", "fix_remaining_fields"):
        setattr(lifecycle, name, MagicMock())
    sys.modules[lifecycle.__name__] = lifecycle

    calendar = types.ModuleType("app.routers.google_calendar")
    calendar.build_event_times = MagicMock(return_value=("start", "end"))
    calendar.create_booking_event = MagicMock(return_value="calendar-event-1")
    sys.modules[calendar.__name__] = calendar

    trigger_functions = {
        "on_contract_received": "handle_contract_received",
        "on_deposit_received": "handle_deposit_received",
        "on_payment_declined": "handle_payment_declined",
        "on_balance_paid": "handle_balance_paid",
        "on_event_canceled": "handle_event_canceled",
        "on_event_reminder": "handle_event_reminder",
        "on_reengagement": "send_anniversary_reminders",
    }
    for module_name, function_name in trigger_functions.items():
        module = types.ModuleType(f"app.triggers.{module_name}")
        result = {"status": "success"} if function_name == "handle_deposit_received" else None
        setattr(module, function_name, MagicMock(return_value=result))
        sys.modules[module.__name__] = module

    invoices = types.ModuleType("app.services.stripe_invoices")
    invoices.ensure_remaining_invoice = MagicMock()
    invoices.record_invoice_failure = MagicMock()
    invoices.update_booking_from_invoice = MagicMock()
    sys.modules[invoices.__name__] = invoices


install_dependency_stubs()
from app.routers import booking  # noqa: E402


class FakeRequest:
    def __init__(self, payload=b"{}", signature="test-signature"):
        self._payload = payload
        self.headers = {"stripe-signature": signature}

    async def body(self):
        return self._payload


class StripeCheckoutFlowTests(unittest.TestCase):
    def setUp(self):
        FAKE_DB.collections.clear()
        booking.send_email_from_file.reset_mock()
        booking.handle_deposit_received.reset_mock()
        booking.build_event_times.reset_mock()
        booking.create_booking_event.reset_mock()
        booking.ensure_remaining_invoice.reset_mock()
        booking.record_invoice_failure.reset_mock()

    def test_checkout_creates_pending_booking_and_75_dollar_session(self):
        customer = SimpleNamespace(id="cus_mock")
        session = SimpleNamespace(url="https://checkout.stripe.test/session")
        payload = {
            "name": "Mock Customer",
            "email": "mock@example.com",
            "phone": "5555550100",
            "date": "2030-01-01",
            "address": "123 Test Street, Rome, GA 30161",
            "items": [{"name": "Mock Bounce House", "price": 300, "mode": "dry"}],
            "mileageFee": 10,
            "distance": 20,
        }

        with (
            patch.object(booking.uuid, "uuid4", return_value="booking-mock-1"),
            patch.object(booking.stripe.Customer, "create", return_value=customer) as create_customer,
            patch.object(booking.stripe.checkout.Session, "create", return_value=session) as create_session,
        ):
            result = asyncio.run(booking.create_checkout(payload))

        self.assertEqual(result["checkoutUrl"], session.url)
        create_customer.assert_called_once()
        session_args = create_session.call_args.kwargs
        self.assertEqual(session_args["line_items"][0]["price_data"]["unit_amount"], 7500)
        self.assertEqual(session_args["metadata"]["booking_id"], "booking-mock-1")
        self.assertIn("booking-mock-1", session_args["success_url"])

        saved = FAKE_DB.collection("bookings").document("booking-mock-1").data
        self.assertEqual(saved["paymentStatus"], "pending")
        self.assertEqual(saved["stripe_customer_id"], "cus_mock")
        self.assertEqual(saved["deposit"], 75.0)
        booking.send_email_from_file.assert_called_once()

    def test_completed_checkout_acknowledges_then_creates_invoice(self):
        booking_doc = FAKE_DB.collection("bookings").document("booking-mock-2")
        booking_doc.data = {
            "booking_id": "booking-mock-2",
            "date": "2030-01-01",
            "remaining": 246.70,
            "stripe_customer_id": "cus_mock",
            "deposit_confirmation_sent": False,
        }
        session = MagicMock()
        session.to_dict.return_value = {
            "metadata": {"booking_id": "booking-mock-2"},
            "customer": "cus_mock",
            "payment_intent": "pi_mock",
        }
        event = {
            "id": "evt_mock_completed",
            "type": "checkout.session.completed",
            "data": {"object": session},
        }
        intent = SimpleNamespace(id="pi_mock", payment_method="pm_mock")
        booking.ensure_remaining_invoice.return_value = {
            "status": "open",
            "amount": 246.70,
            "invoice_id": "in_mock",
            "hosted_invoice_url": "https://invoice.stripe.test/in_mock",
        }
        background_tasks = FakeBackgroundTasks()

        with (
            patch.object(booking.stripe.Webhook, "construct_event", return_value=event),
            patch.object(booking.stripe.PaymentIntent, "retrieve", return_value=intent),
        ):
            response = asyncio.run(booking.stripe_webhook(FakeRequest(), background_tasks))
            self.assertEqual(response, {"status": "ok"})
            booking.ensure_remaining_invoice.assert_not_called()
            asyncio.run(background_tasks())

        booking.ensure_remaining_invoice.assert_called_once()
        processed_booking = booking.ensure_remaining_invoice.call_args.args[0]
        self.assertEqual(processed_booking["paymentStatus"], "deposit_paid")
        self.assertEqual(processed_booking["stripe_payment_method_id"], "pm_mock")
        self.assertEqual(processed_booking["stripe_payment_intent"], "pi_mock")
        booking.handle_deposit_received.assert_called_once()
        booking.create_booking_event.assert_called_once()
        self.assertTrue(
            any(update.get("deposit_confirmation_sent") is True for update in booking_doc.updates)
        )


if __name__ == "__main__":
    unittest.main()
