"""Settings read from environment variables, with development defaults."""
import os
import warnings
from dataclasses import dataclass, field

DEV_SECRET = 'dev-secret-change-me-in-production-0000'  # ≥ 32 bytes, as recommended for HS256


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv('DATABASE_URL', 'sqlite:///./chamados.db')
    secret_key: str = os.getenv('SECRET_KEY', DEV_SECRET)
    token_minutes: int = int(os.getenv('TOKEN_MINUTES', '480'))
    cors_origins: list[str] = field(default_factory=lambda: os.getenv('CORS_ORIGINS', 'http://localhost:5173').split(','))
    # Fraction of the SLA window after which an unmet target is flagged "em risco".
    sla_risk_fraction: float = float(os.getenv('SLA_RISK_FRACTION', '0.8'))


settings = Settings()
if settings.secret_key == DEV_SECRET:
    warnings.warn('SECRET_KEY not set: using the development key. Never use it in production.', stacklevel=1)
