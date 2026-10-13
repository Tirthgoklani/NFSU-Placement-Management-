"""
Unit Tests for NFSU 2026-27 Placement Policy Rule Engine
Validates all switching rules, category classifications, offer-type constraints,
academic criteria, and absenteeism penalties.
"""

import unittest
from policy_engine import classify_category, calculate_placement_status, evaluate_eligibility

class TestPolicyEngine(unittest.TestCase):

    def setUp(self):
        self.base_student = {
            "placement_id": "NFSU26-TEST-01",
            "course": "M.Tech. Computer Science (M.Tech. CS)",
            "registration_status": "Registered",
            "eligibility_status": "Eligible",
            "cgpa": 8.5,
            "active_backlogs": 0,
            "absenteeism_penalty_drives_remaining": 0
        }
        self.base_drive = {
            "company_name": "Tech Corp",
            "category": "A",
            "offer_type": "F",
            "fte_package_ctc": 12.0,
            "min_cgpa": 7.0,
            "max_backlogs": 0,
            "eligible_courses": "M.Tech. Computer Science (M.Tech. CS),M.Sc. Computer Science (M.Sc. CS)"
        }

    # 1. Category Classification Tests
    def test_classify_category(self):
        self.assertEqual(classify_category(22.5), "A+")
        self.assertEqual(classify_category(16.0), "A+")
        self.assertEqual(classify_category(15.9), "A")
        self.assertEqual(classify_category(10.0), "A")
        self.assertEqual(classify_category(9.9), "B")
        self.assertEqual(classify_category(6.0), "B")
        self.assertEqual(classify_category(5.9), "C")
        self.assertEqual(classify_category(3.5), "C")
        self.assertEqual(classify_category(0.0), "C")

    # 2. Placement Status Derivation Tests
    def test_calculate_placement_status(self):
        self.assertEqual(calculate_placement_status([]), "Unplaced")
        self.assertEqual(calculate_placement_status([{"offer_type": "I", "ppo_status": "Not Applicable"}]), "Internship Only")
        self.assertEqual(calculate_placement_status([{"offer_type": "F", "ppo_status": "Not Applicable"}]), "FTE Only")
        self.assertEqual(calculate_placement_status([{"offer_type": "I+F", "ppo_status": "Accepted"}]), "Internship + PPO/FTE")
        # Both I and F accepted
        self.assertEqual(calculate_placement_status([
            {"offer_type": "I", "ppo_status": "Not Applicable"},
            {"offer_type": "F", "ppo_status": "Not Applicable"}
        ]), "Internship + PPO/FTE")
        # I accepted with PPO accepted
        self.assertEqual(calculate_placement_status([
            {"offer_type": "I", "ppo_status": "Accepted"}
        ]), "Internship + PPO/FTE")

    # 3. Registration & Verification Checks
    def test_unregistered_student_blocked(self):
        student = dict(self.base_student, registration_status="Deregistered")
        res = evaluate_eligibility(student, self.base_drive)
        self.assertEqual(res["decision"], "Blocked")
        self.assertFalse(res["can_apply"])
        self.assertIn("Registration check failed", res["summary"])

    def test_ineligible_student_blocked(self):
        student = dict(self.base_student, eligibility_status="Ineligible")
        res = evaluate_eligibility(student, self.base_drive)
        self.assertEqual(res["decision"], "Blocked")
        self.assertIn("Institutional check failed", res["summary"])

    def test_pending_verification_referred(self):
        student = dict(self.base_student, eligibility_status="Pending Verification")
        res = evaluate_eligibility(student, self.base_drive)
        self.assertEqual(res["decision"], "Referred for Manual Review")
        self.assertTrue(res["needs_review"])

    # 4. Absenteeism Penalties & Waiver Exceptions
    def test_absenteeism_penalty_blocks_student(self):
        student = dict(self.base_student, absenteeism_penalty_drives_remaining=2)
        res = evaluate_eligibility(student, self.base_drive)
        self.assertEqual(res["decision"], "Blocked")
        self.assertIn("Disciplinary penalty active", res["summary"])

    def test_absenteeism_penalty_allowed_with_waiver(self):
        student = dict(self.base_student, absenteeism_penalty_drives_remaining=2)
        exceptions = [{"exception_type": "Absenteeism Waiver", "status": "Approved"}]
        res = evaluate_eligibility(student, self.base_drive, exceptions=exceptions)
        self.assertEqual(res["decision"], "Allowed")
        self.assertTrue(res["can_apply"])

    # 5. Academic Criteria
    def test_cgpa_below_minimum_blocked(self):
        student = dict(self.base_student, cgpa=6.5) # drive min is 7.0
        res = evaluate_eligibility(student, self.base_drive)
        self.assertEqual(res["decision"], "Blocked")
        self.assertIn("CGPA requirement not met", res["summary"])

    def test_backlogs_exceeding_threshold_blocked(self):
        student = dict(self.base_student, active_backlogs=2) # drive max is 0
        res = evaluate_eligibility(student, self.base_drive)
        self.assertEqual(res["decision"], "Blocked")
        self.assertIn("Backlog limit exceeded", res["summary"])

    def test_course_mismatch_blocked(self):
        student = dict(self.base_student, course="M.Sc. Digital Forensics and Information Security (M.Sc. DFIS)")
        res = evaluate_eligibility(student, self.base_drive)
        self.assertEqual(res["decision"], "Blocked")
        self.assertIn("Programme mismatch", res["summary"])

    # 6. Category A+ Switching Rules (No switching; out of placement process)
    def test_category_a_plus_placed_blocked(self):
        existing_offers = [{
            "company_name": "Microsoft",
            "category": "A+",
            "offer_type": "F",
            "fte_package_ctc": 24.0,
            "offer_acceptance": "Accepted"
        }]
        target_drive = dict(self.base_drive, category="A+", fte_package_ctc=30.0)
        res = evaluate_eligibility(self.base_student, target_drive, existing_offers=existing_offers)
        self.assertEqual(res["decision"], "Blocked")
        self.assertIn("No switching allowed", res["summary"])

    # 7. Category A Switching Rules (Switching allowed ONLY to A+ category >= 16 LPA)
    def test_category_a_placed_blocked_for_a_or_b(self):
        existing_offers = [{
            "company_name": "Deloitte",
            "category": "A",
            "offer_type": "F",
            "fte_package_ctc": 12.0,
            "offer_acceptance": "Accepted"
        }]
        # Trying to apply to another Category A drive (14 LPA) -> Blocked
        drive_a = dict(self.base_drive, category="A", fte_package_ctc=14.0)
        res = evaluate_eligibility(self.base_student, drive_a, existing_offers=existing_offers)
        self.assertEqual(res["decision"], "Blocked")
        self.assertIn("Category A holders can only switch to Category A+", res["summary"])

    def test_category_a_placed_allowed_for_a_plus(self):
        existing_offers = [{
            "company_name": "Deloitte",
            "category": "A",
            "offer_type": "F",
            "fte_package_ctc": 12.0,
            "offer_acceptance": "Accepted"
        }]
        # Trying to apply to Category A+ drive (20 LPA) -> Allowed
        drive_a_plus = dict(self.base_drive, company_name="Google", category="A+", fte_package_ctc=20.0)
        res = evaluate_eligibility(self.base_student, drive_a_plus, existing_offers=existing_offers)
        self.assertEqual(res["decision"], "Allowed")
        self.assertTrue(res["can_apply"])

    # 8. Category B 1.5x Multiplier Rule
    def test_category_b_below_1_5x_blocked(self):
        existing_offers = [{
            "company_name": "Quick Heal",
            "category": "B",
            "offer_type": "F",
            "fte_package_ctc": 8.0,
            "offer_acceptance": "Accepted"
        }]
        # 1.5 * 8.0 = 12.0 LPA. Drive offering 10.0 LPA -> Blocked
        drive = dict(self.base_drive, category="A", fte_package_ctc=10.0)
        res = evaluate_eligibility(self.base_student, drive, existing_offers=existing_offers)
        self.assertEqual(res["decision"], "Blocked")
        self.assertIn("less than 1.5x of existing Category B package", res["summary"])

    def test_category_b_above_1_5x_allowed(self):
        existing_offers = [{
            "company_name": "Quick Heal",
            "category": "B",
            "offer_type": "F",
            "fte_package_ctc": 8.0,
            "offer_acceptance": "Accepted"
        }]
        # 1.5 * 8.0 = 12.0 LPA. Drive offering 12.5 LPA -> Allowed
        drive = dict(self.base_drive, category="A", fte_package_ctc=12.5)
        res = evaluate_eligibility(self.base_student, drive, existing_offers=existing_offers)
        self.assertEqual(res["decision"], "Allowed")
        self.assertTrue(res["can_apply"])

    # 9. Category C Lateral Switching Prohibited
    def test_category_c_lateral_switch_blocked(self):
        existing_offers = [{
            "company_name": "Startup Alpha",
            "category": "C",
            "offer_type": "F",
            "fte_package_ctc": 4.5,
            "offer_acceptance": "Accepted"
        }]
        # Target drive also Category C (5.0 LPA) -> Blocked
        drive_c = dict(self.base_drive, category="C", fte_package_ctc=5.0)
        res = evaluate_eligibility(self.base_student, drive_c, existing_offers=existing_offers)
        self.assertEqual(res["decision"], "Blocked")
        self.assertIn("Lateral switching within Category C is prohibited", res["summary"])

    def test_category_c_to_higher_category_allowed(self):
        existing_offers = [{
            "company_name": "Startup Alpha",
            "category": "C",
            "offer_type": "F",
            "fte_package_ctc": 4.5,
            "offer_acceptance": "Accepted"
        }]
        # Target drive Category B (7.5 LPA) -> Allowed
        drive_b = dict(self.base_drive, category="B", fte_package_ctc=7.5)
        res = evaluate_eligibility(self.base_student, drive_b, existing_offers=existing_offers)
        self.assertEqual(res["decision"], "Allowed")
        self.assertTrue(res["can_apply"])

    # 10. Offer-Type Restrictions: Internship Only (I) & I+F
    def test_internship_holder_cannot_apply_another_internship(self):
        existing_offers = [{
            "company_name": "CERT-In",
            "category": "A",
            "offer_type": "I",
            "fte_package_ctc": 0.0,
            "offer_acceptance": "Accepted"
        }]
        # Target drive is another Internship only (I) -> Blocked
        drive_i = dict(self.base_drive, company_name="DRDO", offer_type="I", fte_package_ctc=0.0)
        res = evaluate_eligibility(self.base_student, drive_i, existing_offers=existing_offers)
        self.assertEqual(res["decision"], "Blocked")
        self.assertIn("Cannot apply for another internship-only role", res["summary"])

    def test_internship_holder_can_apply_fte(self):
        existing_offers = [{
            "company_name": "CERT-In",
            "category": "A",
            "offer_type": "I",
            "fte_package_ctc": 0.0,
            "offer_acceptance": "Accepted"
        }]
        # Target drive is FTE -> Allowed
        drive_f = dict(self.base_drive, offer_type="F", fte_package_ctc=12.0)
        res = evaluate_eligibility(self.base_student, drive_f, existing_offers=existing_offers)
        self.assertEqual(res["decision"], "Allowed")
        self.assertTrue(res["can_apply"])

    def test_i_plus_f_holder_locked_out(self):
        existing_offers = [{
            "company_name": "Microsoft",
            "category": "A+",
            "offer_type": "I+F",
            "fte_package_ctc": 26.5,
            "offer_acceptance": "Accepted"
        }]
        # Target drive is any other company -> Blocked
        drive = dict(self.base_drive, company_name="Amazon", category="A+", fte_package_ctc=28.0)
        res = evaluate_eligibility(self.base_student, drive, existing_offers=existing_offers)
        self.assertEqual(res["decision"], "Blocked")
        self.assertIn("Already secured I+F offer", res["summary"])

if __name__ == "__main__":
    unittest.main()
