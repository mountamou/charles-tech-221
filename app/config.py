from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, model_validator

class Settings(BaseSettings):
    app_name: str = "Charles Tech 221"
    secret_key: str = "dev-secret-change-me"
    access_token_minutes: int = 1440
    database_url: str = "sqlite:///./charlestech_v4.db"
    database_replicated: bool = False  # set by start.sh when Litestream replicates SQLite to R2
    environment: str = "local"
    upload_dir: str = ""

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix):]
        return value

    admin_email: str = "admin@charlestech221.sn"
    admin_password: str = "ChangeMe123!"
    employee_email: str = "employee@charlestech221.sn"
    employee_password: str = "ChangeMe123!"

    contact_phone: str = "+221781910585"
    contact_email: str = "charlestech221@gmail.com"
    company_name: str = "Charles Tech 221"
    company_address: str = "Sénégal"
    currency: str = "FCFA"
    wave_merchant_number: str = "+221781910585"
    orange_money_number: str = "+221781910585"

    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = ""

    # CinetPay (online payments): empty api key means the integration is disabled and
    # only the manual Wave/Orange Money declaration flow is available.
    cinetpay_api_key: str = ""
    cinetpay_api_password: str = ""
    cinetpay_country: str = "SN"
    # Absolute site URL, needed for CinetPay's success/failed/notify callback URLs.
    public_base_url: str = "http://127.0.0.1:8000"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def validate_production(self):
        if self.environment == "production":
            if len(self.secret_key) < 32 or "change" in self.secret_key.lower():
                raise ValueError("Production requires a random SECRET_KEY of at least 32 characters")
            for password in (self.admin_password, self.employee_password):
                if len(password) < 8 or password == "ChangeMe123!":
                    raise ValueError("Production requires configured team passwords")
            is_postgres = self.database_url.startswith("postgresql+psycopg://")
            is_replicated_sqlite = self.database_url.startswith("sqlite") and self.database_replicated
            if not (is_postgres or is_replicated_sqlite):
                raise ValueError("Production requires PostgreSQL or a replicated SQLite database")
            has_r2 = self.r2_account_id and self.r2_access_key_id and self.r2_secret_access_key and self.r2_bucket
            if not self.upload_dir and not has_r2:
                raise ValueError("Production requires either a persistent UPLOAD_DIR or R2 storage configured")
        return self

settings = Settings()
