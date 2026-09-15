"""CinetPay integration: initialization, webhook confirmation, training access.

The real CinetPay SDK is never called — `cinetpay.get_client` is monkeypatched to a
fake client so these tests run with no network access.
"""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app, log, notify
from app import cinetpay
from app.database import SessionLocal
from app.models import Invoice, Payment, Training, TrainingFile, User

client = TestClient(app)


def register_client():
    email = f"test-{uuid.uuid4().hex[:10]}@example.com"
    r = client.post("/api/auth/register", json={"name": "Test Client", "email": email, "password": "TestPass123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"], r.json()["user"]["id"]


def make_invoice(db, client_id, amount, training_id=None):
    inv = Invoice(client_id=client_id, training_id=training_id, reference=f"CT221-TEST-{uuid.uuid4().hex[:8]}",
                  description="Test", amount=amount)
    db.add(inv); db.commit(); db.refresh(inv)
    return inv


def make_payment(db, invoice):
    p = Payment(invoice_id=invoice.id, client_id=invoice.client_id, method="CinetPay",
                amount=invoice.amount, status="En attente")
    db.add(p); db.commit(); db.refresh(p)
    return p


class FakeStatus:
    def __init__(self, status):
        self.status = status


class FakePaymentResponse:
    def __init__(self, transaction_id, notify_token):
        self.payment_url = "https://checkout.cinetpay.com/fake"
        self.transaction_id = transaction_id
        self.notify_token = notify_token


class FakePaymentAPI:
    def __init__(self, transaction_id="TX", notify_token="TOK", status="SUCCESS"):
        self._transaction_id = transaction_id
        self._notify_token = notify_token
        self._status = status

    def initialize(self, request, country):
        return FakePaymentResponse(self._transaction_id, self._notify_token)

    def get_status(self, merchant_transaction_id, country):
        return FakeStatus(self._status)


class FakeClient:
    def __init__(self, **kwargs):
        self.payment = FakePaymentAPI(**kwargs)


def test_start_payment_rejects_out_of_range_amount(monkeypatch):
    monkeypatch.setattr(cinetpay, "get_client", lambda: FakeClient())
    token, uid = register_client()
    db = SessionLocal()
    inv = make_invoice(db, uid, 50)  # below MIN_AMOUNT
    payment = make_payment(db, inv)
    user = db.get(User, uid)
    with pytest.raises(cinetpay.AmountOutOfRange):
        cinetpay.start_payment(db, payment, inv, user)
    db.close()


def test_webhook_confirms_success_and_is_idempotent(monkeypatch):
    monkeypatch.setattr(cinetpay, "get_client", lambda: FakeClient(transaction_id="TX-A", notify_token="TOK-A", status="SUCCESS"))
    token, uid = register_client()
    db = SessionLocal()
    inv = make_invoice(db, uid, 1000)
    payment = make_payment(db, inv)
    user = db.get(User, uid)

    url = cinetpay.start_payment(db, payment, inv, user)
    assert url == "https://checkout.cinetpay.com/fake"
    assert payment.merchant_transaction_id == f"CTP-{payment.id}"

    body = {"notify_token": "TOK-A", "merchant_transaction_id": payment.merchant_transaction_id, "transaction_id": "TX-A"}
    cinetpay.confirm_from_webhook(db, body, log, notify)
    db.refresh(payment); db.refresh(inv)
    assert payment.status == "Validé"
    assert inv.status == "Payée"

    # A second call for the same (already processed) payment must not flip it to FAILED
    # even if a fresh status check would say so — idempotency guards on payment.status first.
    monkeypatch.setattr(cinetpay, "get_client", lambda: FakeClient(status="FAILED"))
    cinetpay.confirm_from_webhook(db, body, log, notify)
    db.refresh(payment)
    assert payment.status == "Validé"
    db.close()


def test_webhook_rejects_invalid_token(monkeypatch):
    monkeypatch.setattr(cinetpay, "get_client", lambda: FakeClient(transaction_id="TX-B", notify_token="REAL", status="SUCCESS"))
    token, uid = register_client()
    db = SessionLocal()
    inv = make_invoice(db, uid, 1000)
    payment = make_payment(db, inv)
    user = db.get(User, uid)
    cinetpay.start_payment(db, payment, inv, user)

    bad_body = {"notify_token": "WRONG", "merchant_transaction_id": payment.merchant_transaction_id, "transaction_id": "TX-B"}
    cinetpay.confirm_from_webhook(db, bad_body, log, notify)
    db.refresh(payment)
    assert payment.status == "En attente"
    db.close()


def test_training_purchase_creates_enrollment_on_success(monkeypatch):
    monkeypatch.setattr(cinetpay, "get_client", lambda: FakeClient(transaction_id="TX-C", notify_token="TOK-C", status="SUCCESS"))
    token, uid = register_client()
    db = SessionLocal()
    tr = Training(title="Formation payante test", description="d", price=20000)
    db.add(tr); db.commit(); db.refresh(tr)
    training_id = tr.id
    db.close()

    headers = {"Authorization": f"Bearer {token}"}
    r = client.post(f"/api/trainings/{training_id}/pay", headers=headers)
    assert r.status_code == 200, r.text
    payment_url = r.json()["payment_url"]
    assert payment_url == "https://checkout.cinetpay.com/fake"

    db = SessionLocal()
    payment = db.scalar(select(Payment).where(Payment.client_id == uid))
    body = {"notify_token": "TOK-C", "merchant_transaction_id": payment.merchant_transaction_id, "transaction_id": "TX-C"}
    cinetpay.confirm_from_webhook(db, body, log, notify)
    db.close()

    r = client.get(f"/api/trainings/{training_id}/files", headers=headers)
    assert r.status_code == 200  # access granted: the Enrollment was created by the webhook


def test_training_files_require_enrollment():
    token, uid = register_client()
    db = SessionLocal()
    tr = Training(title="Formation gratuite test", description="d", price=0)
    db.add(tr); db.commit(); db.refresh(tr)
    training_id = tr.id
    tf = TrainingFile(training_id=training_id, kind="video", label="Intro", video_url="https://youtu.be/x")
    db.add(tf); db.commit()
    db.close()

    headers = {"Authorization": f"Bearer {token}"}
    r = client.get(f"/api/trainings/{training_id}/files", headers=headers)
    assert r.status_code == 403

    r = client.post("/api/enrollments", json={"training_id": training_id}, headers=headers)
    assert r.status_code == 200

    r = client.get(f"/api/trainings/{training_id}/files", headers=headers)
    assert r.status_code == 200
    assert r.json()[0]["video_url"] == "https://youtu.be/x"
