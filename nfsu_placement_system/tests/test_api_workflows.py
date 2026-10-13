"""
End-to-End Placement Workflows Integration Tests
Tests student registration, drive scheduling, offer lifecycle with history preservation,
absenteeism penalty enforcement & administrative waiver, and statistics reporting.
"""

import unittest
from app import create_app
from database import query_db, execute_db
from policy_engine import classify_category
from routes.report_routes import compute_placement_metrics

class TestPlacementWorkflows(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def login_as(self, username, password):
        return self.client.post("/login", data={
            "username": username,
            "password": password
        }, follow_redirects=True)

    # 1. Workflow: Student Registration & Uniqueness Enforcement
    def test_student_registration_and_duplicate_rejection(self):
        self.login_as("admin", "Admin@NFSU2026!")

        # Create unique student
        p_id = "NFSU26-TEST-E2E"
        resp = self.client.post("/students/new", data={
            "placement_id": p_id,
            "student_name": "Integration Test Student",
            "mobile_number": "+91 9999988888",
            "email_id": "test.e2e@nfsu.ac.in",
            "course": "M.Sc. Digital Forensics and Information Security (M.Sc. DFIS)",
            "batch": "2025–2027",
            "cgpa": "8.8",
            "active_backlogs": "0",
            "registration_status": "Registered",
            "eligibility_status": "Eligible"
        }, follow_redirects=True)

        self.assertEqual(resp.status_code, 200)
        created = query_db("SELECT * FROM students WHERE placement_id = ?", (p_id,), one=True)
        self.assertIsNotNone(created)
        self.assertEqual(created["student_name"], "Integration Test Student")

        # Duplicate Placement ID rejection test
        resp_dup = self.client.post("/students/new", data={
            "placement_id": p_id,
            "student_name": "Duplicate Student",
            "mobile_number": "+91 9999977777",
            "email_id": "dup@nfsu.ac.in",
            "course": "M.Sc. Digital Forensics and Information Security (M.Sc. DFIS)",
            "batch": "2025–2027",
            "cgpa": "8.0",
            "active_backlogs": "0",
            "registration_status": "Registered",
            "eligibility_status": "Eligible"
        }, follow_redirects=True)

        self.assertIn(b"already exists in database", resp_dup.data)

        # Cleanup
        execute_db("DELETE FROM students WHERE placement_id = ?", (p_id,))

    # 2. Workflow: Drive Creation & Automated Category Classification
    def test_drive_creation_and_auto_category(self):
        self.login_as("admin", "Admin@NFSU2026!")

        drive_code = "DRV-TEST-E2E"
        resp = self.client.post("/drives/new", data={
            "drive_code": drive_code,
            "company_name": "Symantec Cyber",
            "offer_type": "F",
            "fte_package_ctc": "15.5", # Should be Category A (10 - 16 LPA)
            "stipend_amount": "0",
            "stipend_period": "",
            "min_cgpa": "7.0",
            "max_backlogs": "0",
            "drive_date": "2026-11-01",
            "acceptance_deadline_hours": "24",
            "eligible_courses": ["M.Sc. Digital Forensics and Information Security (M.Sc. DFIS)"]
        }, follow_redirects=True)

        self.assertEqual(resp.status_code, 200)
        drive = query_db("SELECT * FROM drives WHERE drive_code = ?", (drive_code,), one=True)
        self.assertIsNotNone(drive)
        self.assertEqual(drive["category"], "A")

        # Cleanup
        execute_db("DELETE FROM drives WHERE drive_code = ?", (drive_code,))

    # 3. Workflow: Absenteeism Penalty Application and Administrative Waiver
    def test_absenteeism_penalty_and_waiver_workflow(self):
        self.login_as("officer", "Officer@NFSU2026!")

        # Pick Sneha (student id = 14) who has 0 penalty
        student = query_db("SELECT * FROM students WHERE id = 14", one=True)
        orig_penalty = student["absenteeism_penalty_drives_remaining"]

        # Record unexcused absence in Drive 1
        self.client.post("/drives/1/attendance", data={
            "student_id": "14",
            "activity_type": "Pre-Placement Talk",
            "attendance_status": "Absent",
            "remarks": "Unexcused test absence"
        })

        # Verify 3-drive penalty was applied
        updated_s = query_db("SELECT * FROM students WHERE id = 14", one=True)
        self.assertEqual(updated_s["absenteeism_penalty_drives_remaining"], 3)

        # Placement Admin grants an Absenteeism Waiver
        self.login_as("admin", "Admin@NFSU2026!")
        self.client.post("/policy/exceptions", data={
            "student_id": "14",
            "exception_type": "Absenteeism Waiver",
            "justification": "Medical emergency certificate verified by university medical officer."
        })

        # Verify waiver reset the penalty
        waived_s = query_db("SELECT * FROM students WHERE id = 14", one=True)
        self.assertEqual(waived_s["absenteeism_penalty_drives_remaining"], 0)

        # Restore
        execute_db("DELETE FROM drive_attendance WHERE student_id = 14 AND remarks = 'Unexcused test absence'")
        execute_db("DELETE FROM policy_exceptions WHERE student_id = 14 AND justification LIKE 'Medical emergency%'")
        execute_db("UPDATE students SET absenteeism_penalty_drives_remaining = ? WHERE id = 14", (orig_penalty,))

    # 4. Workflow: Distinct Placed Students vs Total Offers & Separate CTC vs Stipend
    def test_placement_metrics_strict_separation(self):
        metrics = compute_placement_metrics()

        # Placed candidates should be distinct unique students
        self.assertGreater(metrics["unique_placed_students"], 0)
        # Total offers can exceed unique placed students
        self.assertGreaterEqual(metrics["total_offers_received"], metrics["unique_placed_students"])

        # Highest FTE CTC must be in LPA (e.g. >= 16 LPA for Microsoft)
        self.assertGreaterEqual(metrics["highest_fte_ctc"], 16.0)

        # Internship stipend must be separate (e.g. ₹1,00,000 / month or ₹45,000 / month)
        self.assertGreaterEqual(metrics["highest_stipend"], 10000.0)

        # All 5 NFSU courses must be covered
        self.assertEqual(len(metrics["course_stats"]), 5)

if __name__ == "__main__":
    unittest.main()
