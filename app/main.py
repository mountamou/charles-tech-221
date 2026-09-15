from pathlib import Path
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse, PlainTextResponse, Response
from sqlalchemy.orm import Session
from sqlalchemy import select, func, inspect, text

from .config import settings
from .database import Base, engine, SessionLocal, get_db
from .models import User, Service, Project, ProjectFile, Invoice, Payment, Training, Enrollment, TrainingFile, ContactMessage, Notification, AuditLog
from .schemas import RegisterIn, LoginIn, UserOut, TokenOut, ProjectIn, ProjectUpdateIn, ContactIn, InvoiceIn, PaymentIn, PaymentStatusIn, EnrollmentIn, TrainingVideoIn, PasswordChangeIn
from .security import hash_password, verify_password, make_token, current_user, staff_user, admin_user
from .pdf_utils import invoice_pdf, payment_receipt_pdf
from . import storage
from . import cinetpay

app = FastAPI(title="Charles Tech 221 V4 API", version="4.0.0")
Base.metadata.create_all(engine)

def migrate_schema():
    """Add columns that models.py has gained since the database was created.

    create_all() only creates missing tables — it never alters an existing one, and
    with the database now persisted across deploys (Litestream/R2), every model field
    added from here on needs this to actually reach a table that already exists.
    """
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue  # brand new table: create_all() above already built it in full
            existing_cols = {c["name"] for c in insp.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing_cols:
                    continue
                ddl_type = column.type.compile(dialect=engine.dialect)
                conn.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {column.name} {ddl_type}"))
migrate_schema()

def log(db, user_id, action, details=""):
    db.add(AuditLog(user_id=user_id, action=action, details=details))
    db.commit()

def notify(db, user_id, title, body):
    db.add(Notification(user_id=user_id, title=title, body=body))
    db.commit()

def seed():
    db = SessionLocal()
    try:
        for email, pwd, name, role in [
            (settings.admin_email.lower(), settings.admin_password, "Administrateur Charles Tech 221", "admin"),
            (settings.employee_email.lower(), settings.employee_password, "Employé Charles Tech 221", "employee"),
        ]:
            # These two system accounts are controlled by the ADMIN_PASSWORD/EMPLOYEE_PASSWORD
            # secrets, not by the user: keep the stored hash in sync on every boot instead of
            # only seeding once, so rotating the secret actually changes the login.
            existing = db.scalar(select(User).where(User.email == email))
            if not existing:
                db.add(User(name=name,email=email,phone=settings.contact_phone,password_hash=hash_password(pwd),role=role))
            elif not verify_password(pwd, existing.password_hash):
                existing.password_hash = hash_password(pwd)
        defaults = [
            ("applications","Applications mobiles","Android, iOS et applications cross-platform modernes.",150000),
            ("web","Sites web","Sites vitrines, e-commerce et plateformes métiers.",100000),
            ("logiciels","Programmes informatiques","Logiciels de gestion et automatisation sur mesure.",175000),
            ("inventaire","Programme d'inventaire","Gestion de stock, entrées/sorties, clients, fournisseurs, factures et rapports.",200000),
            ("formation","Formation numérique","Développement, programmation et bureautique professionnelle.",50000),
        ]
        for slug, name, desc, price in defaults:
            if not db.scalar(select(Service).where(Service.slug == slug)):
                db.add(Service(slug=slug,name=name,description=desc,starting_price=price))
        trainings = [
            ("Développement Web","HTML, CSS, JavaScript, APIs et projets pratiques.",75000),
            ("Développement d'applications","Applications mobiles modernes et projets réels.",95000),
            ("Programmation informatique","Python, logique, bases de données et automatisation.",80000),
            ("Bureautique professionnelle","Word, Excel, PowerPoint et productivité.",50000),
        ]
        for title, desc, price in trainings:
            if not db.scalar(select(Training).where(Training.title == title)):
                db.add(Training(title=title,description=desc,price=price))
        db.commit()
    finally:
        db.close()
seed()

@app.get("/api/health")
def health():
    return {"ok": True, "version": "4.0.0"}

@app.get("/api/config")
def public_config():
    return {
        "phone": settings.contact_phone,
        "email": settings.contact_email,
        "currency": settings.currency,
        "wave": settings.wave_merchant_number,
        "orange_money": settings.orange_money_number,
        "cinetpay_enabled": bool(settings.cinetpay_api_key and settings.cinetpay_api_password),
    }

@app.get("/api/services")
def services(db: Session = Depends(get_db)):
    rows = db.scalars(select(Service).where(Service.active == True).order_by(Service.id)).all()
    return [{"id":x.id,"slug":x.slug,"name":x.name,"description":x.description,"starting_price":x.starting_price} for x in rows]

@app.get("/api/trainings")
def trainings(db: Session = Depends(get_db)):
    rows = db.scalars(select(Training).where(Training.active == True).order_by(Training.id)).all()
    return [{"id":x.id,"title":x.title,"description":x.description,"price":x.price} for x in rows]

@app.post("/api/auth/register", response_model=TokenOut)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    email=data.email.lower()
    if db.scalar(select(User).where(User.email==email)):
        raise HTTPException(409,"Cet e-mail est déjà utilisé")
    user=User(name=data.name,email=email,phone=data.phone,password_hash=hash_password(data.password),role="client")
    db.add(user); db.commit(); db.refresh(user)
    log(db,user.id,"register","Création de compte client")
    return {"access_token":make_token(user),"user":user}

@app.post("/api/auth/login", response_model=TokenOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    user=db.scalar(select(User).where(User.email==data.email.lower()))
    if not user or not user.active or not verify_password(data.password,user.password_hash):
        raise HTTPException(401,"Identifiants incorrects")
    log(db,user.id,"login","Connexion réussie")
    return {"access_token":make_token(user),"user":user}

@app.get("/api/me", response_model=UserOut)
def me(user:User=Depends(current_user)): return user

@app.post("/api/me/change-password")
def change_password(data:PasswordChangeIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    if not verify_password(data.current_password,user.password_hash):
        raise HTTPException(400,"Mot de passe actuel incorrect")
    user.password_hash=hash_password(data.new_password); db.commit()
    log(db,user.id,"change_password","Mot de passe modifié")
    return {"ok":True}

@app.post("/api/contact")
def contact(data: ContactIn, db: Session = Depends(get_db)):
    row=ContactMessage(name=data.name,email=str(data.email or ""),phone=data.phone,subject=data.subject,message=data.message)
    db.add(row); db.commit()
    return {"ok":True,"message":"Message reçu. Nous vous répondrons rapidement."}

@app.post("/api/projects")
def create_project(data:ProjectIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    p=Project(client_id=user.id,service=data.service,title=data.title,budget=data.budget,details=data.details)
    db.add(p); db.commit(); db.refresh(p)
    notify(db,user.id,"Projet créé",f"Votre demande « {p.title} » a été enregistrée.")
    log(db,user.id,"create_project",f"Projet #{p.id}")
    return {"id":p.id,"status":p.status,"message":"Projet enregistré"}

@app.get("/api/projects")
def my_projects(user:User=Depends(current_user),db:Session=Depends(get_db)):
    rows=db.scalars(select(Project).where(Project.client_id==user.id).order_by(Project.created_at.desc())).all()
    return [{"id":p.id,"service":p.service,"title":p.title,"budget":p.budget,"details":p.details,"status":p.status,"progress":p.progress,"created_at":p.created_at.isoformat()} for p in rows]

@app.post("/api/projects/{project_id}/files")
def upload_file(project_id:int,file:UploadFile=File(...),user:User=Depends(current_user),db:Session=Depends(get_db)):
    p=db.get(Project,project_id)
    if not p or (p.client_id!=user.id and user.role not in ("employee","admin")):
        raise HTTPException(404,"Projet introuvable")
    ext=Path(file.filename or "").suffix[:12]
    stored=f"{uuid4().hex}{ext}"
    storage.save(stored,file.file)
    row=ProjectFile(project_id=project_id,uploaded_by=user.id,original_name=file.filename or stored,stored_name=stored)
    db.add(row);db.commit()
    log(db,user.id,"upload_file",f"Projet #{project_id}: {row.original_name}")
    return {"ok":True,"id":row.id,"name":row.original_name}

@app.get("/api/projects/{project_id}/files")
def project_files(project_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    p=db.get(Project,project_id)
    if not p or (p.client_id!=user.id and user.role not in ("employee","admin")): raise HTTPException(404,"Projet introuvable")
    rows=db.scalars(select(ProjectFile).where(ProjectFile.project_id==project_id)).all()
    return [{"id":r.id,"name":r.original_name,"created_at":r.created_at.isoformat()} for r in rows]

@app.get("/api/projects/files/{file_id}")
def download_file(file_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    row=db.get(ProjectFile,file_id)
    if not row: raise HTTPException(404,"Fichier introuvable")
    p=db.get(Project,row.project_id)
    if p.client_id!=user.id and user.role not in ("employee","admin"): raise HTTPException(403,"Accès refusé")
    return storage.download_response(row.stored_name,row.original_name)

@app.get("/api/invoices")
def my_invoices(user:User=Depends(current_user),db:Session=Depends(get_db)):
    rows=db.scalars(select(Invoice).where(Invoice.client_id==user.id).order_by(Invoice.issued_at.desc())).all()
    return [{"id":i.id,"reference":i.reference,"description":i.description,"amount":i.amount,"status":i.status,"issued_at":i.issued_at.isoformat()} for i in rows]

@app.get("/api/invoices/{invoice_id}/pdf")
def invoice_download(invoice_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    inv=db.get(Invoice,invoice_id)
    if not inv or (inv.client_id!=user.id and user.role not in ("employee","admin")): raise HTTPException(404,"Facture introuvable")
    client=db.get(User,inv.client_id)
    buf=invoice_pdf(inv,client)
    return StreamingResponse(buf,media_type="application/pdf",headers={"Content-Disposition":f'attachment; filename="{inv.reference}.pdf"'})

@app.post("/api/invoices/{invoice_id}/pay")
def invoice_pay(invoice_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    inv=db.get(Invoice,invoice_id)
    if not inv or (inv.client_id!=user.id and user.role not in ("employee","admin")): raise HTTPException(404,"Facture introuvable")
    if inv.status=="Payée": raise HTTPException(409,"Facture déjà payée")
    row=Payment(invoice_id=inv.id,client_id=inv.client_id,method="CinetPay",amount=inv.amount,status="En attente")
    db.add(row);db.commit();db.refresh(row)
    try:
        url=cinetpay.start_payment(db,row,inv,db.get(User,inv.client_id))
    except cinetpay.CinetPayUnavailable as e:
        raise HTTPException(503,str(e))
    except cinetpay.AmountOutOfRange as e:
        raise HTTPException(400,str(e))
    log(db,user.id,"invoice_pay_init",inv.reference)
    return {"payment_url":url}

@app.get("/api/payments/{payment_id}/receipt")
def payment_receipt(payment_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    p=db.get(Payment,payment_id)
    if not p or (p.client_id!=user.id and user.role not in ("employee","admin")): raise HTTPException(404,"Paiement introuvable")
    if p.status!="Validé": raise HTTPException(409,"Paiement non confirmé")
    inv=db.get(Invoice,p.invoice_id)
    client=db.get(User,p.client_id)
    buf=payment_receipt_pdf(p,inv,client)
    return StreamingResponse(buf,media_type="application/pdf",headers={"Content-Disposition":f'attachment; filename="recu-{inv.reference}.pdf"'})

@app.post("/api/payments/cinetpay/webhook")
def cinetpay_webhook(data:dict,db:Session=Depends(get_db)):
    cinetpay.confirm_from_webhook(db,data,log,notify)
    return {"ok":True}

@app.post("/api/payments")
def declare_payment(data:PaymentIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    inv=db.get(Invoice,data.invoice_id)
    if not inv or inv.client_id!=user.id: raise HTTPException(404,"Facture introuvable")
    row=Payment(invoice_id=inv.id,client_id=user.id,method=data.method,amount=data.amount,reference=data.reference,status="En attente")
    db.add(row);db.commit();db.refresh(row)
    notify(db,user.id,"Paiement déclaré",f"Votre paiement de {row.amount:,.0f} {settings.currency} est en attente de validation.".replace(","," "))
    return {"ok":True,"id":row.id,"status":row.status}

@app.get("/api/payments")
def my_payments(user:User=Depends(current_user),db:Session=Depends(get_db)):
    rows=db.scalars(select(Payment).where(Payment.client_id==user.id).order_by(Payment.created_at.desc())).all()
    return [{"id":p.id,"invoice_id":p.invoice_id,"method":p.method,"amount":p.amount,"reference":p.reference,"status":p.status,"created_at":p.created_at.isoformat()} for p in rows]

@app.post("/api/enrollments")
def enroll(data:EnrollmentIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    tr=db.get(Training,data.training_id)
    if not tr or not tr.active: raise HTTPException(404,"Formation introuvable")
    existing=db.scalar(select(Enrollment).where(Enrollment.user_id==user.id,Enrollment.training_id==data.training_id))
    if existing: raise HTTPException(409,"Vous êtes déjà inscrit")
    e=Enrollment(user_id=user.id,training_id=tr.id);db.add(e);db.commit();db.refresh(e)
    notify(db,user.id,"Inscription formation",f"Inscription confirmée à « {tr.title} ».")
    return {"ok":True,"id":e.id}

@app.get("/api/enrollments")
def my_enrollments(user:User=Depends(current_user),db:Session=Depends(get_db)):
    rows=db.scalars(select(Enrollment).where(Enrollment.user_id==user.id)).all()
    result=[]
    for e in rows:
        tr=db.get(Training,e.training_id)
        result.append({"id":e.id,"training_id":e.training_id,"title":tr.title if tr else "Formation","status":e.status,"progress":e.progress})
    return result

@app.post("/api/trainings/{training_id}/pay")
def training_pay(training_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    tr=db.get(Training,training_id)
    if not tr or not tr.active: raise HTTPException(404,"Formation introuvable")
    if tr.price<=0: raise HTTPException(400,"Formation gratuite : utilisez l'inscription directe")
    if db.scalar(select(Enrollment).where(Enrollment.user_id==user.id,Enrollment.training_id==training_id)):
        raise HTTPException(409,"Vous êtes déjà inscrit")
    ref=f"CT221-{datetime.utcnow():%Y%m}-{uuid4().hex[:6].upper()}"
    inv=Invoice(client_id=user.id,training_id=tr.id,reference=ref,description=f"Formation : {tr.title}",amount=tr.price)
    db.add(inv);db.commit();db.refresh(inv)
    row=Payment(invoice_id=inv.id,client_id=user.id,method="CinetPay",amount=inv.amount,status="En attente")
    db.add(row);db.commit();db.refresh(row)
    try:
        url=cinetpay.start_payment(db,row,inv,user)
    except cinetpay.CinetPayUnavailable as e:
        raise HTTPException(503,str(e))
    except cinetpay.AmountOutOfRange as e:
        raise HTTPException(400,str(e))
    log(db,user.id,"training_pay_init",tr.title)
    return {"payment_url":url}

@app.get("/api/trainings/{training_id}/files")
def training_files(training_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    if user.role not in ("employee","admin") and not db.scalar(select(Enrollment).where(Enrollment.user_id==user.id,Enrollment.training_id==training_id)):
        raise HTTPException(403,"Inscription requise")
    rows=db.scalars(select(TrainingFile).where(TrainingFile.training_id==training_id).order_by(TrainingFile.id)).all()
    out=[]
    for f in rows:
        item={"id":f.id,"kind":f.kind,"label":f.label}
        if f.kind=="video": item["video_url"]=f.video_url
        else: item["download_url"]=f"/api/trainings/files/{f.id}"
        out.append(item)
    return out

@app.get("/api/trainings/files/{file_id}")
def training_file_download(file_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    row=db.get(TrainingFile,file_id)
    if not row or row.kind!="pdf": raise HTTPException(404,"Fichier introuvable")
    if user.role not in ("employee","admin") and not db.scalar(select(Enrollment).where(Enrollment.user_id==user.id,Enrollment.training_id==row.training_id)):
        raise HTTPException(403,"Inscription requise")
    return storage.download_response(row.stored_name,row.original_name or "support.pdf")

@app.get("/api/notifications")
def notifications(user:User=Depends(current_user),db:Session=Depends(get_db)):
    rows=db.scalars(select(Notification).where(Notification.user_id==user.id).order_by(Notification.created_at.desc())).all()
    return [{"id":n.id,"title":n.title,"body":n.body,"read":n.read,"created_at":n.created_at.isoformat()} for n in rows]

@app.post("/api/notifications/{notification_id}/read")
def notification_read(notification_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    n=db.get(Notification,notification_id)
    if not n or n.user_id!=user.id: raise HTTPException(404,"Notification introuvable")
    n.read=True;db.commit();return {"ok":True}

@app.get("/api/staff/dashboard")
def staff_dashboard(_:User=Depends(staff_user),db:Session=Depends(get_db)):
    return {
        "clients": db.scalar(select(func.count()).select_from(User).where(User.role=="client")),
        "projects": db.scalar(select(func.count()).select_from(Project)),
        "open_projects": db.scalar(select(func.count()).select_from(Project).where(Project.status!="Terminé")),
        "invoices": db.scalar(select(func.count()).select_from(Invoice)),
        "unpaid": db.scalar(select(func.count()).select_from(Invoice).where(Invoice.status!="Payée")),
        "pending_payments": db.scalar(select(func.count()).select_from(Payment).where(Payment.status=="En attente")),
    }

@app.get("/api/staff/projects")
def staff_projects(_:User=Depends(staff_user),db:Session=Depends(get_db)):
    rows=db.scalars(select(Project).order_by(Project.created_at.desc())).all()
    out=[]
    for p in rows:
        client=db.get(User,p.client_id)
        out.append({"id":p.id,"client_id":p.client_id,"client":client.name if client else "Client","phone":client.phone if client else "",
                    "service":p.service,"title":p.title,"budget":p.budget,"status":p.status,"progress":p.progress,"assigned_to":p.assigned_to})
    return out

@app.patch("/api/staff/projects/{project_id}")
def update_project(project_id:int,data:ProjectUpdateIn,staff:User=Depends(staff_user),db:Session=Depends(get_db)):
    p=db.get(Project,project_id)
    if not p: raise HTTPException(404,"Projet introuvable")
    if data.status is not None: p.status=data.status
    if data.progress is not None: p.progress=data.progress
    if data.assigned_to is not None: p.assigned_to=data.assigned_to
    p.updated_at=datetime.utcnow();db.commit()
    notify(db,p.client_id,"Projet mis à jour",f"« {p.title} » : {p.status} — {p.progress}%")
    log(db,staff.id,"update_project",f"Projet #{p.id}: {p.status}, {p.progress}%")
    return {"ok":True}

@app.post("/api/staff/invoices")
def create_invoice(data:InvoiceIn,staff:User=Depends(staff_user),db:Session=Depends(get_db)):
    client=db.get(User,data.client_id)
    if not client or client.role!="client": raise HTTPException(404,"Client introuvable")
    ref=f"CT221-{datetime.utcnow().strftime('%Y%m')}-{uuid4().hex[:6].upper()}"
    inv=Invoice(client_id=data.client_id,project_id=data.project_id,reference=ref,description=data.description,amount=data.amount,due_at=datetime.utcnow()+timedelta(days=15))
    db.add(inv);db.commit();db.refresh(inv)
    notify(db,client.id,"Nouvelle facture",f"Facture {inv.reference} : {inv.amount:,.0f} {settings.currency}".replace(","," "))
    log(db,staff.id,"create_invoice",inv.reference)
    return {"ok":True,"id":inv.id,"reference":inv.reference}

@app.get("/api/staff/invoices")
def staff_invoices(_:User=Depends(staff_user),db:Session=Depends(get_db)):
    rows=db.scalars(select(Invoice).order_by(Invoice.issued_at.desc())).all()
    out=[]
    for i in rows:
        client=db.get(User,i.client_id)
        out.append({"id":i.id,"reference":i.reference,"client":client.name if client else "Client","client_id":i.client_id,
                    "amount":i.amount,"status":i.status,"description":i.description})
    return out

@app.get("/api/staff/payments")
def staff_payments(_:User=Depends(staff_user),db:Session=Depends(get_db)):
    rows=db.scalars(select(Payment).order_by(Payment.created_at.desc())).all()
    return [{"id":p.id,"invoice_id":p.invoice_id,"client_id":p.client_id,"method":p.method,"amount":p.amount,"reference":p.reference,"status":p.status} for p in rows]

@app.patch("/api/staff/payments/{payment_id}")
def payment_status(payment_id:int,data:PaymentStatusIn,staff:User=Depends(staff_user),db:Session=Depends(get_db)):
    p=db.get(Payment,payment_id)
    if not p: raise HTTPException(404,"Paiement introuvable")
    p.status=data.status
    inv=db.get(Invoice,p.invoice_id)
    if data.status=="Validé" and inv:
        inv.status="Payée"
    db.commit()
    notify(db,p.client_id,"Paiement mis à jour",f"Statut de votre paiement : {p.status}")
    log(db,staff.id,"payment_status",f"Paiement #{p.id}: {p.status}")
    return {"ok":True}

@app.post("/api/staff/trainings/{training_id}/video")
def staff_training_video(training_id:int,data:TrainingVideoIn,staff:User=Depends(staff_user),db:Session=Depends(get_db)):
    tr=db.get(Training,training_id)
    if not tr: raise HTTPException(404,"Formation introuvable")
    row=TrainingFile(training_id=training_id,kind="video",label=data.label,video_url=data.video_url)
    db.add(row);db.commit()
    log(db,staff.id,"staff_training_video",tr.title)
    return {"ok":True,"id":row.id}

@app.post("/api/staff/trainings/{training_id}/pdf")
def staff_training_pdf(training_id:int,file:UploadFile=File(...),label:str="",staff:User=Depends(staff_user),db:Session=Depends(get_db)):
    tr=db.get(Training,training_id)
    if not tr: raise HTTPException(404,"Formation introuvable")
    ext=Path(file.filename or "").suffix[:12]
    stored=f"{uuid4().hex}{ext}"
    storage.save(stored,file.file)
    row=TrainingFile(training_id=training_id,kind="pdf",label=label,stored_name=stored,original_name=file.filename or stored)
    db.add(row);db.commit()
    log(db,staff.id,"staff_training_pdf",f"{tr.title}: {row.original_name}")
    return {"ok":True,"id":row.id}

@app.get("/api/staff/trainings/{training_id}/files")
def staff_training_files(training_id:int,_:User=Depends(staff_user),db:Session=Depends(get_db)):
    rows=db.scalars(select(TrainingFile).where(TrainingFile.training_id==training_id).order_by(TrainingFile.id)).all()
    return [{"id":f.id,"kind":f.kind,"label":f.label,"video_url":f.video_url,"name":f.original_name} for f in rows]

@app.get("/api/admin/users")
def admin_users(_:User=Depends(admin_user),db:Session=Depends(get_db)):
    rows=db.scalars(select(User).order_by(User.created_at.desc())).all()
    return [{"id":u.id,"name":u.name,"email":u.email,"phone":u.phone,"role":u.role,"active":u.active} for u in rows]

@app.get("/api/admin/audit")
def admin_audit(_:User=Depends(admin_user),db:Session=Depends(get_db)):
    rows=db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(100)).all()
    return [{"id":a.id,"user_id":a.user_id,"action":a.action,"details":a.details,"created_at":a.created_at.isoformat()} for a in rows]

@app.get("/api/inventory/demo")
def inventory_demo():
    return {"products":1256,"entries":235,"exits":187,"stock_value":12450000,"currency":"FCFA","low_stock":12}

@app.get("/robots.txt")
def robots():
    lines=["User-agent: *","Disallow: /portal","Disallow: /staff","Disallow: /api/",f"Sitemap: {settings.public_base_url}/sitemap.xml"]
    return PlainTextResponse("\n".join(lines))

@app.get("/sitemap.xml")
def sitemap():
    xml=f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>{settings.public_base_url}/</loc></url></urlset>'
    return Response(content=xml,media_type="application/xml")

STATIC=Path(__file__).parent/"static"
app.mount("/static",StaticFiles(directory=STATIC),name="static")
@app.get("/") 
def home(): return FileResponse(STATIC/"index.html")
@app.get("/portal")
def portal(): return FileResponse(STATIC/"portal.html")
@app.get("/staff")
def staff(): return FileResponse(STATIC/"staff.html")
