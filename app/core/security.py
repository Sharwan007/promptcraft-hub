"""PIN hashing, signed admin sessions and CSRF tokens (stdlib + itsdangerous)."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from itsdangerous import BadSignature, SignatureExpired, URLSafeSerializer, URLSafeTimedSerializer

PBKDF2_ITERATIONS = 310_000
SESSION_COOKIE = "pch_session"
CSRF_COOKIE = "pch_csrf"
CSRF_HEADER = "X-CSRF-Token"
MIN_PIN_LENGTH = 6


def hash_pin(pin: str, salt: bytes | None = None, iterations: int = PBKDF2_ITERATIONS) -> tuple[str, str, int]:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, iterations)
    return digest.hex(), salt.hex(), iterations


def verify_pin(pin: str, pin_hash: str, salt_hex: str, iterations: int) -> bool:
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), bytes.fromhex(salt_hex), iterations)
    return hmac.compare_digest(digest.hex(), pin_hash)


def validate_pin_strength(pin: str) -> list[str]:
    errors = []
    if len(pin) < MIN_PIN_LENGTH:
        errors.append(f"The PIN must be at least {MIN_PIN_LENGTH} characters long.")
    if len(pin) > 64:
        errors.append("The PIN must be 64 characters or fewer.")
    if pin and len(set(pin)) == 1:
        errors.append("The PIN must not be a single repeated character.")
    return errors


class SessionManager:
    def __init__(self, secret_key: str, expiry_minutes: int):
        self._timed = URLSafeTimedSerializer(secret_key, salt="pch-admin-session")
        self._csrf = URLSafeSerializer(secret_key, salt="pch-csrf")
        self.max_age = max(1, expiry_minutes) * 60

    # ---- admin session ------------------------------------------------
    def create_session(self, nonce: str) -> str:
        return self._timed.dumps({"admin": True, "nonce": nonce})

    def read_session(self, token: str | None, nonce: str | None) -> tuple[bool, str]:
        """Return (valid, reason). reason is 'ok', 'none', 'expired' or 'invalid'."""
        if not token:
            return False, "none"
        try:
            data = self._timed.loads(token, max_age=self.max_age)
        except SignatureExpired:
            return False, "expired"
        except BadSignature:
            return False, "invalid"
        if not data.get("admin") or not nonce or not hmac.compare_digest(str(data.get("nonce")), nonce):
            return False, "invalid"
        return True, "ok"

    # ---- csrf ----------------------------------------------------------
    def new_csrf(self) -> str:
        return self._csrf.dumps(secrets.token_hex(16))

    def csrf_valid(self, cookie_value: str | None, submitted: str | None) -> bool:
        if not cookie_value or not submitted:
            return False
        if not hmac.compare_digest(cookie_value, submitted):
            return False
        try:
            self._csrf.loads(cookie_value)
        except BadSignature:
            return False
        return True


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def lock_until(minutes: int) -> datetime:
    return utcnow() + timedelta(minutes=minutes)
