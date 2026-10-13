"""
Security, Role-Based Access Control (RBAC), Privacy Masking, and
Forensic Tamper-Evident Cryptographic Audit Logging for NFSU Placement System.
"""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import session, request, redirect, url_for, flash, abort, render_template
from werkzeug.security import generate_password_hash, check_password_hash
from cryptography.fernet import Fernet
import base64

from config import (
    SECRET_KEY, MAX_LOGIN_ATTEMPTS, LOCKOUT_DURATION_MINUTES,
    PERMANENT_SESSION_LIFETIME_MINUTES
)
from database import query_db, execute_db, execute_insert

# Generate deterministic Fernet key derived from SECRET_KEY for field-level encryption
_fernet_key = base64.urlsafe_b64encode(hashlib.sha256(SECRET_KEY.encode()).digest())
_cipher = Fernet(_fernet_key)

def encrypt_sensitive_data(plaintext: str) -> str:
    """Encrypts confidential notes or compensation details using AES-CBC/HMAC (Fernet)."""
    if not plaintext:
        return ""
    return _cipher.encrypt(plaintext.encode("utf-8")).decode("utf-8")

def decrypt_sensitive_data(ciphertext: str) -> str:
    """Decrypts AES-encrypted data; returns fallback if not encrypted."""
    if not ciphertext:
        return ""
    try:
        return _cipher.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except Exception:
        return ciphertext  # Return plaintext fallback if legacy or unencrypted

def hash_password(password: str) -> str:
    return generate_password_hash(password, method="scrypt")

def verify_password(password: str, password_hash: str) -> bool:
    return check_password_hash(password_hash, password)

# -------------------------------------------------------------
# Brute-force Protection & Account Lockout
# -------------------------------------------------------------
def check_account_locked(user_row):
    """Checks whether the user account is temporarily locked due to failed attempts."""
    if not user_row or not user_row["locked_until"]:
        return False, None
    
    try:
        locked_until = datetime.fromisoformat(str(user_row["locked_until"]))
        if datetime.now() < locked_until:
            minutes_left = int((locked_until - datetime.now()).total_seconds() / 60) + 1
            return True, minutes_left
    except Exception:
        pass
    
    return False, None

def record_failed_login(username: str):
    """Increments failed login count and locks account if threshold exceeded."""
    user = query_db("SELECT id, failed_login_attempts FROM users WHERE username = ?", (username,), one=True)
    if not user:
        return
    
    new_attempts = user["failed_login_attempts"] + 1
    if new_attempts >= MAX_LOGIN_ATTEMPTS:
        lockout_time = (datetime.now() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)).isoformat()
        execute_db(
            "UPDATE users SET failed_login_attempts = ?, locked_until = ? WHERE id = ?",
            (new_attempts, lockout_time, user["id"])
        )
        log_audit_event(
            actor_username="SYSTEM",
            actor_role="SYSTEM",
            action="ACCOUNT_LOCKED",
            entity_type="Auth",
            entity_id=str(user["id"]),
            details=f"Account locked for {username} after {new_attempts} consecutive failed attempts."
        )
    else:
        execute_db(
            "UPDATE users SET failed_login_attempts = ? WHERE id = ?",
            (new_attempts, user["id"])
        )

def reset_failed_logins(user_id: int):
    """Resets failed login counter upon successful authentication."""
    execute_db(
        "UPDATE users SET failed_login_attempts = 0, locked_until = NULL WHERE id = ?",
        (user_id,)
    )

# -------------------------------------------------------------
# Privacy Masking Controls
# -------------------------------------------------------------
def mask_mobile_number(mobile: str, viewer_role: str) -> str:
    """Masks mobile number for privacy unless authorized (Placement Administrator/Officer)."""
    if not mobile:
        return "N/A"
    if viewer_role in ("Placement Administrator", "Placement Officer"):
        return mobile
    
    cleaned = "".join(filter(str.isdigit, mobile))
    if len(cleaned) >= 10:
        return f"{cleaned[:2]}*****{cleaned[-3:]}"
    elif len(cleaned) >= 6:
        return f"{cleaned[:2]}***{cleaned[-2:]}"
    return "***-***-****"

def mask_email_address(email: str, viewer_role: str) -> str:
    """Masks email address for student privacy when viewed by restricted roles."""
    if not email:
        return "N/A"
    if viewer_role in ("Placement Administrator", "Placement Officer", "Course Coordinator"):
        return email
    parts = email.split("@")
    if len(parts) == 2:
        uname, domain = parts
        masked_u = (uname[0] + "***" + uname[-1]) if len(uname) > 2 else "***"
        return f"{masked_u}@{domain}"
    return "***@***"

# -------------------------------------------------------------
# Tamper-Evident Forensic Cryptographic Audit Log
# -------------------------------------------------------------
GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"

def log_audit_event(actor_username: str, actor_role: str, action: str,
                    entity_type: str, entity_id: str = None, details: str = "",
                    before_state=None, after_state=None, ip_address: str = None):
    """
    Appends a new cryptographically chained audit record.
    record_hash = sha256(timestamp | actor | role | action | entity_type | entity_id | details | before | after | prev_hash)
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    ip = ip_address or (request.remote_addr if request else "127.0.0.1")
    
    before_json = json.dumps(before_state, default=str) if before_state is not None else ""
    after_json = json.dumps(after_state, default=str) if after_state is not None else ""

    # Fetch latest hash in chain
    latest = query_db("SELECT record_hash FROM audit_logs ORDER BY id DESC LIMIT 1", one=True)
    prev_hash = latest["record_hash"] if latest else GENESIS_HASH

    # Compute tamper-evident SHA-256 hash
    hasher = hashlib.sha256()
    payload = f"{timestamp}|{actor_username}|{actor_role}|{action}|{entity_type}|{entity_id or ''}|{details}|{before_json}|{after_json}|{prev_hash}"
    hasher.update(payload.encode("utf-8"))
    record_hash = hasher.hexdigest()

    execute_insert(
        """
        INSERT INTO audit_logs 
        (timestamp, actor_username, actor_role, action, entity_type, entity_id, details, before_state, after_state, ip_address, previous_hash, record_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (timestamp, actor_username, actor_role, action, entity_type, entity_id, details, before_json, after_json, ip, prev_hash, record_hash)
    )
    return record_hash

def verify_audit_log_integrity():
    """
    Forensic verification utility: Traverses the entire audit log blockchain
    and validates every cryptographic hash link. Flags any altered or deleted records.
    """
    records = query_db("SELECT * FROM audit_logs ORDER BY id ASC")
    if not records:
        return {
            "is_valid": True,
            "total_records": 0,
            "message": "Audit log is empty. Genesis integrity intact.",
            "tampered_record_id": None
        }

    expected_prev = GENESIS_HASH
    for r in records:
        # Check previous hash link
        if r["previous_hash"] != expected_prev:
            return {
                "is_valid": False,
                "total_records": len(records),
                "tampered_record_id": r["id"],
                "message": f"Cryptographic break detected at Log Record #{r['id']}: previous_hash mismatch."
            }
        
        # Recompute hash
        hasher = hashlib.sha256()
        payload = f"{r['timestamp']}|{r['actor_username']}|{r['actor_role']}|{r['action']}|{r['entity_type']}|{r['entity_id'] or ''}|{r['details']}|{r['before_state'] or ''}|{r['after_state'] or ''}|{r['previous_hash']}"
        hasher.update(payload.encode("utf-8"))
        computed_hash = hasher.hexdigest()

        if computed_hash != r["record_hash"]:
            return {
                "is_valid": False,
                "total_records": len(records),
                "tampered_record_id": r["id"],
                "message": f"Cryptographic tampering detected at Log Record #{r['id']}: payload hash does not match stored signature."
            }
        
        expected_prev = r["record_hash"]

    return {
        "is_valid": True,
        "total_records": len(records),
        "latest_hash": expected_prev,
        "message": f"Audit log verification successful. All {len(records)} cryptographic records intact."
    }

# -------------------------------------------------------------
# RBAC & Authorization Decorators
# -------------------------------------------------------------
def get_current_user():
    """Retrieves current authenticated user from session."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    return query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in to access the NFSU Placement Portal.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*allowed_roles):
    """Enforces role-based permissions strictly on backend routes."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in to continue.", "warning")
                return redirect(url_for("auth.login", next=request.path))
            
            user_role = session.get("role")
            if user_role not in allowed_roles:
                log_audit_event(
                    actor_username=session.get("username", "UNKNOWN"),
                    actor_role=user_role or "UNAUTHORIZED",
                    action="UNAUTHORIZED_ACCESS_ATTEMPT",
                    entity_type="RBAC",
                    entity_id=request.path,
                    details=f"Forbidden access attempt to {request.path} by role '{user_role}'. Required: {allowed_roles}"
                )
                flash(f"Access Denied: Your role ('{user_role}') lacks permission for this action.", "danger")
                return render_template("error.html", error_code=403, error_message="Unauthorized Access Restricted under NFSU Security Policy."), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def check_course_coordinator_scope(user, student_course: str) -> bool:
    """Course Coordinator is scoped strictly to their assigned programme."""
    if user["role"] != "Course Coordinator":
        return True
    return user["assigned_course"] == student_course

def check_recruiter_scope(user, company_name: str) -> bool:
    """Recruiters can only access records or drives matching their affiliated company."""
    if user["role"] != "Recruiter":
        return True
    return user["recruiter_company"] == company_name

def check_student_self_access(user, student_id: int) -> bool:
    """A student can ONLY access their own student record."""
    if user["role"] != "Student":
        return True
    return user["student_id"] == student_id
