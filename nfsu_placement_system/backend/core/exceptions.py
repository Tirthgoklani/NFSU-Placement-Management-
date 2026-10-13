"""
Custom Exception Hierarchy for NFSU Placement Backend
Distinguishes security breaches, policy conflicts, and data validation errors.
"""

class NFSUBackendError(Exception):
    """Base exception for all NFSU backend errors."""
    def __init__(self, message: str, status_code: int = 500, error_code: str = "INTERNAL_ERROR"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code

class AuthenticationError(NFSUBackendError):
    """Raised when authentication credentials or MFA fails."""
    def __init__(self, message: str = "Invalid authentication credentials"):
        super().__init__(message, status_code=401, error_code="AUTHENTICATION_FAILED")

class AccountLockedError(NFSUBackendError):
    """Raised when an account is locked due to brute-force attempts."""
    def __init__(self, minutes_left: int):
        super().__init__(
            f"Account locked due to consecutive failed attempts. Please retry in {minutes_left} minute(s).",
            status_code=423,
            error_code="ACCOUNT_LOCKED"
        )

class AuthorizationError(NFSUBackendError):
    """Raised when user role lacks required permissions."""
    def __init__(self, message: str = "Access denied under NFSU role-based access control policy"):
        super().__init__(message, status_code=403, error_code="FORBIDDEN_ACCESS")

class IDORViolationError(AuthorizationError):
    """Raised when a candidate attempts to access another candidate's private record."""
    def __init__(self, target_resource: str):
        super().__init__(f"Security Violation: Insecure Direct Object Reference (IDOR) attempt on {target_resource} blocked.")
        self.error_code = "IDOR_ATTEMPT_BLOCKED"

class PolicyConflictError(NFSUBackendError):
    """Raised when an operation violates NFSU 2026-27 placement guidelines."""
    def __init__(self, message: str, policy_step: str = None):
        super().__init__(message, status_code=422, error_code="POLICY_VIOLATION")
        self.policy_step = policy_step

class ValidationError(NFSUBackendError):
    """Raised when input payload fails validation schema."""
    def __init__(self, message: str, field: str = None):
        super().__init__(message, status_code=400, error_code="VALIDATION_FAILED")
        self.field = field

class NotFoundError(NFSUBackendError):
    """Raised when requested entity is not found."""
    def __init__(self, entity: str, identifier: str):
        super().__init__(f"{entity} identified by '{identifier}' was not found.", status_code=404, error_code="NOT_FOUND")

class DuplicateResourceError(NFSUBackendError):
    """Raised when unique constraint (e.g. Placement ID) is violated."""
    def __init__(self, entity: str, field: str, value: str):
        super().__init__(f"{entity} with {field} '{value}' already exists.", status_code=409, error_code="DUPLICATE_RESOURCE")
