"""
Seed Data Script for NFSU Student Placement Management System (2026-27)
Populates realistic students across 5 programmes, recruitment drives across Categories A+, A, B, C,
attendance records, historical offers, policy exceptions, and role-based test accounts.
"""

from datetime import datetime, date, timedelta
from database import init_db, get_db, execute_db, execute_insert
from security import hash_password, log_audit_event
from policy_engine import classify_category
from config import COURSES, BATCHES

def populate_seed_data():
    init_db()
    
    with get_db() as conn:
        # Check if already seeded
        existing_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if existing_users > 0:
            print("Database already contains data. Skipping initial seeding.")
            return

    print("Seeding NFSU 2026-27 Placement Database...")

    # 1. Insert 35 Realistic Students across 5 Programmes
    students_data = [
        # M.Tech. Computer Science
        ("NFSU26-CS-001", "Rohit Sharma", "+91 9825101001", "rohit.cs@nfsu.ac.in", COURSES[0], "2025–2027", 9.15, 0, "Registered", "Eligible", "Internship + PPO/FTE", 0, 0),
        ("NFSU26-CS-002", "Pooja Patel", "+91 9825101002", "pooja.cs@nfsu.ac.in", COURSES[0], "2025–2027", 8.40, 0, "Registered", "Eligible", "FTE Only", 0, 0),
        ("NFSU26-CS-003", "Aman Verma", "+91 9825101003", "aman.cs@nfsu.ac.in", COURSES[0], "2025–2027", 7.80, 0, "Registered", "Eligible", "Internship Only", 0, 0),
        ("NFSU26-CS-004", "Deepak Joshi", "+91 9825101004", "deepak.cs@nfsu.ac.in", COURSES[0], "2025–2027", 6.90, 1, "Registered", "Eligible", "Unplaced", 0, 0),
        ("NFSU26-CS-005", "Kavita Rao", "+91 9825101005", "kavita.cs@nfsu.ac.in", COURSES[0], "2025–2027", 8.90, 0, "Registered", "Eligible", "FTE Only", 0, 0),
        ("NFSU26-CS-006", "Harshil Dave", "+91 9825101006", "harshil.cs@nfsu.ac.in", COURSES[0], "2025–2027", 5.80, 2, "Registered", "Ineligible", "Unplaced", 0, 0),
        ("NFSU26-CS-007", "Meera Sen", "+91 9825101007", "meera.cs@nfsu.ac.in", COURSES[0], "2025–2027", 7.20, 0, "Deregistered", "Ineligible", "Unplaced", 0, 0),

        # M.Tech. Artificial Intelligence and Data Science
        ("NFSU26-AI-011", "Vikram Rathore", "+91 9825202011", "vikram.ai@nfsu.ac.in", COURSES[1], "2025–2027", 8.65, 0, "Registered", "Eligible", "FTE Only", 0, 0),
        ("NFSU26-AI-012", "Rhea Sengupta", "+91 9825202012", "rhea.ai@nfsu.ac.in", COURSES[1], "2025–2027", 9.40, 0, "Registered", "Eligible", "Internship + PPO/FTE", 0, 0),
        ("NFSU26-AI-013", "Karan Malhotra", "+91 9825202013", "karan.ai@nfsu.ac.in", COURSES[1], "2025–2027", 7.50, 0, "Registered", "Eligible", "Internship Only", 0, 0),
        ("NFSU26-AI-014", "Divya Nair", "+91 9825202014", "divya.ai@nfsu.ac.in", COURSES[1], "2025–2027", 8.10, 0, "Registered", "Eligible", "Unplaced", 0, 0),
        ("NFSU26-AI-015", "Aditya Deshmukh", "+91 9825202015", "aditya.ai@nfsu.ac.in", COURSES[1], "2025–2027", 7.00, 0, "Registered", "Pending Verification", "Unplaced", 0, 0),
        ("NFSU26-AI-016", "Siddharth Jain", "+91 9825202016", "siddharth.ai@nfsu.ac.in", COURSES[1], "2025–2027", 8.25, 0, "Registered", "Eligible", "FTE Only", 0, 0),

        # B.Tech.–M.Tech. Computer Science and Engineering (CS)
        ("NFSU26-ID-021", "Sneha Kulkarni", "+91 9825303021", "sneha.id@nfsu.ac.in", COURSES[2], "2022–2027", 9.10, 0, "Registered", "Eligible", "Unplaced", 0, 0),
        ("NFSU26-ID-022", "Manish Mehra", "+91 9825303022", "manish.id@nfsu.ac.in", COURSES[2], "2022–2027", 8.55, 0, "Registered", "Eligible", "Internship + PPO/FTE", 0, 0),
        ("NFSU26-ID-023", "Shreya Iyer", "+91 9825303023", "shreya.id@nfsu.ac.in", COURSES[2], "2022–2027", 7.90, 0, "Registered", "Eligible", "FTE Only", 0, 0),
        ("NFSU26-ID-024", "Pranav Bansal", "+91 9825303024", "pranav.id@nfsu.ac.in", COURSES[2], "2022–2027", 6.80, 0, "Registered", "Eligible", "Internship Only", 0, 0),
        ("NFSU26-ID-025", "Nidhi Agarwal", "+91 9825303025", "nidhi.id@nfsu.ac.in", COURSES[2], "2022–2027", 8.30, 0, "Registered", "Eligible", "FTE Only", 0, 0),
        ("NFSU26-ID-026", "Tanya Kapoor", "+91 9825303026", "tanya.id@nfsu.ac.in", COURSES[2], "2022–2027", 7.60, 0, "Not Registered", "Ineligible", "Unplaced", 0, 0),

        # M.Sc. Computer Science
        ("NFSU26-MC-031", "Arjun Pandey", "+91 9825404031", "arjun.mc@nfsu.ac.in", COURSES[3], "2025–2027", 8.15, 0, "Registered", "Eligible", "Unplaced", 2, 2), # Penalized for absenteeism
        ("NFSU26-MC-032", "Sonali Ghosh", "+91 9825404032", "sonali.mc@nfsu.ac.in", COURSES[3], "2025–2027", 8.80, 0, "Registered", "Eligible", "FTE Only", 0, 0),
        ("NFSU26-MC-033", "Gaurav Singh", "+91 9825404033", "gaurav.mc@nfsu.ac.in", COURSES[3], "2025–2027", 7.40, 1, "Registered", "Eligible", "Internship Only", 0, 0),
        ("NFSU26-MC-034", "Bhavna Trivedi", "+91 9825404034", "bhavna.mc@nfsu.ac.in", COURSES[3], "2025–2027", 7.95, 0, "Registered", "Eligible", "Unplaced", 0, 0),
        ("NFSU26-MC-035", "Chetan Bhatt", "+91 9825404035", "chetan.mc@nfsu.ac.in", COURSES[3], "2025–2027", 6.50, 0, "Registered", "Eligible", "Unplaced", 0, 0),

        # M.Sc. Digital Forensics and Information Security (M.Sc. DFIS)
        ("NFSU26-DF-041", "Ananya Mishra", "+91 9825505041", "ananya.dfis@nfsu.ac.in", COURSES[4], "2025–2027", 9.50, 0, "Registered", "Eligible", "Internship Only", 0, 0),
        ("NFSU26-DF-042", "Naveen Choudhary", "+91 9825505042", "naveen.dfis@nfsu.ac.in", COURSES[4], "2025–2027", 8.75, 0, "Registered", "Eligible", "Internship + PPO/FTE", 0, 0),
        ("NFSU26-DF-043", "Priyanka Soni", "+91 9825505043", "priyanka.dfis@nfsu.ac.in", COURSES[4], "2025–2027", 8.35, 0, "Registered", "Eligible", "FTE Only", 0, 0),
        ("NFSU26-DF-044", "Varun Thakur", "+91 9825505044", "varun.dfis@nfsu.ac.in", COURSES[4], "2025–2027", 7.90, 0, "Registered", "Eligible", "FTE Only", 0, 0),
        ("NFSU26-DF-045", "Simran Gill", "+91 9825505045", "simran.dfis@nfsu.ac.in", COURSES[4], "2025–2027", 8.60, 0, "Registered", "Eligible", "Unplaced", 0, 0),
        ("NFSU26-DF-046", "Rohan Mehta", "+91 9825505046", "rohan.dfis@nfsu.ac.in", COURSES[4], "2025–2027", 7.30, 0, "Registered", "Pending Verification", "Unplaced", 0, 0),
        ("NFSU26-DF-047", "Swati Saxena", "+91 9825505047", "swati.dfis@nfsu.ac.in", COURSES[4], "2025–2027", 8.90, 0, "Registered", "Eligible", "FTE Only", 0, 0),
    ]

    student_id_map = {}
    for item in students_data:
        s_id = execute_insert(
            """
            INSERT INTO students 
            (placement_id, student_name, mobile_number, email_id, course, batch, cgpa, active_backlogs, registration_status, eligibility_status, placement_status, absenteeism_count, absenteeism_penalty_drives_remaining)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            item
        )
        student_id_map[item[0]] = s_id

    # 2. Insert Recruitment Drives across Categories A+, A, B, C
    drives_data = [
        ("DRV-2026-001", "Microsoft India", "A+", "I+F", 100000.0, "₹1,00,000 / month, 6 months", 26.5, 8.0, 0, ",".join(COURSES), 24, "2026-08-15", "Active", "admin"),
        ("DRV-2026-002", "Palo Alto Networks", "A+", "F", 0.0, "N/A", 22.0, 7.5, 0, ",".join(COURSES), 24, "2026-08-20", "Active", "admin"),
        ("DRV-2026-003", "CrowdStrike Cybersecurity", "A+", "I+F", 80000.0, "₹80,000 / month, 6 months", 18.5, 7.5, 0, f"{COURSES[0]},{COURSES[4]},{COURSES[1]}", 24, "2026-08-28", "Active", "admin"),
        ("DRV-2026-004", "Deloitte Cyber Risk", "A", "F", 0.0, "N/A", 12.5, 7.0, 0, ",".join(COURSES), 24, "2026-09-05", "Active", "admin"),
        ("DRV-2026-005", "CERT-In Cyber Lab", "A", "I", 45000.0, "₹45,000 / month, 6 months", 0.0, 7.5, 0, f"{COURSES[4]},{COURSES[3]}", 24, "2026-09-10", "Active", "admin"),
        ("DRV-2026-006", "Quick Heal Technologies", "B", "F", 0.0, "N/A", 8.5, 6.5, 1, ",".join(COURSES), 24, "2026-09-18", "Active", "admin"),
        ("DRV-2026-007", "TCS Digital", "B", "F", 0.0, "N/A", 7.2, 6.5, 0, ",".join(COURSES), 24, "2026-09-25", "Active", "admin"),
        ("DRV-2026-008", "Infosys Cyber Defense", "C", "F", 0.0, "N/A", 5.5, 6.0, 1, ",".join(COURSES), 24, "2026-10-02", "Active", "admin"),
    ]

    drive_id_map = {}
    for d in drives_data:
        d_id = execute_insert(
            """
            INSERT INTO drives
            (drive_code, company_name, category, offer_type, stipend_amount, stipend_period, fte_package_ctc, min_cgpa, max_backlogs, eligible_courses, acceptance_deadline_hours, drive_date, status, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            d
        )
        drive_id_map[d[0]] = d_id

    # 3. Insert Historical Offers Preserving Full Event Trail
    # A student who accepted an offer has an explicit offer event recorded
    today = date.today()
    offers_data = [
        # Rohit Sharma: Initially received Internship, then PPO -> 26.5 LPA (A+)
        (student_id_map["NFSU26-CS-001"], drive_id_map["DRV-2026-001"], "Microsoft India", "A+", "I+F", 100000.0, "₹1,00,000 / mo", 26.5, 1, "Accepted", "Accepted", (datetime.now() - timedelta(days=20)).isoformat(), "Joined", "2026-08-16", 0, "Approved", "Pre-placement offer confirmed following summer internship", "admin"),

        # Pooja Patel: Deloitte Cyber Risk 12.5 LPA (A)
        (student_id_map["NFSU26-CS-002"], drive_id_map["DRV-2026-004"], "Deloitte Cyber Risk", "A", "F", 0.0, "N/A", 12.5, 0, "Not Applicable", "Accepted", (datetime.now() - timedelta(days=10)).isoformat(), "Pending", "2026-09-06", 0, "Not Required", "FTE accepted; eligible for A+ switch only", "officer"),

        # Aman Verma: CERT-In Internship (I)
        (student_id_map["NFSU26-CS-003"], drive_id_map["DRV-2026-005"], "CERT-In Cyber Lab", "A", "I", 45000.0, "₹45,000 / mo", 0.0, 0, "Not Applicable", "Accepted", (datetime.now() - timedelta(days=8)).isoformat(), "Joined", "2026-09-11", 0, "Approved", "Internship accepted. Eligible for FTE/I+F drives", "officer"),

        # Kavita Rao: Palo Alto Networks 22.0 LPA (A+)
        (student_id_map["NFSU26-CS-005"], drive_id_map["DRV-2026-002"], "Palo Alto Networks", "A+", "F", 0.0, "N/A", 22.0, 0, "Not Applicable", "Accepted", (datetime.now() - timedelta(days=15)).isoformat(), "Pending", "2026-08-22", 0, "Not Required", "Category A+ placement complete; out of placement process", "admin"),

        # Vikram Rathore: Quick Heal 8.5 LPA (B) - Eligible to switch only if new >= 12.75 LPA
        (student_id_map["NFSU26-AI-011"], drive_id_map["DRV-2026-006"], "Quick Heal Technologies", "B", "F", 0.0, "N/A", 8.5, 0, "Not Applicable", "Accepted", (datetime.now() - timedelta(days=7)).isoformat(), "Pending", "2026-09-19", 0, "Not Required", "Category B offer. Switching allowed only if new package >= 1.5x (12.75 LPA)", "officer"),

        # Rhea Sengupta: CrowdStrike I+F 18.5 LPA (A+)
        (student_id_map["NFSU26-AI-012"], drive_id_map["DRV-2026-003"], "CrowdStrike Cybersecurity", "A+", "I+F", 80000.0, "₹80,000 / mo", 18.5, 0, "Offered", "Accepted", (datetime.now() - timedelta(days=12)).isoformat(), "Joined", "2026-08-30", 0, "Approved", "Category A+ I+F accepted; locked from other drives", "admin"),

        # Karan Malhotra: CERT-In Internship (I)
        (student_id_map["NFSU26-AI-013"], drive_id_map["DRV-2026-005"], "CERT-In Cyber Lab", "A", "I", 45000.0, "₹45,000 / mo", 0.0, 0, "Not Applicable", "Accepted", (datetime.now() - timedelta(days=5)).isoformat(), "Joined", "2026-09-12", 0, "Approved", "Accepted 6-month cybersecurity internship", "officer"),

        # Siddharth Jain: TCS Digital 7.2 LPA (B)
        (student_id_map["NFSU26-AI-016"], drive_id_map["DRV-2026-007"], "TCS Digital", "B", "F", 0.0, "N/A", 7.2, 0, "Not Applicable", "Accepted", (datetime.now() - timedelta(days=4)).isoformat(), "Pending", "2026-09-26", 0, "Not Required", "Category B offer. Requires >= 10.8 LPA for subsequent switch", "officer"),

        # Manish Mehra: Microsoft India I+F 26.5 LPA (A+)
        (student_id_map["NFSU26-ID-022"], drive_id_map["DRV-2026-001"], "Microsoft India", "A+", "I+F", 100000.0, "₹1,00,000 / mo", 26.5, 1, "Accepted", "Accepted", (datetime.now() - timedelta(days=22)).isoformat(), "Joined", "2026-08-16", 0, "Approved", "Integrated M.Tech selection in Microsoft", "admin"),

        # Shreya Iyer: Deloitte Cyber Risk 12.5 LPA (A)
        (student_id_map["NFSU26-ID-023"], drive_id_map["DRV-2026-004"], "Deloitte Cyber Risk", "A", "F", 0.0, "N/A", 12.5, 0, "Not Applicable", "Accepted", (datetime.now() - timedelta(days=9)).isoformat(), "Pending", "2026-09-06", 0, "Not Required", "Category A accepted", "officer"),

        # Pranav Bansal: CERT-In Internship (I)
        (student_id_map["NFSU26-ID-024"], drive_id_map["DRV-2026-005"], "CERT-In Cyber Lab", "A", "I", 45000.0, "₹45,000 / mo", 0.0, 0, "Not Applicable", "Accepted", (datetime.now() - timedelta(days=6)).isoformat(), "Joined", "2026-09-12", 0, "Approved", "Internship active", "officer"),

        # Nidhi Agarwal: Quick Heal 8.5 LPA (B)
        (student_id_map["NFSU26-ID-025"], drive_id_map["DRV-2026-006"], "Quick Heal Technologies", "B", "F", 0.0, "N/A", 8.5, 0, "Not Applicable", "Accepted", (datetime.now() - timedelta(days=5)).isoformat(), "Pending", "2026-09-20", 0, "Not Required", "Category B accepted", "officer"),

        # Sonali Ghosh: Deloitte Cyber Risk 12.5 LPA (A)
        (student_id_map["NFSU26-MC-032"], drive_id_map["DRV-2026-004"], "Deloitte Cyber Risk", "A", "F", 0.0, "N/A", 12.5, 0, "Not Applicable", "Accepted", (datetime.now() - timedelta(days=10)).isoformat(), "Pending", "2026-09-07", 0, "Not Required", "M.Sc. CS selection", "officer"),

        # Gaurav Singh: CERT-In Internship (I)
        (student_id_map["NFSU26-MC-033"], drive_id_map["DRV-2026-005"], "CERT-In Cyber Lab", "A", "I", 45000.0, "₹45,000 / mo", 0.0, 0, "Not Applicable", "Accepted", (datetime.now() - timedelta(days=7)).isoformat(), "Joined", "2026-09-12", 0, "Approved", "Internship secured", "officer"),

        # Ananya Mishra: CERT-In Internship (I) - M.Sc. DFIS topper
        (student_id_map["NFSU26-DF-041"], drive_id_map["DRV-2026-005"], "CERT-In Cyber Lab", "A", "I", 45000.0, "₹45,000 / mo", 0.0, 0, "Not Applicable", "Accepted", (datetime.now() - timedelta(days=7)).isoformat(), "Joined", "2026-09-12", 0, "Approved", "DFIS student accepted CERT-In digital forensics internship", "coord_dfis"),

        # Naveen Choudhary: CrowdStrike I+F 18.5 LPA (A+)
        (student_id_map["NFSU26-DF-042"], drive_id_map["DRV-2026-003"], "CrowdStrike Cybersecurity", "A+", "I+F", 80000.0, "₹80,000 / mo", 18.5, 0, "Accepted", "Accepted", (datetime.now() - timedelta(days=11)).isoformat(), "Joined", "2026-08-30", 0, "Approved", "CrowdStrike Incident Responder offer", "admin"),

        # Priyanka Soni: Palo Alto Networks 22.0 LPA (A+)
        (student_id_map["NFSU26-DF-043"], drive_id_map["DRV-2026-002"], "Palo Alto Networks", "A+", "F", 0.0, "N/A", 22.0, 0, "Not Applicable", "Accepted", (datetime.now() - timedelta(days=14)).isoformat(), "Pending", "2026-08-22", 0, "Not Required", "SOC Analyst role secured", "admin"),

        # Varun Thakur: Quick Heal 8.5 LPA (B)
        (student_id_map["NFSU26-DF-044"], drive_id_map["DRV-2026-006"], "Quick Heal Technologies", "B", "F", 0.0, "N/A", 8.5, 0, "Not Applicable", "Accepted", (datetime.now() - timedelta(days=6)).isoformat(), "Pending", "2026-09-20", 0, "Not Required", "Malware Analyst role", "officer"),

        # Swati Saxena: Deloitte Cyber Risk 12.5 LPA (A)
        (student_id_map["NFSU26-DF-047"], drive_id_map["DRV-2026-004"], "Deloitte Cyber Risk", "A", "F", 0.0, "N/A", 12.5, 0, "Not Applicable", "Accepted", (datetime.now() - timedelta(days=9)).isoformat(), "Pending", "2026-09-07", 0, "Not Required", "Cyber forensics consultant offer", "officer"),

        # Pending Offer for Deepak Joshi (TCS Digital, deadline 24h)
        (student_id_map["NFSU26-CS-004"], drive_id_map["DRV-2026-007"], "TCS Digital", "B", "F", 0.0, "N/A", 7.2, 0, "Not Applicable", "Pending", (datetime.now() + timedelta(hours=14)).isoformat(), "Pending", "2026-10-12", 0, "Not Required", "Offer letter dispatched; awaiting candidate acceptance", "officer"),
    ]

    for off in offers_data:
        execute_insert(
            """
            INSERT INTO offers
            (student_id, drive_id, company_name, category, offer_type, stipend_amount, stipend_period, fte_package_ctc, is_ppo, ppo_status, offer_acceptance, deadline_at, joining_status, offer_date, is_off_campus, noc_status, remarks, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            off
        )

    # 4. Insert Attendance Tracking & Absenteeism Records
    attendance_records = [
        # Arjun Pandey missed Pre-Placement Talk and Test without excuse -> penalty applied
        (drive_id_map["DRV-2026-006"], student_id_map["NFSU26-MC-031"], "Pre-Placement Talk", "Absent", "Did not attend mandatory PPT without prior intimation", "officer"),
        (drive_id_map["DRV-2026-007"], student_id_map["NFSU26-MC-031"], "Aptitude/Tech Test", "Absent", "Unexcused absence from online test round; flagged for 3 drives penalty", "officer"),
        
        # Rohit Sharma attended all rounds
        (drive_id_map["DRV-2026-001"], student_id_map["NFSU26-CS-001"], "Pre-Placement Talk", "Present", "Verified attendance", "officer"),
        (drive_id_map["DRV-2026-001"], student_id_map["NFSU26-CS-001"], "Technical Interview", "Present", "Cleared round 1 and 2", "officer"),
        
        # Sneha Kulkarni attended Palo Alto PPT
        (drive_id_map["DRV-2026-002"], student_id_map["NFSU26-ID-021"], "Pre-Placement Talk", "Present", "Present", "officer"),
    ]

    for att in attendance_records:
        execute_insert(
            """
            INSERT INTO drive_attendance
            (drive_id, student_id, activity_type, attendance_status, remarks, recorded_by)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            att
        )

    # 5. Insert Policy Exception Example
    execute_insert(
        """
        INSERT INTO policy_exceptions
        (student_id, drive_id, exception_type, justification, status, approved_by)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            student_id_map["NFSU26-CS-003"],
            drive_id_map["DRV-2026-004"],
            "Switching Rule Override",
            "Emergency special project permission approved by Dean Academic and Placement Committee",
            "Approved",
            "admin"
        )
    )

    # 6. Insert User Accounts for All 5 Roles
    users_data = [
        # Placement Administrator (Full Admin Privilege)
        ("admin", "placement.admin@nfsu.ac.in", hash_password("Admin@NFSU2026!"), "Placement Administrator", None, None, None),
        
        # Placement Officer (Drive operations, offers, attendance)
        ("officer", "placement.officer@nfsu.ac.in", hash_password("Officer@NFSU2026!"), "Placement Officer", None, None, None),
        
        # Course Coordinator for M.Sc. DFIS
        ("coord_dfis", "coord.dfis@nfsu.ac.in", hash_password("Coord@NFSU2026!"), "Course Coordinator", COURSES[4], None, None),
        
        # Course Coordinator for M.Tech CS
        ("coord_cs", "coord.cs@nfsu.ac.in", hash_password("Coord@NFSU2026!"), "Course Coordinator", COURSES[0], None, None),
        
        # Recruiter for CrowdStrike
        ("recruiter_crowdstrike", "recruiter@crowdstrike.com", hash_password("Recruiter@NFSU2026!"), "Recruiter", None, "CrowdStrike Cybersecurity", None),
        
        # Recruiter for Palo Alto
        ("recruiter_paloalto", "recruiter@paloaltonetworks.com", hash_password("Recruiter@NFSU2026!"), "Recruiter", None, "Palo Alto Networks", None),
        
        # Student 1: Rohit Sharma (Category A+ Placed)
        ("student_rohit", "rohit.cs@nfsu.ac.in", hash_password("Student@NFSU2026!"), "Student", None, None, student_id_map["NFSU26-CS-001"]),
        
        # Student 2: Ananya Mishra (Internship Only Placed)
        ("student_ananya", "ananya.dfis@nfsu.ac.in", hash_password("Student@NFSU2026!"), "Student", None, None, student_id_map["NFSU26-DF-041"]),
        
        # Student 3: Vikram Rathore (Category B Placed)
        ("student_vikram", "vikram.ai@nfsu.ac.in", hash_password("Student@NFSU2026!"), "Student", None, None, student_id_map["NFSU26-AI-011"]),
        
        # Student 4: Sneha Kulkarni (Unplaced)
        ("student_sneha", "sneha.id@nfsu.ac.in", hash_password("Student@NFSU2026!"), "Student", None, None, student_id_map["NFSU26-ID-021"]),
        
        # Student 5: Arjun Pandey (Absenteeism Penalized)
        ("student_arjun", "arjun.mc@nfsu.ac.in", hash_password("Student@NFSU2026!"), "Student", None, None, student_id_map["NFSU26-MC-031"]),
    ]

    for u in users_data:
        execute_insert(
            """
            INSERT INTO users 
            (username, email, password_hash, role, assigned_course, recruiter_company, student_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            u
        )

    # 7. Initialize Tamper-Evident Audit Blockchain Log with Initial Events
    log_audit_event(
        actor_username="SYSTEM",
        actor_role="SYSTEM",
        action="DATABASE_INIT",
        entity_type="Database",
        entity_id="SCHEMA_V1",
        details="Genesis block initialized. NFSU 2026-27 Placement System tables established."
    )
    log_audit_event(
        actor_username="admin",
        actor_role="Placement Administrator",
        action="DATA_SEED",
        entity_type="Students",
        entity_id="BATCH_2026",
        details="Registered 31 baseline candidate profiles across 5 NFSU academic programmes."
    )
    log_audit_event(
        actor_username="admin",
        actor_role="Placement Administrator",
        action="DRIVE_PUBLISH",
        entity_type="Drive",
        entity_id="DRV-2026-001",
        details="Published Microsoft India recruitment drive (A+, ₹26.5 LPA, I+F)."
    )
    log_audit_event(
        actor_username="officer",
        actor_role="Placement Officer",
        action="OFFER_RECORDED",
        entity_type="Offer",
        entity_id="OFFER-ROHIT-MS",
        details="Confirmed and verified Microsoft India offer of ₹26.5 LPA for Rohit Sharma."
    )

    print("NFSU 2026-27 Placement Database seeded successfully!")

if __name__ == "__main__":
    populate_seed_data()
