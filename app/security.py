from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db
from .models import User

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer = HTTPBearer(auto_error=False)
ALGO = "HS256"

def hash_password(value: str) -> str:
    return pwd.hash(value)

def verify_password(value: str, hashed: str) -> bool:
    return pwd.verify(value, hashed)

def make_token(user: User) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode({"sub": str(user.id), "role": user.role, "exp": exp}, settings.secret_key, algorithm=ALGO)

def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if not credentials:
        raise HTTPException(401, "Authentification requise")
    try:
        payload = jwt.decode(credentials.credentials, settings.secret_key, algorithms=[ALGO])
        uid = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(401, "Jeton invalide")
    user = db.get(User, uid)
    if not user or not user.active:
        raise HTTPException(401, "Compte indisponible")
    return user

def staff_user(user: User = Depends(current_user)) -> User:
    if user.role not in ("employee", "admin"):
        raise HTTPException(403, "Accès employé requis")
    return user

def admin_user(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, "Accès administrateur requis")
    return user
