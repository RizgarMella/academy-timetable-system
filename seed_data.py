"""Comprehensive seed data generator for the training academy timetabling system.

Populates the database with realistic lecturers, courses, modules, classrooms,
qualifications, course runs, resits, rules, and availability data.
"""

import random
import datetime
from datetime import date, timedelta

from models import (
    Lecturer, LecturerAvailability, Course, Module, CourseRun,
    AcademicYear, Classroom, ClassroomAvailability,
    LecturerQualification, Rule, Resit,
)

random.seed(42)


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _weekdays_between(start, end):
    """Return list of weekday dates between start and end inclusive."""
    days = []
    d = start
    while d <= end:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return days


def _fridays_between(start, end):
    """Return all Fridays between start and end inclusive."""
    days = []
    d = start
    while d <= end:
        if d.weekday() == 4:
            days.append(d)
        d += timedelta(days=1)
    return days


def _add_weeks(start, weeks):
    """Return start + weeks * 7 days."""
    return start + timedelta(weeks=weeks)


# ---------------------------------------------------------------------------
# Student name pool for resits
# ---------------------------------------------------------------------------

_FIRST_NAMES = [
    "Oliver", "Amelia", "Noah", "Isla", "Liam", "Ava", "Ethan", "Mia",
    "James", "Charlotte", "William", "Sophia", "Henry", "Emily", "Lucas",
    "Ella", "Benjamin", "Grace", "Jack", "Lily", "Alexander", "Chloe",
    "Daniel", "Hannah", "Matthew", "Zara", "Samuel", "Freya", "Oscar",
    "Phoebe", "Harry", "Ruby", "George", "Evie", "Charlie", "Isabelle",
    "Thomas", "Daisy", "Leo", "Rosie",
]

_LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Wilson", "Moore", "Taylor", "Anderson", "Thomas", "Jackson",
    "White", "Harris", "Martin", "Thompson", "Robinson", "Clark", "Lewis",
    "Walker", "Hall", "Young", "King", "Wright", "Lopez", "Hill", "Scott",
    "Green", "Adams", "Baker", "Nelson", "Carter", "Mitchell", "Perez",
    "Roberts", "Turner", "Phillips", "Campbell",
]


def _random_student_name():
    return f"{random.choice(_FIRST_NAMES)} {random.choice(_LAST_NAMES)}"


# ---------------------------------------------------------------------------
# check_if_seeded
# ---------------------------------------------------------------------------

def check_if_seeded(session):
    """Return True if the database already contains seed data."""
    return session.query(AcademicYear).count() > 0


# ---------------------------------------------------------------------------
# seed_all
# ---------------------------------------------------------------------------

def seed_all(session):
    """Populate the database with comprehensive, realistic seed data.

    Uses random.seed(42) for reproducibility. After seeding, runs the solver
    for the first academic year to pre-populate the schedule.

    Args:
        session: A SQLAlchemy session.
    """
    random.seed(42)

    if check_if_seeded(session):
        return

    # -----------------------------------------------------------------------
    # 1. Academic Years
    # -----------------------------------------------------------------------
    academic_years = [
        AcademicYear(
            label="2025-2026",
            start_date=date(2025, 9, 1),
            end_date=date(2026, 7, 31),
        ),
        AcademicYear(
            label="2026-2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 7, 31),
        ),
        AcademicYear(
            label="2027-2028",
            start_date=date(2027, 9, 1),
            end_date=date(2028, 7, 31),
        ),
    ]
    session.add_all(academic_years)
    session.flush()

    ay_map = {ay.label: ay for ay in academic_years}

    # -----------------------------------------------------------------------
    # 2. Lecturers (20)
    # -----------------------------------------------------------------------
    lecturers_data = [
        # (name, email, max_weekly_hours, max_consecutive_days, prep_time, marking_per_student, wind_down)
        ("Dr Sarah Chen", "s.chen@academy.ac.uk", 25, 5, 4.0, 0.5, 2.0),
        ("Prof Marcus Williams", "m.williams@academy.ac.uk", 20, 4, 6.0, 0.7, 3.0),
        ("Dr Priya Patel", "p.patel@academy.ac.uk", 28, 5, 3.0, 0.4, 2.0),
        ("James O'Brien", "j.obrien@academy.ac.uk", 30, 5, 2.0, 0.3, 1.0),
        ("Dr Fatima Al-Rashid", "f.alrashid@academy.ac.uk", 22, 4, 5.0, 0.6, 3.0),
        ("Michael Torres", "m.torres@academy.ac.uk", 26, 5, 3.0, 0.5, 2.0),
        ("Dr Emma Richardson", "e.richardson@academy.ac.uk", 24, 5, 4.0, 0.5, 2.0),
        ("Robert Kim", "r.kim@academy.ac.uk", 28, 5, 3.0, 0.4, 2.0),
        ("Dr Aisha Mohammed", "a.mohammed@academy.ac.uk", 20, 4, 5.0, 0.8, 4.0),
        ("Thomas Blake", "t.blake@academy.ac.uk", 30, 5, 2.0, 0.3, 1.0),
        ("Dr Yuki Tanaka", "y.tanaka@academy.ac.uk", 24, 5, 4.0, 0.6, 3.0),
        ("Sophie Anderson", "s.anderson@academy.ac.uk", 26, 5, 3.0, 0.4, 2.0),
        ("Dr Kwame Asante", "k.asante@academy.ac.uk", 22, 4, 5.0, 0.7, 3.0),
        ("Laura Martinez", "l.martinez@academy.ac.uk", 28, 5, 3.0, 0.5, 2.0),
        ("Dr Ravi Sharma", "r.sharma@academy.ac.uk", 18, 3, 6.0, 0.8, 4.0),
        ("Claire Dubois", "c.dubois@academy.ac.uk", 26, 5, 3.0, 0.4, 2.0),
        ("Dr Ben Carter", "b.carter@academy.ac.uk", 24, 5, 4.0, 0.5, 2.0),
        ("Nadia Volkov", "n.volkov@academy.ac.uk", 28, 5, 2.0, 0.3, 1.0),
        ("Dr Olumide Adeyemi", "o.adeyemi@academy.ac.uk", 22, 4, 5.0, 0.6, 3.0),
        ("Hannah Cooper", "h.cooper@academy.ac.uk", 30, 5, 2.0, 0.4, 2.0),
    ]

    lecturers = []
    for name, email, mwh, mcd, pt, mps, wd in lecturers_data:
        lec = Lecturer(
            name=name,
            email=email,
            max_weekly_hours=mwh,
            max_consecutive_days=mcd,
            prep_time_hours=pt,
            marking_hours_per_student=mps,
            wind_down_hours=wd,
        )
        session.add(lec)
        lecturers.append(lec)
    session.flush()

    # Build a name->object lookup
    lec_by_name = {l.name: l for l in lecturers}

    # -----------------------------------------------------------------------
    # 3. Courses & Modules
    # -----------------------------------------------------------------------
    courses_spec = [
        {
            "code": "CYB-101",
            "name": "Cyber Security Fundamentals",
            "description": "Foundation course covering core cyber security concepts, threat landscapes, and defensive techniques.",
            "total_weeks": 12,
            "max_class": 20,
            "modules": [
                ("CYB-101-01", "Security Principles", 12, False, 2),
                ("CYB-101-02", "Network Security", 16, False, 3),
                ("CYB-101-03", "Threat Modelling", 12, False, 2),
                ("CYB-101-04", "Cryptography Basics", 16, False, 3),
                ("CYB-101-05", "Ethical Hacking Intro", 20, True, 3),
                ("CYB-101-06", "Incident Response", 12, False, 2),
                ("CYB-101-07", "Security Auditing", 16, True, 3),
                ("CYB-101-08", "Cyber Law & Compliance", 8, False, None),
            ],
        },
        {
            "code": "NET-201",
            "name": "Network Engineering",
            "description": "Advanced networking course covering design, implementation, and management of enterprise networks.",
            "total_weeks": 10,
            "max_class": 25,
            "modules": [
                ("NET-201-01", "TCP/IP Deep Dive", 16, False, 3),
                ("NET-201-02", "Routing & Switching", 20, True, 3),
                ("NET-201-03", "Network Design", 12, False, 2),
                ("NET-201-04", "Wireless Networks", 12, True, 2),
                ("NET-201-05", "Network Monitoring", 16, True, 3),
                ("NET-201-06", "Cloud Networking", 12, False, 2),
                ("NET-201-07", "Network Automation", 16, True, 3),
            ],
        },
        {
            "code": "SWD-301",
            "name": "Software Development",
            "description": "Comprehensive software development programme from fundamentals to capstone project.",
            "total_weeks": 16,
            "max_class": 25,
            "modules": [
                ("SWD-301-01", "Python Programming", 20, True, 3),
                ("SWD-301-02", "Object-Oriented Design", 16, False, 3),
                ("SWD-301-03", "Web Development", 20, True, 3),
                ("SWD-301-04", "Database Systems", 16, True, 3),
                ("SWD-301-05", "API Development", 16, True, 3),
                ("SWD-301-06", "Testing & QA", 12, False, 2),
                ("SWD-301-07", "DevOps Basics", 16, True, 3),
                ("SWD-301-08", "Software Architecture", 12, False, 2),
                ("SWD-301-09", "Agile Methodologies", 8, False, None),
                ("SWD-301-10", "Capstone Project", 24, True, 3),
            ],
        },
        {
            "code": "DAT-101",
            "name": "Data Analytics",
            "description": "Data analytics fundamentals covering statistics, data manipulation, and business intelligence.",
            "total_weeks": 8,
            "max_class": 30,
            "modules": [
                ("DAT-101-01", "Statistics Fundamentals", 16, False, 3),
                ("DAT-101-02", "Data Wrangling with Python", 16, True, 3),
                ("DAT-101-03", "Data Visualisation", 12, True, 2),
                ("DAT-101-04", "SQL for Analytics", 16, True, 3),
                ("DAT-101-05", "Business Intelligence", 12, False, 2),
                ("DAT-101-06", "Predictive Modelling", 16, True, 3),
            ],
        },
        {
            "code": "CLD-201",
            "name": "Cloud Infrastructure",
            "description": "Cloud infrastructure and services covering major platforms and modern deployment practices.",
            "total_weeks": 10,
            "max_class": 20,
            "modules": [
                ("CLD-201-01", "Cloud Concepts", 8, False, None),
                ("CLD-201-02", "AWS Fundamentals", 20, True, 3),
                ("CLD-201-03", "Azure Fundamentals", 20, True, 3),
                ("CLD-201-04", "Infrastructure as Code", 16, True, 3),
                ("CLD-201-05", "Containerisation", 16, True, 3),
                ("CLD-201-06", "Cloud Security", 12, False, 2),
                ("CLD-201-07", "Cloud Architecture", 12, False, 2),
            ],
        },
        {
            "code": "PMG-101",
            "name": "Project Management Professional",
            "description": "Professional project management methodologies, tools, and leadership techniques.",
            "total_weeks": 6,
            "max_class": 35,
            "modules": [
                ("PMG-101-01", "PM Foundations", 12, False, 2),
                ("PMG-101-02", "Planning & Scheduling", 16, False, 3),
                ("PMG-101-03", "Risk Management", 12, False, 2),
                ("PMG-101-04", "Stakeholder Management", 8, False, None),
                ("PMG-101-05", "Agile & Scrum", 12, False, 2),
                ("PMG-101-06", "PM Capstone", 8, False, None),
            ],
        },
        {
            "code": "AIM-301",
            "name": "AI & Machine Learning",
            "description": "Advanced AI and machine learning covering theory, practical implementation, and ethics.",
            "total_weeks": 12,
            "max_class": 20,
            "modules": [
                ("AIM-301-01", "Maths for ML", 16, False, 3),
                ("AIM-301-02", "Python for Data Science", 16, True, 3),
                ("AIM-301-03", "Supervised Learning", 20, True, 3),
                ("AIM-301-04", "Unsupervised Learning", 16, True, 3),
                ("AIM-301-05", "Deep Learning", 20, True, 3),
                ("AIM-301-06", "NLP Fundamentals", 16, True, 3),
                ("AIM-301-07", "ML Operations", 12, True, 2),
                ("AIM-301-08", "AI Ethics", 8, False, None),
            ],
        },
        {
            "code": "SYS-201",
            "name": "Systems Administration",
            "description": "Enterprise systems administration covering Linux, Windows, virtualisation, and automation.",
            "total_weeks": 10,
            "max_class": 25,
            "modules": [
                ("SYS-201-01", "Linux Administration", 20, True, 3),
                ("SYS-201-02", "Windows Server", 16, True, 3),
                ("SYS-201-03", "Active Directory", 12, True, 2),
                ("SYS-201-04", "Virtualisation", 16, True, 3),
                ("SYS-201-05", "Backup & Recovery", 12, False, 2),
                ("SYS-201-06", "Monitoring & Logging", 12, True, 2),
                ("SYS-201-07", "Automation & Scripting", 16, True, 3),
            ],
        },
    ]

    courses = []
    all_modules = []
    modules_by_course_code = {}

    for spec in courses_spec:
        course = Course(
            code=spec["code"],
            name=spec["name"],
            description=spec["description"],
            total_weeks=spec["total_weeks"],
            max_concurrent_runs=2,
        )
        session.add(course)
        session.flush()
        courses.append(course)

        course_modules = []
        for seq, (mod_code, mod_name, hours, lab, exam_dur) in enumerate(spec["modules"], start=1):
            mod = Module(
                course_id=course.id,
                code=mod_code,
                name=mod_name,
                duration_hours=hours,
                sequence_order=seq,
                requires_lab=lab,
                max_class_size=spec["max_class"],
                exam_duration_hours=exam_dur,
            )
            session.add(mod)
            course_modules.append(mod)
            all_modules.append(mod)

        session.flush()
        modules_by_course_code[spec["code"]] = course_modules

    course_by_code = {c.code: c for c in courses}

    # -----------------------------------------------------------------------
    # 4. Classrooms (12)
    # -----------------------------------------------------------------------
    classrooms_data = [
        # (name, building, capacity, has_lab, has_projector)
        ("Main Hall", "Main Building", 60, False, True),
        ("Auditorium A", "Main Building", 80, False, True),
        ("Lecture Theatre B", "East Wing", 50, False, True),
        ("Room 101", "Main Building", 30, False, True),
        ("Room 102", "Main Building", 35, False, True),
        ("Room 103", "East Wing", 25, False, True),
        ("Room 104", "East Wing", 30, False, True),
        ("Room 105", "West Wing", 28, False, True),
        ("Computer Lab 1", "Tech Centre", 20, True, True),
        ("Computer Lab 2", "Tech Centre", 25, True, True),
        ("Network Lab", "Tech Centre", 15, True, True),
        ("Security Lab", "Tech Centre", 15, True, True),
    ]

    classrooms = []
    for name, building, cap, lab, proj in classrooms_data:
        room = Classroom(
            name=name,
            building=building,
            capacity=cap,
            has_lab_equipment=lab,
            has_projector=proj,
        )
        session.add(room)
        classrooms.append(room)
    session.flush()

    # -----------------------------------------------------------------------
    # 5. Lecturer Qualifications (~150)
    # -----------------------------------------------------------------------
    # Define specialist groupings by lecturer index (0-19)
    # Lecturer specialisation mapping:
    #   0  Dr Sarah Chen         - Cyber security specialist
    #   1  Prof Marcus Williams  - Cyber security / network specialist
    #   2  Dr Priya Patel        - Network engineering specialist
    #   3  James O'Brien         - Network / systems admin generalist
    #   4  Dr Fatima Al-Rashid   - Software development specialist
    #   5  Michael Torres        - Software development specialist
    #   6  Dr Emma Richardson    - Software dev / data analytics
    #   7  Robert Kim            - Data analytics / AI specialist
    #   8  Dr Aisha Mohammed     - AI / ML specialist
    #   9  Thomas Blake          - Cloud infrastructure specialist
    #   10 Dr Yuki Tanaka        - Cloud / network specialist
    #   11 Sophie Anderson       - Systems admin specialist
    #   12 Dr Kwame Asante       - Systems admin / cloud
    #   13 Laura Martinez        - PM specialist / generalist
    #   14 Dr Ravi Sharma        - AI / data specialist
    #   15 Claire Dubois         - PM / software dev
    #   16 Dr Ben Carter         - Cyber security / systems admin
    #   17 Nadia Volkov          - Cloud / DevOps specialist
    #   18 Dr Olumide Adeyemi    - Data / AI specialist
    #   19 Hannah Cooper         - PM / generalist

    qualification_specs = {
        # lecturer_index: [(course_code, module_indices (0-based), proficiency, can_examine)]
        0: [  # Dr Sarah Chen - Cyber specialist
            ("CYB-101", [0, 1, 2, 3, 4, 5, 6, 7], "primary", True),
            ("NET-201", [0, 1], "secondary", True),
        ],
        1: [  # Prof Marcus Williams - Cyber + network
            ("CYB-101", [0, 1, 2, 5, 6], "primary", True),
            ("CYB-101", [3, 4], "secondary", True),
            ("NET-201", [0, 1, 2], "secondary", True),
        ],
        2: [  # Dr Priya Patel - Network specialist
            ("NET-201", [0, 1, 2, 3, 4, 5, 6], "primary", True),
            ("CYB-101", [1], "secondary", True),
            ("SYS-201", [0, 6], "secondary", True),
        ],
        3: [  # James O'Brien - Network + sysadmin generalist
            ("NET-201", [0, 1, 2, 4, 6], "primary", True),
            ("NET-201", [3, 5], "secondary", True),
            ("SYS-201", [0, 1, 4, 5, 6], "secondary", True),
        ],
        4: [  # Dr Fatima Al-Rashid - Software dev specialist
            ("SWD-301", [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], "primary", True),
            ("DAT-101", [1], "secondary", True),
        ],
        5: [  # Michael Torres - Software dev specialist
            ("SWD-301", [0, 1, 2, 4, 5, 8], "primary", True),
            ("SWD-301", [3, 6, 7, 9], "secondary", True),
            ("DAT-101", [3], "secondary", True),
        ],
        6: [  # Dr Emma Richardson - Software dev + data
            ("SWD-301", [0, 1, 3, 5, 7], "primary", True),
            ("SWD-301", [2, 4, 8], "secondary", True),
            ("DAT-101", [0, 1, 2], "secondary", True),
        ],
        7: [  # Robert Kim - Data analytics + AI
            ("DAT-101", [0, 1, 2, 3, 4, 5], "primary", True),
            ("AIM-301", [0, 1, 2], "secondary", True),
        ],
        8: [  # Dr Aisha Mohammed - AI/ML specialist
            ("AIM-301", [0, 1, 2, 3, 4, 5, 6, 7], "primary", True),
            ("DAT-101", [0, 5], "secondary", True),
        ],
        9: [  # Thomas Blake - Cloud specialist
            ("CLD-201", [0, 1, 2, 3, 4, 5, 6], "primary", True),
            ("NET-201", [5], "secondary", True),
            ("SYS-201", [3], "emergency", True),
        ],
        10: [  # Dr Yuki Tanaka - Cloud + network
            ("CLD-201", [0, 1, 2, 4, 5, 6], "primary", True),
            ("CLD-201", [3], "secondary", True),
            ("NET-201", [0, 5, 6], "secondary", True),
        ],
        11: [  # Sophie Anderson - Systems admin
            ("SYS-201", [0, 1, 2, 3, 4, 5, 6], "primary", True),
            ("CLD-201", [4], "secondary", True),
            ("NET-201", [4], "emergency", True),
        ],
        12: [  # Dr Kwame Asante - Systems admin + cloud
            ("SYS-201", [0, 1, 2, 3, 5, 6], "primary", True),
            ("SYS-201", [4], "secondary", True),
            ("CLD-201", [0, 3, 4], "secondary", True),
        ],
        13: [  # Laura Martinez - PM specialist
            ("PMG-101", [0, 1, 2, 3, 4, 5], "primary", True),
            ("SWD-301", [8], "secondary", True),
            ("SWD-301", [5], "emergency", False),
        ],
        14: [  # Dr Ravi Sharma - AI + data specialist
            ("AIM-301", [0, 2, 3, 4, 5, 7], "primary", True),
            ("AIM-301", [1, 6], "secondary", True),
            ("DAT-101", [0, 1, 5], "primary", True),
        ],
        15: [  # Claire Dubois - PM + software dev
            ("PMG-101", [0, 1, 2, 3, 4, 5], "primary", True),
            ("SWD-301", [1, 5, 7, 8], "secondary", True),
        ],
        16: [  # Dr Ben Carter - Cyber + systems admin
            ("CYB-101", [0, 1, 3, 5, 6, 7], "primary", True),
            ("CYB-101", [2, 4], "secondary", True),
            ("SYS-201", [0, 2], "emergency", True),
        ],
        17: [  # Nadia Volkov - Cloud + DevOps
            ("CLD-201", [1, 2, 3, 4, 5], "primary", True),
            ("CLD-201", [0, 6], "secondary", True),
            ("SWD-301", [6], "secondary", True),
            ("SYS-201", [3, 6], "emergency", True),
        ],
        18: [  # Dr Olumide Adeyemi - Data + AI
            ("DAT-101", [0, 1, 2, 3, 4, 5], "primary", True),
            ("AIM-301", [0, 1, 2, 3, 7], "secondary", True),
        ],
        19: [  # Hannah Cooper - PM generalist + some others
            ("PMG-101", [0, 1, 2, 3, 4, 5], "primary", True),
            ("CYB-101", [7], "emergency", False),
            ("DAT-101", [4], "emergency", False),
        ],
    }

    qualifications = []
    seen_qual_pairs = set()

    for lec_idx, specs in qualification_specs.items():
        lecturer = lecturers[lec_idx]
        for course_code, mod_indices, proficiency, can_exam in specs:
            course_mods = modules_by_course_code[course_code]
            for mi in mod_indices:
                mod = course_mods[mi]
                pair = (lecturer.id, mod.id)
                if pair in seen_qual_pairs:
                    continue
                seen_qual_pairs.add(pair)
                q = LecturerQualification(
                    lecturer_id=lecturer.id,
                    module_id=mod.id,
                    proficiency_level=proficiency,
                    can_examine=can_exam,
                )
                session.add(q)
                qualifications.append(q)

    session.flush()

    # -----------------------------------------------------------------------
    # 6. Course Runs (15-20 per academic year, across 3 years)
    # -----------------------------------------------------------------------
    # Define run schedule: (course_code, cohort_label, start_month, start_day)
    # for each academic year pattern
    run_patterns = [
        # Year 1 pattern (2025-2026)
        ("CYB-101", "Cohort A", 10, 6),
        ("CYB-101", "Cohort B", 2, 2),
        ("CYB-101", "Cohort C", 6, 1),
        ("NET-201", "Cohort A", 9, 8),
        ("NET-201", "Cohort B", 1, 12),
        ("SWD-301", "Cohort A", 10, 13),
        ("SWD-301", "Cohort B", 3, 9),
        ("DAT-101", "Cohort A", 11, 3),
        ("DAT-101", "Cohort B", 3, 2),
        ("DAT-101", "Cohort C", 6, 8),
        ("CLD-201", "Cohort A", 9, 15),
        ("CLD-201", "Cohort B", 2, 9),
        ("PMG-101", "Cohort A", 10, 20),
        ("PMG-101", "Cohort B", 1, 19),
        ("PMG-101", "Cohort C", 4, 6),
        ("PMG-101", "Cohort D", 6, 15),
        ("AIM-301", "Cohort A", 11, 10),
        ("AIM-301", "Cohort B", 4, 13),
        ("SYS-201", "Cohort A", 9, 22),
        ("SYS-201", "Cohort B", 3, 16),
    ]

    course_runs = []

    for ay_idx, ay in enumerate(academic_years):
        ay_year_start = ay.start_date.year  # e.g. 2025 for 2025-2026

        for course_code, cohort_label, start_month, start_day in run_patterns:
            course = course_by_code[course_code]

            # Calculate the actual year for this run's start date
            if start_month >= 9:
                run_year = ay_year_start
            else:
                run_year = ay_year_start + 1

            # Adjust cohort label to include year info for uniqueness
            full_cohort = f"{cohort_label} {ay.label}"

            start = date(run_year, start_month, start_day)
            end = _add_weeks(start, course.total_weeks)

            # Ensure end date is within academic year (clamp if needed)
            if end > ay.end_date:
                end = ay.end_date

            student_count = random.randint(12, 30)

            cr = CourseRun(
                course_id=course.id,
                academic_year_id=ay.id,
                cohort_label=full_cohort,
                planned_start_date=start,
                planned_end_date=end,
                student_count=student_count,
                status="draft",
            )
            session.add(cr)
            course_runs.append(cr)

    session.flush()

    # -----------------------------------------------------------------------
    # 7. Rules
    # -----------------------------------------------------------------------
    rules_data = [
        ("teacher_cannot_examine", "true",
         "The person who taught a module cannot examine resits for it"),
        ("min_prep_hours", "4",
         "Minimum prep hours before delivering a module"),
        ("min_wind_down_hours", "2",
         "Minimum marking/wind-down hours after a module block"),
        ("max_concurrent_course_runs", "6",
         "Maximum course runs active simultaneously academy-wide"),
        ("preferred_start_day", "monday",
         "Course runs preferably start on this day"),
        ("min_gap_between_blocks_days", "2",
         "Minimum gap between a lecturer's teaching blocks"),
        ("balance_weight", "50",
         "Weight for load-balancing objective (0-100)"),
        ("compactness_weight", "30",
         "Weight for compact scheduling objective"),
        ("qualification_preference_weight", "20",
         "Weight for preferring primary-qualified lecturers"),
    ]

    for key, value, desc in rules_data:
        rule = Rule(key=key, value=value, description=desc, enabled=True)
        session.add(rule)
    session.flush()

    # -----------------------------------------------------------------------
    # 8. Lecturer Availability
    # -----------------------------------------------------------------------
    # For each academic year create unavailability records

    for ay in academic_years:
        ay_start = ay.start_date
        ay_end = ay.end_date
        ay_year_start = ay_start.year

        # Christmas break (Dec 20 - Jan 3) for ALL lecturers
        christmas_start = date(ay_year_start, 12, 20)
        christmas_end = date(ay_year_start + 1, 1, 3)
        christmas_days = _weekdays_between(christmas_start, christmas_end)

        for lec in lecturers:
            for d in christmas_days:
                session.add(LecturerAvailability(
                    lecturer_id=lec.id,
                    date=d,
                    available=False,
                    reason="Christmas break",
                ))

        # Lecturer 1 (Prof Marcus Williams) - unavailable every Friday
        all_fridays = _fridays_between(ay_start, ay_end)
        for d in all_fridays:
            session.add(LecturerAvailability(
                lecturer_id=lecturers[1].id,
                date=d,
                available=False,
                reason="Not available on Fridays",
            ))

        # Lecturers 4 and 8 - 2-week annual leave blocks
        # Dr Fatima Al-Rashid: 2 weeks in July
        leave_start_4 = date(ay_year_start + 1, 7, 7)
        leave_end_4 = date(ay_year_start + 1, 7, 18)
        for d in _weekdays_between(leave_start_4, leave_end_4):
            if ay_start <= d <= ay_end:
                session.add(LecturerAvailability(
                    lecturer_id=lecturers[4].id,
                    date=d,
                    available=False,
                    reason="Annual leave",
                ))

        # Dr Aisha Mohammed: 2 weeks in April
        leave_start_8 = date(ay_year_start + 1, 4, 14)
        leave_end_8 = date(ay_year_start + 1, 4, 25)
        for d in _weekdays_between(leave_start_8, leave_end_8):
            if ay_start <= d <= ay_end:
                session.add(LecturerAvailability(
                    lecturer_id=lecturers[8].id,
                    date=d,
                    available=False,
                    reason="Annual leave",
                ))

        # Lecturer 14 (Dr Ravi Sharma) - 2-week annual leave in February
        leave_start_14 = date(ay_year_start + 1, 2, 17)
        leave_end_14 = date(ay_year_start + 1, 2, 28)
        for d in _weekdays_between(leave_start_14, leave_end_14):
            if ay_start <= d <= ay_end:
                session.add(LecturerAvailability(
                    lecturer_id=lecturers[14].id,
                    date=d,
                    available=False,
                    reason="Annual leave",
                ))

        # Lecturer 9 (Thomas Blake) - 1 month long-term absence (November)
        lta_start = date(ay_year_start, 11, 3)
        lta_end = date(ay_year_start, 11, 28)
        for d in _weekdays_between(lta_start, lta_end):
            if ay_start <= d <= ay_end:
                session.add(LecturerAvailability(
                    lecturer_id=lecturers[9].id,
                    date=d,
                    available=False,
                    reason="Long-term absence",
                ))

    session.flush()

    # -----------------------------------------------------------------------
    # 9. Resits (15-25 per academic year)
    # -----------------------------------------------------------------------
    # Generate resits for course runs that would have completed by now
    # (or that are in the past portion of each academic year)

    for ay in academic_years:
        num_resits = random.randint(15, 25)

        # Get course runs for this academic year
        ay_runs = [cr for cr in course_runs if cr.academic_year_id == ay.id]

        for _ in range(num_resits):
            # Pick a random course run
            cr = random.choice(ay_runs)
            course = course_by_code[
                next(code for code, c in course_by_code.items() if c.id == cr.course_id)
            ]

            # Pick a random module from this course
            course_mods = modules_by_course_code[course.code]
            mod = random.choice(course_mods)

            # Find a qualified lecturer for original_lecturer_id
            qualified_lecs = [
                q.lecturer_id for q in qualifications
                if q.module_id == mod.id
            ]
            if not qualified_lecs:
                continue

            original_lec_id = random.choice(qualified_lecs)

            # required_by_date: 2-6 weeks after course end
            weeks_after = random.randint(2, 6)
            required_by = cr.planned_end_date + timedelta(weeks=weeks_after)

            resit = Resit(
                course_run_id=cr.id,
                module_id=mod.id,
                student_name=_random_student_name(),
                required_by_date=required_by,
                original_lecturer_id=original_lec_id,
                status="pending",
            )
            session.add(resit)

    session.flush()
    session.commit()

    # -----------------------------------------------------------------------
    # 10. Run the solver for the first academic year
    # -----------------------------------------------------------------------
    try:
        from solver.engine import TimetableSolver
        solver = TimetableSolver(session)
        solver.solve(academic_year_id=academic_years[0].id, timeout_seconds=60)
        session.commit()
    except Exception as e:
        # Don't let solver failure prevent seeding from completing
        session.rollback()
        print(f"Warning: Solver failed during seeding: {e}")
        # Re-commit the seed data without solver results
        session.commit()
