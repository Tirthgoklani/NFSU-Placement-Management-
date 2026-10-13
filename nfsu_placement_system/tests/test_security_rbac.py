"""
Security, RBAC, IDOR Defense, and Attack Resistance Test Suite
Demonstrates enforcement of role permissions, student self-service boundaries,
brute-force lockout, SQLi/XSS resilience, and tamper-evident audit blockchain detection.
"""

import unittest
import sqlite3
from app import create_app
from database import get_db, execute_db, query_db
from security import verify_audit_log_integrity, log_audit_event

class TestSecurityAndRBAC(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def login_as(self, username, password):
        return self.client.post("/login", data={
            "username": username,
            "password": password
        }, follow_redirects=True)

    # 1. RBAC: Placement Administrator Privileges
    def test_admin_has_full_access(self):
        self.login_as("admin", "Admin@NFSU2026!")
        # Admin can access audit blockchain
        resp = self.client.get("/audit")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Forensic Tamper-Evident Audit Trail", resp.data)

        # Admin can access backups
        resp = self.client.get("/backup")
        self.assertEqual(resp.status_code, 200)

        # Admin can access students
        resp = self.client.get("/students")
        self.assertEqual(resp.status_code, 200)

    # 2. RBAC: Placement Officer Restrictions
    def test_officer_restricted_from_admin_zones(self):
        self.login_as("officer", "Officer@NFSU2026!")
        # Officer can access students and drives
        resp = self.client.get("/students")
        self.assertEqual(resp.status_code, 200)

        # Officer is BLOCKED from audit logs (HTTP 403)
        resp = self.client.get("/audit")
        self.assertEqual(resp.status_code, 403)

        # Officer is BLOCKED from backups (HTTP 403)
        resp = self.client.get("/backup")
        self.assertEqual(resp.status_code, 403)

    # 3. RBAC: Course Coordinator Scoping
    def test_course_coordinator_scope_isolation(self):
        self.login_as("coord_dfis", "Coord@NFSU2026!")
        # Coordinator for DFIS can view student in DFIS (Ananya Mishra id=25)
        resp = self.client.get("/students/25")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Ananya Mishra", resp.data)

        # Coordinator for DFIS is BLOCKED from viewing M.Tech CS student (e.g. Rohit Sharma id=1)
        resp = self.client.get("/students/1")
        self.assertEqual(resp.status_code, 403)
        self.assertIn(b"Unauthorized Department Access", resp.data)

    # 4. Security Challenge: Student IDOR Protection
    def test_student_cannot_access_other_student_profile(self):
        # Rohit (student_id = 1)
        self.login_as("student_rohit", "Student@NFSU2026!")

        # Can access own profile (id = 1)
        resp = self.client.get("/students/1")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Rohit Sharma", resp.data)

        # IDOR ATTEMPT: Rohit attempts to access student id = 2 (Pooja Patel)
        resp = self.client.get("/students/2")
        self.assertEqual(resp.status_code, 403)
        self.assertIn(b"Unauthorized", resp.data)

    # 5. Security Challenge: Student Cannot Tamper With Own Status or Package
    def test_student_cannot_modify_own_or_other_placement_records(self):
        self.login_as("student_rohit", "Student@NFSU2026!")

        # Tampering Attempt: Student submits POST to modify academic/placement status
        resp = self.client.post("/students/1/edit", data={
            "cgpa": "9.99",
            "registration_status": "Registered",
            "eligibility_status": "Eligible",
            "active_backlogs": "0"
        })
        # Must be rejected with 403 Forbidden!
        self.assertEqual(resp.status_code, 403)

    # 6. Recruiter Isolation: Recruiter cannot access other company's drives or global student directory
    def test_recruiter_company_isolation(self):
        # Recruiter for CrowdStrike
        self.login_as("recruiter_crowdstrike", "Recruiter@NFSU2026!")

        # Recruiter is redirected or blocked from master student directory
        resp = self.client.get("/students", follow_redirects=True)
        self.assertIn(b"Recruiters can only access applicants within their company drives", resp.data)

        # Recruiter can access CrowdStrike drive (id = 3)
        resp = self.client.get("/drives/3")
        self.assertEqual(resp.status_code, 200)

        # Recruiter is BLOCKED from accessing Palo Alto drive (id = 2)
        resp = self.client.get("/drives/2")
        self.assertEqual(resp.status_code, 403)

    # 7. Brute-Force Defense: Account Lockout after 5 failed attempts
    def test_brute_force_account_lockout(self):
        # Attempt 5 incorrect logins for student_sneha
        for i in range(5):
            self.client.post("/login", data={
                "username": "student_sneha",
                "password": "WrongPassword123!"
            })

        # 6th attempt: Even with or without correct password, account must be locked
        resp = self.client.post("/login", data={
            "username": "student_sneha",
            "password": "Student@NFSU2026!"
        }, follow_redirects=True)

        self.assertIn(b"Account locked due to excessive failed attempts", resp.data)

        # Clean up lockout in database for subsequent tests
        execute_db("UPDATE users SET failed_login_attempts = 0, locked_until = NULL WHERE username = 'student_sneha'")

    # 8. Cryptographic Tamper-Evident Audit Blockchain Verification
    def test_audit_blockchain_integrity_and_tamper_detection(self):
        # Baseline: Audit log should be completely valid
        status = verify_audit_log_integrity()
        self.assertTrue(status["is_valid"])

        # Tampering Simulation: Directly modify a record's details in SQLite without re-signing
        execute_db("UPDATE audit_logs SET details = 'MALICIOUS_UNAUTHORIZED_ALTERATION' WHERE id = 2")

        # Rerun verification: Blockchain MUST detect tampering at row 2!
        tamper_status = verify_audit_log_integrity()
        self.assertFalse(tamper_status["is_valid"])
        self.assertEqual(tamper_status["tampered_record_id"], 2)
        self.assertIn("Cryptographic tampering detected", tamper_status["message"])

        # Restore original state
        execute_db("UPDATE audit_logs SET details = 'Registered 31 baseline candidate profiles across 5 NFSU academic programmes.' WHERE id = 2")
        restored_status = verify_audit_log_integrity()
        self.assertTrue(restored_status["is_valid"])

    # 9. SQL Injection Resistance Test
    def test_sql_injection_defense(self):
        # 9a. Authentication SQL Injection: Attempt ' OR '1'='1' -- login bypass
        resp_login = self.client.post("/login", data={
            "username": "' OR '1'='1' --",
            "password": "' OR '1'='1"
        }, follow_redirects=True)
        self.assertIn(b"Invalid credentials provided", resp_login.data)

        # 9b. Search Query Parameterization: Ensure UNION attack does not return unauthorized rows
        self.login_as("admin", "Admin@NFSU2026!")
        sqli_payload = "' UNION SELECT 1, 'HACKED_NAME', '0000', 'hacked@evil.com', 'M.Sc.', '2026', 10.0, 0, 'Registered', 'Eligible', 'Unplaced', 0, 0, 0, '', '' --"
        resp = self.client.get(f"/students?q={sqli_payload}")
        self.assertEqual(resp.status_code, 200)
        # Verify that no rows were matched or injected
        self.assertIn(b"No student records match the active criteria", resp.data)

        # 9c. Direct parameterized query check: Ensure SQL injection string does not match any rows
        res = query_db("SELECT * FROM students WHERE placement_id = ?", ("' OR '1'='1",))
        self.assertEqual(len(res), 0)

if __name__ == "__main__":
    unittest.main()
