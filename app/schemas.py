from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str = ""
    password: str = Field(min_length=8, max_length=128)

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    phone: str
    role: str
    active: bool
    model_config = {"from_attributes": True}

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

class ProjectIn(BaseModel):
    service: str
    title: str = Field(min_length=3, max_length=180)
    budget: str = ""
    details: str = Field(min_length=5, max_length=5000)

class ProjectUpdateIn(BaseModel):
    status: Optional[str] = None
    progress: Optional[int] = Field(default=None, ge=0, le=100)
    assigned_to: Optional[int] = None

class ContactIn(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    phone: str = ""
    subject: str
    message: str = Field(min_length=5, max_length=4000)

class InvoiceIn(BaseModel):
    client_id: int
    project_id: Optional[int] = None
    description: str
    amount: float = Field(gt=0)

class PaymentIn(BaseModel):
    invoice_id: int
    method: str
    amount: float = Field(gt=0)
    reference: str = ""

class PaymentStatusIn(BaseModel):
    status: str

class EnrollmentIn(BaseModel):
    training_id: int

class TrainingVideoIn(BaseModel):
    label: str = Field(default="", max_length=160)
    video_url: str = Field(min_length=5, max_length=500)

class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)
