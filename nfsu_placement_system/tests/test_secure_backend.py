"""
Comprehensive Test Suite for Enterprise Secure Backend
Validates AES-256-GCM encryption, RFC 6238 TOTP MFA, REST API v1 endpoints,
and security defense mechanisms (IDOR, role enforcement, input validation).
"""

import unittest
from app import create_app
from backend.core.crypto import (
    encrypt_pii, decrypt_pii, generate_totp_secret,
    compute_totp_code, verify_totp_code
)
from backend.repositories.student_repository import StudentRepository
from backend.repositories.audit_repository import AuditRepository
from backend.services.audit_service import AuditService

class TestSecureBackend(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    # 1. Cryptography: AES-256-GCM AEAD Encryption
    def test_aes_gcm_encryption_and_integrity(self):
        secret_mobile = "+91 9825101001"
        ciphertext = encrypt_pii(secret_mobile)
        self.assertTrue(ciphertext.startswith("v1:"))
        self.assertNotEqual(ciphertext, secret_mobile)

        # Successful decryption
        decrypted = decrypt_pii(ciphertext)
        self.assertEqual(decrypted, secret_mobile)

        # Nonce randomness test: Encrypting the same string twice produces unique ciphertexts
        ciphertext2 = encrypt_pii(secret_mobile)
        self.assertNotEqual(ciphertext, ciphertext2)
        self.assertEqual(decrypt_pii(ciphertext2), secret_mobile)

        # Tamper defense test: altering ciphertext causes authentication tag failure
        corrupted = ciphertext[:-2] + ("AA" if ciphertext[-2:] != "AA" else "BB")
        # AEAD decryption of corrupted payload gracefully falls back or rejects
        self.assertNotEqual(decrypt_pii(corrupted), secret_mobile)

    # 2. Cryptography: RFC 6238 TOTP Multi-Factor Authentication
    def test_rfc6238_totp_mfa_engine(self):
        secret = generate_totp_secret()
        self.assertEqual(len(secret), 32)

        # Compute valid code
        valid_code = compute_totp_code(secret)
        self.assertEqual(len(valid_code), 6)
        self.assertTrue(valid_code.isdigit())

        # Verify valid code
        self.assertTrue(verify_totp_code(secret, valid_code))

        # Reject invalid code
        self.assertFalse(verify_totp_code(secret, "000000" if valid_code != "000000" else "999999"))

    # 3. REST API: Authentication Endpoint
    def test_api_login_endpoint(self):
        # Valid login
        resp = self.client.post("/api/v1/auth/login", json={
            "username": "admin",
            "password": "Admin@NFSU2026!"
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("token", data)
        self.assertEqual(data["user"]["role"], "Placement Administrator")

        # Invalid credentials
        resp_invalid = self.client.post("/api/v1/auth/login", json={
            "username": "admin",
            "password": "WrongPassword!"
        })
        self.assertEqual(resp_invalid.status_code, 401)

    # 4. REST API: Student Endpoints with Bearer Token
    def test_api_students_crud_and_validation(self):
        # Authenticate as admin
        admin_token = "admin:Placement Administrator"
        headers = {"Authorization": f"Bearer {admin_token}"}

        # List students
        resp = self.client.get("/api/v1/students", headers=headers)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("students", resp.get_json())

        # Input validation test: Create student with invalid course -> must return 400
        resp_bad = self.client.post("/api/v1/students", json={
            "placement_id": "NFSU26-CS-999",
            "student_name": "Invalid Student",
            "mobile_number": "+91 9825101001",
            "email_id": "invalid@nfsu.ac.in",
            "course": "B.A. English Literature", # Not in 5 covered programmes!
            "cgpa": 8.0,
            "active_backlogs": 0
        }, headers=headers)
        self.assertEqual(resp_bad.status_code, 400)
        self.assertIn("Invalid programme", resp_bad.get_json()["message"])

        # Input validation test: Create student with invalid Placement ID format -> must return 400
        resp_bad_pid = self.client.post("/api/v1/students", json={
            "placement_id": "INVALID-ID", # Doesn't match NFSU regex
            "student_name": "Invalid Student",
            "mobile_number": "+91 9825101001",
            "email_id": "invalid@nfsu.ac.in",
            "course": "M.Tech. Computer Science (M.Tech. CS)",
            "cgpa": 8.0,
            "active_backlogs": 0
        }, headers=headers)
        self.assertEqual(resp_bad_pid.status_code, 400)

    # 5. REST API Security Challenge: Student IDOR Defense over API
    def test_api_student_idor_defense(self):
        # Rohit (student_id = 1)
        student_token = "student_rohit:Student"
        headers = {"Authorization": f"Bearer {student_token}"}

        # Rohit accesses own profile (id = 1) -> Allowed (200)
        resp_own = self.client.get("/api/v1/students/1", headers=headers)
        self.assertEqual(resp_own.status_code, 200)

        # IDOR Attempt: Rohit attempts to access student id = 2 (Pooja) -> Blocked (403)
        resp_other = self.client.get("/api/v1/students/2", headers=headers)
        self.assertEqual(resp_other.status_code, 403)
        self.assertIn("Forbidden", resp_other.get_json()["error"])

        # Tampering Attempt: Student attempts to update own placement status -> Blocked (403)
        resp_tamper = self.client.put("/api/v1/students/1", json={
            "placement_status": "Internship + PPO/FTE",
            "cgpa": 10.0
        }, headers=headers)
        self.assertEqual(resp_tamper.status_code, 403)

    # 6. REST API: Policy Rule Engine Live Evaluation
    def test_api_policy_evaluation(self):
        admin_token = "admin:Placement Administrator"
        headers = {"Authorization": f"Bearer {admin_token}"}

        # Test Student 1 (Rohit - Placed in A+ Microsoft 26.5 LPA) against target drive
        resp = self.client.post("/api/v1/policy/evaluate", json={
            "student_id": 1,
            "drive": {
                "id": 2,
                "company_name": "Palo Alto Networks",
                "category": "A+",
                "offer_type": "F",
                "fte_package_ctc": 22.0,
                "min_cgpa": 7.0,
                "max_backlogs": 0,
                "eligible_courses": "M.Tech. Computer Science (M.Tech. CS)"
            }
        }, headers=headers)

        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        # Rohit is placed in A+ -> Must be Blocked under No Switching Rule
        self.assertEqual(data["decision"], "Blocked")
        self.assertFalse(data["can_apply"])
        self.assertIn("out of placement process", data["summary"])

    # 7. REST API: Audit Blockchain Verification
    def test_api_audit_blockchain_verify(self):
        admin_token = "admin:Placement Administrator"
        headers = {"Authorization": f"Bearer {admin_token}"}

        resp = self.client.post("/api/v1/audit/verify", headers=headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["is_valid"])
        self.assertIn("All", data["message"])

if __name__ == "__main__":
    unittest.main()
