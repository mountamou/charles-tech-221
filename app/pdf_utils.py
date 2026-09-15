from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from .config import settings

def invoice_pdf(invoice, client):
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    c.setFont("Helvetica-Bold", 20)
    c.drawString(20*mm, h-25*mm, settings.company_name)
    c.setFont("Helvetica", 10)
    c.drawString(20*mm, h-32*mm, settings.company_address)
    c.drawString(20*mm, h-38*mm, f"Tél: {settings.contact_phone}")
    c.drawString(20*mm, h-44*mm, settings.contact_email)

    c.setFont("Helvetica-Bold", 18)
    c.drawRightString(w-20*mm, h-25*mm, "FACTURE")
    c.setFont("Helvetica", 10)
    c.drawRightString(w-20*mm, h-32*mm, f"Référence: {invoice.reference}")
    c.drawRightString(w-20*mm, h-38*mm, f"Statut: {invoice.status}")

    y = h-70*mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(20*mm, y, "Client")
    c.setFont("Helvetica", 10)
    c.drawString(20*mm, y-6*mm, client.name)
    c.drawString(20*mm, y-12*mm, client.email)
    if client.phone:
        c.drawString(20*mm, y-18*mm, client.phone)

    y -= 36*mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(20*mm, y, "Description")
    c.setFont("Helvetica", 10)
    text = c.beginText(20*mm, y-7*mm)
    text.textLines(invoice.description[:800])
    c.drawText(text)

    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(w-20*mm, 55*mm, f"TOTAL: {invoice.amount:,.0f} {settings.currency}".replace(",", " "))
    c.setFont("Helvetica", 9)
    c.drawString(20*mm, 30*mm, "Merci pour votre confiance.")
    c.drawString(20*mm, 24*mm, "Charles Tech 221 — Code. Crée. Innove. Réussi.")
    c.save()
    buf.seek(0)
    return buf

def payment_receipt_pdf(payment, invoice, client):
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    c.setFont("Helvetica-Bold", 20)
    c.drawString(20*mm, h-25*mm, settings.company_name)
    c.setFont("Helvetica", 10)
    c.drawString(20*mm, h-32*mm, settings.company_address)
    c.drawString(20*mm, h-38*mm, f"Tél: {settings.contact_phone}")
    c.drawString(20*mm, h-44*mm, settings.contact_email)

    c.setFont("Helvetica-Bold", 18)
    c.drawRightString(w-20*mm, h-25*mm, "REÇU DE PAIEMENT")
    c.setFont("Helvetica", 10)
    c.drawRightString(w-20*mm, h-32*mm, f"Facture: {invoice.reference}")
    paid_at = payment.paid_at.strftime("%d/%m/%Y %H:%M") if payment.paid_at else ""
    c.drawRightString(w-20*mm, h-38*mm, f"Payé le: {paid_at}")

    y = h-70*mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(20*mm, y, "Client")
    c.setFont("Helvetica", 10)
    c.drawString(20*mm, y-6*mm, client.name)
    c.drawString(20*mm, y-12*mm, client.email)
    if client.phone:
        c.drawString(20*mm, y-18*mm, client.phone)

    y -= 36*mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(20*mm, y, "Détails du paiement")
    c.setFont("Helvetica", 10)
    text = c.beginText(20*mm, y-7*mm)
    lines = [f"Description: {invoice.description[:200]}", f"Méthode: {payment.method}"]
    if payment.gateway_transaction_id:
        lines.append(f"Référence transaction: {payment.gateway_transaction_id}")
    elif payment.reference:
        lines.append(f"Référence: {payment.reference}")
    text.textLines("\n".join(lines))
    c.drawText(text)

    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(w-20*mm, 55*mm, f"MONTANT PAYÉ: {payment.amount:,.0f} {settings.currency}".replace(",", " "))
    c.setFont("Helvetica", 9)
    c.drawString(20*mm, 30*mm, "Merci pour votre confiance.")
    c.drawString(20*mm, 24*mm, "Charles Tech 221 — Code. Crée. Innove. Réussi.")
    c.save()
    buf.seek(0)
    return buf
