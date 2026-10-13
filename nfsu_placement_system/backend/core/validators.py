"""
Input Validation and Sanitization Engine for NFSU Backend
Protects against malformed data, schema bypasses, and script injection.
"""

import re
from config import COURSES, BATCHES
from backend.core.exceptions import ValidationError

PLACEMENT_ID_REGEX = re.compile(r"^NFSU\d{2}-[A-Z0-9]{2,4}-\d{3,4}$", re.IGNORECASE)
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
MOBILE_REGEX = re.compile(r"^(\+?\d{1,3}[- ]?)?\d{10}$")

def validate_placement_id(placement_id: str) -> str:
    if not placement_id or not isinstance(placement_id, str):
        raise ValidationError("Placement ID is required and must be a string.", field="placement_id")
    cleaned = placement_id.strip().upper()
    if not PLACEMENT_ID_REGEX.match(cleaned):
        raise ValidationError(
            f"Invalid Placement ID format '{cleaned}'. Expected format like 'NFSU26-CS-001'.",
            field="placement_id"
        )
    return cleaned

def validate_email(email: str) -> str:
    if not email or not isinstance(email, str):
        raise ValidationError("Email ID is required.", field="email_id")
    cleaned = email.strip().lower()
    if not EMAIL_REGEX.match(cleaned):
        raise ValidationError(f"Invalid email format: '{cleaned}'.", field="email_id")
    return cleaned

def validate_mobile(mobile: str) -> str:
    if not mobile or not isinstance(mobile, str):
        raise ValidationError("Mobile number is required.", field="mobile_number")
    cleaned = mobile.strip()
    digits_only = "".join(filter(str.isdigit, cleaned))
    if len(digits_only) < 10 or len(digits_only) > 13:
        raise ValidationError(f"Invalid contact mobile number: '{cleaned}'.", field="mobile_number")
    return cleaned

def validate_course(course: str) -> str:
    if not course or course not in COURSES:
        raise ValidationError(
            f"Invalid programme '{course}'. Must be one of the 5 official NFSU covered programmes.",
            field="course"
        )
    return course

def validate_cgpa(cgpa_val) -> float:
    try:
        cgpa = float(cgpa_val)
    except (ValueError, TypeError):
        raise ValidationError("CGPA must be a valid numeric decimal value.", field="cgpa")
    if cgpa < 0.0 or cgpa > 10.0:
        raise ValidationError(f"CGPA must be between 0.00 and 10.00. Given: {cgpa}", field="cgpa")
    return round(cgpa, 2)

def validate_backlogs(backlogs_val) -> int:
    try:
        backlogs = int(backlogs_val)
    except (ValueError, TypeError):
        raise ValidationError("Active backlogs count must be an integer.", field="active_backlogs")
    if backlogs < 0:
        raise ValidationError("Active backlogs cannot be negative.", field="active_backlogs")
    return backlogs

def validate_ctc(ctc_val) -> float:
    try:
        ctc = float(ctc_val)
    except (ValueError, TypeError):
        raise ValidationError("Annual CTC package must be a valid number.", field="fte_package_ctc")
    if ctc < 0.0:
        raise ValidationError("CTC cannot be negative.", field="fte_package_ctc")
    return round(ctc, 2)

def validate_offer_type(offer_type: str) -> str:
    if offer_type not in ("I", "F", "I+F"):
        raise ValidationError(f"Invalid offer classification '{offer_type}'. Must be 'I', 'F', or 'I+F'.", field="offer_type")
    return offer_type

def sanitize_text(text: str, max_length: int = 500) -> str:
    if not text:
        return ""
    # Strip null bytes and control chars, trim
    cleaned = "".join(c for c in str(text) if c.isprintable() or c in "\n\r\t").strip()
    return cleaned[:max_length]
