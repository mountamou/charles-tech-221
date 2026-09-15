"""CinetPay online payments: initialize a checkout, confirm it from the webhook.

The webhook body never carries the real transaction status — it is only a signal to
go check. Every confirmation goes through `client.payment.get_status(...)`, the only
source of truth, after verifying the notify_token CinetPay handed back at
initialization (timing-safe comparison, never trust the token without it).
"""
from datetime import datetime

from cinetpay import (
    CinetPayClient,
    ClientConfig,
    CountryCredentials,
    PaymentRequest,
    parse_notification,
    verify_notification,
)

from sqlalchemy import select

from .config import settings
from .models import Enrollment, Invoice, Payment

MIN_AMOUNT = 100
MAX_AMOUNT = 2_500_000

_client: CinetPayClient | None = None
_client_built = False


def get_client() -> CinetPayClient | None:
    """Lazily build the CinetPay client, or return None when it isn't configured."""
    global _client, _client_built
    if not _client_built:
        _client_built = True
        if settings.cinetpay_api_key and settings.cinetpay_api_password:
            _client = CinetPayClient(ClientConfig(credentials={
                settings.cinetpay_country: CountryCredentials(
                    api_key=settings.cinetpay_api_key,
                    api_password=settings.cinetpay_api_password,
                ),
            }))
    return _client


class CinetPayUnavailable(Exception):
    pass


class AmountOutOfRange(Exception):
    def __init__(self, amount: float):
        super().__init__(
            f"Le paiement en ligne n'accepte que les montants entre {MIN_AMOUNT} et "
            f"{MAX_AMOUNT} FCFA. Utilisez la déclaration manuelle pour {amount:,.0f} FCFA."
            .replace(",", " ")
        )


def start_payment(db, payment: Payment, invoice: Invoice, client_user) -> str:
    """Initialize a CinetPay checkout for `payment`/`invoice`, return the redirect URL."""
    cp = get_client()
    if cp is None:
        raise CinetPayUnavailable("Le paiement en ligne n'est pas configuré.")
    amount = int(round(invoice.amount))
    if not (MIN_AMOUNT <= amount <= MAX_AMOUNT):
        raise AmountOutOfRange(invoice.amount)

    merchant_transaction_id = f"CTP-{payment.id}"
    name_parts = (client_user.name or "Client").strip().split(" ", 1)
    first_name = name_parts[0] or "Client"
    last_name = name_parts[1] if len(name_parts) > 1 else first_name

    resp = cp.payment.initialize(
        PaymentRequest(
            currency="XOF",
            merchant_transaction_id=merchant_transaction_id,
            amount=amount,
            lang="fr",
            designation=invoice.description[:250] or "Charles Tech 221",
            client_email=client_user.email,
            client_first_name=first_name,
            client_last_name=last_name,
            success_url=f"{settings.public_base_url}/portal?payment=success",
            failed_url=f"{settings.public_base_url}/portal?payment=failed",
            notify_url=f"{settings.public_base_url}/api/payments/cinetpay/webhook",
            channel="PUSH",
        ),
        settings.cinetpay_country,
    )

    payment.gateway = "cinetpay"
    payment.merchant_transaction_id = merchant_transaction_id
    payment.gateway_transaction_id = resp.transaction_id
    payment.notify_token = resp.notify_token
    db.commit()
    return resp.payment_url


def confirm_from_webhook(db, raw_body: dict, log, notify) -> None:
    """Handle one CinetPay webhook call: verify, re-check status, apply if final."""
    try:
        payload = parse_notification(raw_body)
    except (TypeError, ValueError):
        return

    payment = db.scalar(select(Payment).where(Payment.merchant_transaction_id == payload.merchant_transaction_id))
    if not payment:
        return
    if not verify_notification(payment.notify_token, payload.notify_token):
        log(db, None, "cinetpay_webhook_invalid_token", payload.merchant_transaction_id)
        return
    if payment.status != "En attente":
        return  # already processed — CinetPay may call the webhook more than once

    cp = get_client()
    if cp is None:
        return
    status = cp.payment.get_status(payment.merchant_transaction_id, settings.cinetpay_country)

    invoice = db.get(Invoice, payment.invoice_id)
    if status.status == "SUCCESS":
        payment.status = "Validé"
        payment.paid_at = datetime.utcnow()
        if invoice:
            invoice.status = "Payée"
            if invoice.training_id and not db.scalar(select(Enrollment).where(
                Enrollment.user_id == invoice.client_id,
                Enrollment.training_id == invoice.training_id,
            )):
                db.add(Enrollment(user_id=invoice.client_id, training_id=invoice.training_id))
        db.commit()
        notify(db, payment.client_id, "Paiement confirmé", f"Votre paiement de {payment.amount:,.0f} {settings.currency} a été validé.".replace(",", " "))
        log(db, None, "cinetpay_payment_success", payment.merchant_transaction_id)
    elif status.status in ("FAILED", "EXPIRED"):
        payment.status = "Refusé"
        db.commit()
        notify(db, payment.client_id, "Paiement échoué", "Votre paiement n'a pas abouti. Vous pouvez réessayer ou déclarer un paiement manuel.")
        log(db, None, "cinetpay_payment_failed", payment.merchant_transaction_id)
    # Any other status (PENDING, INITIATED...) is not final yet — leave the payment as is.
