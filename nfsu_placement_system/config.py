import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
BACKUP_DIR = DATA_DIR / "backups"

DATA_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "nfsu_placement.db"

# Security Configurations
SECRET_KEY = os.environ.get("NFSU_SECRET_KEY", "nfsu_sec_key_2026_placement_cell_forensics_auth_token_99x")
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
PERMANENT_SESSION_LIFETIME_MINUTES = 60
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15

# NFSU Academic & Placement 2026-27 Constants
COURSES = [
    "M.Tech. Computer Science (M.Tech. CS)",
    "M.Tech. Artificial Intelligence and Data Science (M.Tech. AIDS)",
    "B.Tech.–M.Tech. Computer Science and Engineering (CS)",
    "M.Sc. Computer Science (M.Sc. CS)",
    "M.Sc. Digital Forensics and Information Security (M.Sc. DFIS)"
]

BATCHES = [
    "2025–2027",
    "2022–2027",  # Integrated Dual Degree
    "2024–2026"
]

ROLES = [
    "Placement Administrator",
    "Placement Officer",
    "Course Coordinator",
    "Recruiter",
    "Student"
]

OFFER_TYPES = {
    "I": "Internship only",
    "F": "FTE only",
    "I+F": "Internship + PPO/FTE"
}

# Policy Classification Thresholds (in LPA)
CTC_THRESHOLDS = {
    "A+": 16.0,   # >= 16 LPA
    "A": 10.0,    # 10 to 16 LPA
    "B": 6.0,     # 6 to 10 LPA
    "C": 0.0      # < 6 LPA
}

CATEGORY_B_MULTIPLIER = 1.5  # New package must be at least 1.5x existing package
ABSENTEEISM_PENALTY_DRIVES = 3
DEFAULT_OFFER_DEADLINE_HOURS = 24
