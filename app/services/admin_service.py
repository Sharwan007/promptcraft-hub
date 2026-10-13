"""Local administration credentials: salted PIN hash, lockout after repeated failures, logs."""
from __future__ import annotations

import logging
import secrets
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AuthRequired, Conflict, TooManyAttempts, ValidationFailed
from app.core.security import hash_pin, utcnow, validate_pin_strength, verify_pin
from app.database import models as m

logger = logging.getLogger("promptcraft.admin")


def get_credential(db: Session) -> m.AdminCredential | None:
    return db.scalar(select(m.AdminCredential).order_by(m.AdminCredential.id).limit(1))


def is_configured(db: Session) -> bool:
    return get_credential(db) is not None


def setup_pin(db: Session, pin: str, confirm: str) -> m.AdminCredential:
    if get_credential(db) is not None:
        raise Conflict("An administrator PIN has already been set.", hint="Sign in with the existing PIN.")
    _check_new_pin(pin, confirm)
    digest, salt, iterations = hash_pin(pin)
    cred = m.AdminCredential(pin_hash=digest, salt=salt, iterations=iterations, session_nonce=secrets.token_hex(16))
    db.add(cred)
    db.commit()
    logger.info("Administrator PIN configured.")
    return cred


def _check_new_pin(pin: str, confirm: str) -> None:
    errors = validate_pin_strength(pin)
    if pin != confirm:
        errors.append("The PIN and its confirmation do not match.")
    if errors:
        raise ValidationFailed("The PIN could not be saved.", details=errors)


def verify_login(db: Session, pin: str) -> m.AdminCredential:
    """Check the PIN. Raises TooManyAttempts when locked, ValidationFailed on a wrong PIN."""
    settings = get_settings()
    cred = get_credential(db)
    if cred is None:
        raise ValidationFailed("No administrator PIN has been set yet.", hint="Open the setup screen first.")
    now = utcnow()
    if cred.locked_until and cred.locked_until > now:
        mins = max(1, int((cred.locked_until - now).total_seconds() // 60) + 1)
        raise TooManyAttempts(f"Too many incorrect PIN attempts. Try again in about {mins} minute(s).")
    if verify_pin(pin or "", cred.pin_hash, cred.salt, cred.iterations):
        cred.failed_attempts = 0
        cred.locked_until = None
        db.commit()
        return cred
    cred.failed_attempts = (cred.failed_attempts or 0) + 1
    remaining = settings.pin_max_attempts - cred.failed_attempts
    if cred.failed_attempts >= settings.pin_max_attempts:
        cred.locked_until = now + timedelta(minutes=settings.pin_lock_minutes)
        cred.failed_attempts = 0
        db.commit()
        logger.warning("Administrator sign-in locked after repeated failures.")
        raise TooManyAttempts(f"Too many incorrect PIN attempts. Sign-in is locked for {settings.pin_lock_minutes} minutes.")
    db.commit()
    raise AuthRequired("The PIN is not correct.", hint=f"{remaining} attempt(s) left before a temporary lock.")


def change_pin(db: Session, current: str, new: str, confirm: str) -> m.AdminCredential:
    cred = verify_login(db, current)
    _check_new_pin(new, confirm)
    digest, salt, iterations = hash_pin(new)
    cred.pin_hash, cred.salt, cred.iterations = digest, salt, iterations
    cred.session_nonce = secrets.token_hex(16)  # signs out every existing session
    db.commit()
    logger.info("Administrator PIN changed.")
    return cred


def sign_out_everywhere(db: Session) -> None:
    cred = get_credential(db)
    if cred:
        cred.session_nonce = secrets.token_hex(16)
        db.commit()


def log_validation_error(db: Session, source: str, message: str) -> None:
    db.add(m.ValidationErrorLog(source=source[:160], message=message[:1500]))
    db.commit()
    old = db.scalars(select(m.ValidationErrorLog.id).order_by(m.ValidationErrorLog.id.desc()).offset(200)).all()
    if old:
        db.execute(m.ValidationErrorLog.__table__.delete().where(m.ValidationErrorLog.id.in_(old)))
        db.commit()
