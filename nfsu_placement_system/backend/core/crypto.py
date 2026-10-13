"""
Core Cryptographic Engine for NFSU Placement Backend
Implements:
1. AES-256-GCM AEAD for field-level encryption of PII at rest
2. RFC 6238 Time-based One-Time Password (TOTP) Multi-Factor Authentication
3. HMAC-SHA256 Digital Signatures for audit log non-repudiation
"""

import os
import time
import struct
import hmac
import hashlib
import base64
import secrets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from config import SECRET_KEY

# Derive 256-bit AES-GCM master key from SECRET_KEY via HKDF-SHA256
_hkdf = HKDF(
    algorithm=hashes.SHA256(),
    length=32,
    salt=b"nfsu_placement_2026_salt",
    info=b"pii_aes_gcm_encryption_key"
)
_aes_key = _hkdf.derive(SECRET_KEY.encode())
_aesgcm = AESGCM(_aes_key)

# ---------------------------------------------------------------------------
# 1. Field-Level AES-256-GCM AEAD Encryption
# ---------------------------------------------------------------------------
def encrypt_pii(plaintext: str) -> str:
    """
    Encrypts sensitive PII string using AES-256-GCM.
    Returns: 'v1:<nonce_b64>:<ciphertext_b64>'
    """
    if not plaintext:
        return ""
    try:
        nonce = secrets.token_bytes(12)  # 96-bit nonce for AES-GCM
        data = plaintext.encode("utf-8")
        ciphertext = _aesgcm.encrypt(nonce, data, associated_data=b"NFSU_PII")
        n_b64 = base64.b64encode(nonce).decode("utf-8")
        c_b64 = base64.b64encode(ciphertext).decode("utf-8")
        return f"v1:{n_b64}:{c_b64}"
    except Exception as e:
        raise ValueError(f"AES-256-GCM encryption error: {str(e)}")

def decrypt_pii(ciphertext_str: str) -> str:
    """
    Decrypts an AES-256-GCM string.
    Gracefully returns original value if not encrypted.
    """
    if not ciphertext_str or not ciphertext_str.startswith("v1:"):
        return ciphertext_str
    try:
        parts = ciphertext_str.split(":")
        if len(parts) != 3:
            return ciphertext_str
        _, n_b64, c_b64 = parts
        nonce = base64.b64decode(n_b64)
        ciphertext = base64.b64decode(c_b64)
        decrypted = _aesgcm.decrypt(nonce, ciphertext, associated_data=b"NFSU_PII")
        return decrypted.decode("utf-8")
    except Exception:
        # Fallback if decryption fails or unencrypted string
        return ciphertext_str

# ---------------------------------------------------------------------------
# 2. RFC 6238 TOTP Multi-Factor Authentication Engine
# ---------------------------------------------------------------------------
def generate_totp_secret() -> str:
    """Generates a cryptographically secure 160-bit Base32 secret for TOTP."""
    random_bytes = secrets.token_bytes(20)
    return base64.b32encode(random_bytes).decode("utf-8").replace("=", "")

def generate_totp_uri(secret: str, username: str, issuer: str = "NFSU Placement Cell") -> str:
    """Generates an RFC-compliant otpauth URI for mobile authenticators."""
    from urllib.parse import quote
    enc_user = quote(f"{issuer}:{username}")
    enc_issuer = quote(issuer)
    return f"otpauth://totp/{enc_user}?secret={secret}&issuer={enc_issuer}&algorithm=SHA1&digits=6&period=30"

def compute_totp_code(secret: str, for_time: int = None, time_step: int = 30, digits: int = 6) -> str:
    """Computes standard 6-digit TOTP code using HMAC-SHA1 per RFC 6238."""
    if for_time is None:
        for_time = int(time.time())
    
    # Pad secret to standard base32 boundary
    padded_secret = secret + "=" * ((8 - len(secret) % 8) % 8)
    key = base64.b32decode(padded_secret.upper())
    
    counter = int(for_time // time_step)
    counter_bytes = struct.pack(">Q", counter)
    
    mac = hmac.new(key, counter_bytes, hashlib.sha1).digest()
    offset = mac[-1] & 0x0F
    code_int = (struct.unpack(">I", mac[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(code_int).zfill(digits)

def verify_totp_code(secret: str, user_code: str, window: int = 1) -> bool:
    """
    Verifies user-supplied TOTP code within +- window * 30 seconds for clock drift tolerance.
    """
    if not secret or not user_code or len(user_code.strip()) != 6:
        return False
    
    user_code = user_code.strip()
    now = int(time.time())
    for offset in range(-window, window + 1):
        test_time = now + (offset * 30)
        expected = compute_totp_code(secret, for_time=test_time)
        if hmac.compare_digest(expected, user_code):
            return True
    return False

# ---------------------------------------------------------------------------
# 3. HMAC-SHA256 Digital Signatures for Audit Blockchain
# ---------------------------------------------------------------------------
_hmac_key = hashlib.sha256((SECRET_KEY + "_audit_signing").encode()).digest()

def sign_audit_payload(payload: str) -> str:
    """Computes HMAC-SHA256 digital signature over audit record payload."""
    return hmac.new(_hmac_key, payload.encode("utf-8"), hashlib.sha256).hexdigest()

def verify_audit_signature(payload: str, signature: str) -> bool:
    """Verifies HMAC-SHA256 digital signature."""
    expected = sign_audit_payload(payload)
    return hmac.compare_digest(expected, signature)
