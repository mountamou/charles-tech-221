"""Regression test: create_all() never alters an existing table, so any column added
to models.py must actually reach a database that predates it — this is what broke
/api/invoices and /api/payments in production after the CinetPay fields were added.
"""
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import sessionmaker

from app.main import migrate_schema
import app.main as main_module
from app.models import Invoice, Payment


def test_migrate_schema_adds_missing_columns_to_an_existing_table(tmp_path, monkeypatch):
    db_path = tmp_path / "old.db"
    old_engine = create_engine(f"sqlite:///{db_path}")
    # Simulate the pre-CinetPay database: the invoices/payments tables without the
    # columns models.py has since gained.
    with old_engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE invoices (id INTEGER PRIMARY KEY, client_id INTEGER, "
            "project_id INTEGER, reference VARCHAR(60), description TEXT, "
            "amount FLOAT, status VARCHAR(30), issued_at DATETIME, due_at DATETIME)"
        ))
        conn.execute(text(
            "CREATE TABLE payments (id INTEGER PRIMARY KEY, invoice_id INTEGER, "
            "client_id INTEGER, method VARCHAR(30), amount FLOAT, "
            "reference VARCHAR(120), status VARCHAR(30), created_at DATETIME)"
        ))

    new_engine = create_engine(f"sqlite:///{db_path}")
    monkeypatch.setattr(main_module, "engine", new_engine)

    migrate_schema()

    insp = inspect(new_engine)
    invoice_cols = {c["name"] for c in insp.get_columns("invoices")}
    payment_cols = {c["name"] for c in insp.get_columns("payments")}
    assert "training_id" in invoice_cols
    for col in ("gateway", "gateway_transaction_id", "merchant_transaction_id", "notify_token", "paid_at"):
        assert col in payment_cols

    # The columns aren't just present — a full entity select (what /api/invoices and
    # /api/payments actually run) must succeed instead of "no such column".
    Session = sessionmaker(bind=new_engine)
    db = Session()
    assert db.scalars(select(Invoice)).all() == []
    assert db.scalars(select(Payment)).all() == []
    db.close()

    # Running it again must be a no-op (idempotent on every boot).
    migrate_schema()
