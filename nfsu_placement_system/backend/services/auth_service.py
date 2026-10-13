"""
Authentication & Multi-Factor Authentication Service
Handles credential verification, brute-force lockout, TOTP MFA, and token issuance.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, Optional
from werkzeug.security import generate_password_hash, check_password_hash
from backend.repositories.base_repository import BaseRepository
from backend.core.crypto import generate_totp_secret, generate_totp_uri, verify_totp_code
from backend.core.exceptions import AuthenticationError, AccountLockedError, NotFoundError
from config import MAX_LOGIN_ATTEMPTS, LOCKOUT_DURATION_MINUTES

class AuthService:

    @staticmethod
    def authenticate_user(username: str, password: str) -> Dict[str, Any]:
        """Validates primary credentials and checks account lockout."""
        query = "SELECT * FROM users WHERE username = ?"
        user = BaseRepository.fetch_one(query, (username,))
        if not user:
            raise AuthenticationError("Invalid username or password.")

        # Check account lockout
        if user["locked_until"]:
            try:
                locked_until = datetime.fromisoformat(str(user["locked_until"]))
                if datetime.now() < locked_until:
                    minutes_left = int((locked_until - datetime.now()).total_seconds() / 60) + 1
                    raise AccountLockedError(minutes_left)
            except ValueError:
                pass

        # Check password hash
        if not check_password_hash(user["password_hash"], password):
            # Increment failed attempts
            new_attempts = user["failed_login_attempts"] + 1
            if new_attempts >= MAX_LOGIN_ATTEMPTS:
                lockout_time = (datetime.now() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)).isoformat()
                BaseRepository.execute(
                    "UPDATE users SET failed_login_attempts = ?, locked_until = ? WHERE id = ?",
                    (new_attempts, lockout_time, user["id"])
                )
                raise AccountLockedError(LOCKOUT_DURATION_MINUTES)
            else:
                BaseRepository.execute(
                    "UPDATE users SET failed_login_attempts = ? WHERE id = ?",
                    (new_attempts, user["id"])
                )
            raise AuthenticationError("Invalid username or password.")

        # Reset failed login count on success
        BaseRepository.execute(
            "UPDATE users SET failed_login_attempts = 0, locked_until = NULL WHERE id = ?",
            (user["id"],)
        )
        return user

    @staticmethod
    def setup_totp_mfa(user_id: int) -> Tuple[str, str]:
        """Generates a new TOTP secret and QR URI for the user."""
        user = BaseRepository.fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))
        if not user:
            raise NotFoundError("User", str(user_id))

        secret = generate_totp_secret()
        uri = generate_totp_uri(secret, user["username"])
        BaseRepository.execute("UPDATE users SET mfa_secret = ? WHERE id = ?", (secret, user_id))
        return secret, uri

    @staticmethod
    def verify_totp_mfa(user_id: int, user_code: str) -> bool:
        """Verifies TOTP 6-digit code against user's stored secret."""
        user = BaseRepository.fetch_one("SELECT mfa_secret FROM users WHERE id = ?", (user_id,))
        if not user or not user["mfa_secret"]:
            raise AuthenticationError("MFA is not configured for this user.")
        
        is_valid = verify_totp_code(user["mfa_secret"], user_code)
        if not is_valid:
            raise AuthenticationError("Invalid MFA security code.")
        return True
