"""Seed reference data, demo accounts and a historical exam archive.

Usage (from backend/):  python -m scripts.seed [--samples-dir ../samples]

Idempotent: existing departments/courses/users are left as-is and archive papers are
skipped when an identical file was already ingested. Archive papers are processed by the
real analysis pipeline, so their questions get parsed, classified and embedded.
"""
import argparse
import hashlib
import io
import os
import re
import uuid
from pathlib import Path

from sqlalchemy import select

from app.core.admin_security import sync_system_roles
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.entities import AdminRole, AdminUser, Course, Department, PaperStatus, QuestionPaperDraft, SyllabusUnit, User, UserRole
from app.services.file_validation import PDF_MIME
from app.services.paper_pipeline import process_paper
from app.services.storage_service import get_storage_provider
from scripts.pdf_utils import build_pdf

DEMO_PASSWORD = os.environ.get("SEED_PASSWORD", "QpiDemo2026!")
# Admin-panel accounts need 12+ characters.
DEMO_ADMIN_PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD", "QpiAdminDemo2026!")
DEMO_ADMINS = [
    ("superadmin@qpi-demo.edu", "Demo Super Admin", "super_admin"),
    ("support@qpi-demo.edu", "Demo Support Agent", "support"),
]

DEPARTMENTS = [
    ("PHY", "Department of Physics"),
    ("CS", "Computer Science"),
    ("MATH", "Mathematics"),
    ("EE", "Electrical Engineering"),
]

USERS = [
    ("faculty@qpi-demo.edu", "Dr. Demo Faculty", UserRole.FACULTY, "PHY"),
    ("cs.faculty@qpi-demo.edu", "Dr. Demo CS Faculty", UserRole.FACULTY, "CS"),
    ("head.physics@qpi-demo.edu", "Prof. Demo Department Head", UserRole.DEPT_HEAD, "PHY"),
    ("archivist@qpi-demo.edu", "Demo Archivist", UserRole.ARCHIVAL_ADMIN, None),
    ("admin@qpi-demo.edu", "Demo System Admin", UserRole.SYSTEM_ADMIN, None),
]

COURSES = {
    ("PHY", "PHY-201"): ("Classical Mechanics & Thermodynamics", [
        (1, "Kinematics", 20, ["velocity", "acceleration", "displacement", "projectile", "trajectory", "free fall", "kinematic"]),
        (2, "Newton's Laws & Dynamics", 20, ["newton", "force", "friction", "inertia", "tension", "free-body", "net force"]),
        (3, "Work, Energy & Collisions", 20, ["work", "kinetic energy", "potential energy", "conservation of energy", "collision", "elastic", "inelastic", "power", "momentum"]),
        (4, "Rotational Motion", 20, ["torque", "angular", "moment of inertia", "rotational", "rolling", "angular momentum", "flywheel"]),
        (5, "Thermodynamics", 20, ["thermodynamics", "heat", "temperature", "entropy", "carnot", "ideal gas", "specific heat", "heat engine"]),
    ]),
    ("CS", "CS-101"): ("Introduction to Programming", [
        (1, "Basics & Data Types", 20, ["variable", "data type", "integer", "string", "boolean", "type conversion", "operator"]),
        (2, "Control Flow", 20, ["loop", "while", "for loop", "if statement", "conditional", "break", "iteration"]),
        (3, "Functions & Recursion", 20, ["function", "recursion", "recursive", "parameter", "return value", "scope", "factorial"]),
        (4, "Data Structures", 20, ["array", "list", "dictionary", "stack", "queue", "linked list", "hash table"]),
        (5, "Algorithms & Complexity", 20, ["sorting", "searching", "binary search", "complexity", "big-o", "bubble sort", "merge sort"]),
    ]),
}

PHY_ARCHIVE = [
    ("2021-2022", "Fall", "Final Examination", [
        "SECTION A",
        "1. Define displacement and velocity, and state the difference between them. (5 marks)",
        "2. A projectile is launched at 45 degrees with an initial velocity of 20 m/s. Calculate the maximum height and horizontal range of its trajectory. (10 marks)",
        "3. State Newton's three laws of motion and give an everyday example of each. (10 marks)",
        "SECTION B",
        "4. Explain elastic and inelastic collisions with suitable examples. (10 marks)",
        "5. A solid disc of mass 2 kg and radius 0.5 m rotates at 10 rad/s. Calculate its moment of inertia and angular momentum. (10 marks)",
        "6. State the second law of thermodynamics and explain the working of a Carnot heat engine. (15 marks)",
    ]),
    ("2022-2023", "Fall", "Final Examination", [
        "SECTION A",
        "1. A ball is dropped from a height of 45 m. Calculate the time taken to reach the ground and its velocity on impact in free fall. (10 marks)",
        "2. A 5 kg block is pushed across a frictionless surface with a force of 20 N. Calculate its acceleration. (5 marks)",
        "3. Explain the concept of inertia and how it relates to Newton's first law. (5 marks)",
        "SECTION B",
        "4. Derive the work-energy theorem and use it to find the speed of a 2 kg cart after 50 J of work is done on it. (15 marks)",
        "5. Define entropy and explain why the entropy of an isolated system never decreases. (10 marks)",
    ]),
    ("2023-2024", "Fall", "Final Examination", [
        "1. Distinguish between speed and velocity. A car travels 100 m east and then 60 m west in 20 s; find its average velocity. (10 marks)",
        "2. Calculate the trajectory of a projectile launched at 45 degrees with an initial speed of 20 m/s and find its range. (10 marks)",
        "3. Draw a free-body diagram for a block on an inclined plane with friction and determine the net force acting on it. (10 marks)",
        "4. Explain the principle of conservation of energy with the example of a swinging pendulum. (10 marks)",
        "5. An ideal gas expands isothermally at 300 K. Explain the first law of thermodynamics for this process. (10 marks)",
    ]),
    ("2024-2025", "Spring", "Midterm Examination", [
        "1. Define acceleration and state its SI unit. (5 marks)",
        "2. A stone is thrown vertically upward with a velocity of 15 m/s. Calculate the maximum height reached. (10 marks)",
        "3. State Newton's second law of motion and explain the relation between force and momentum. (10 marks)",
        "4. Compare elastic and inelastic collisions and give one example of each. (5 marks)",
    ]),
    ("2024-2025", "Fall", "Final Examination", [
        "1. A projectile is fired horizontally from a cliff 80 m high with a speed of 25 m/s. Determine the time of flight and the displacement from the base of the cliff. (10 marks)",
        "2. A 5 kg block is pushed across a frictionless surface with a force of 20 N. Calculate the acceleration of the block. (5 marks)",
        "3. Explain why a heavier object requires a larger force to achieve the same acceleration, using Newton's laws. (5 marks)",
        "4. Define kinetic energy and potential energy. A 1 kg mass falls 10 m; calculate its kinetic energy just before impact. (10 marks)",
        "5. State the first law of thermodynamics and apply it to a gas heated at constant volume. (10 marks)",
    ]),
]

CS_ARCHIVE = [
    ("2022-2023", "Fall", "Final Examination", [
        "1. Define a variable and list four primitive data types with examples. (5 marks)",
        "2. Write a program using a for loop to print the first 10 even numbers. (10 marks)",
        "3. Explain recursion and write a recursive function to compute the factorial of n. (10 marks)",
        "4. Describe how a stack differs from a queue, with one application of each. (10 marks)",
    ]),
    ("2023-2024", "Fall", "Final Examination", [
        "1. Explain type conversion with an example of converting a string to an integer. (5 marks)",
        "2. Write a while loop that reads numbers until the user enters zero and prints their sum. (10 marks)",
        "3. Implement binary search on a sorted array and state its time complexity in big-O notation. (15 marks)",
        "4. Explain the difference between a list and a dictionary. (5 marks)",
    ]),
    ("2024-2025", "Fall", "Final Examination", [
        "1. Write a recursive function to compute the factorial of n and trace it for n = 4. (10 marks)",
        "2. Explain bubble sort and analyse its worst-case complexity. (10 marks)",
        "3. What is a hash table? Explain how collisions are handled. (10 marks)",
        "4. Explain the scope of a variable declared inside a function. (5 marks)",
    ]),
]

SAMPLE_DRAFTS = {
    "physics_draft_sample.pdf": ("PHY-201 Final Examination (Draft) - Fall 2026", [
        "SECTION A: MECHANICS",
        "1. Calculate the trajectory of a projectile launched at 45 degrees with an initial speed of 20 m/s and find its range. (10 marks)",
        "2. A 5 kg block is pushed across a frictionless surface with a force of 20 N. Calculate its acceleration. (5 marks)",
        "3. Explain elastic collisions. (10 marks)",
        "(a) Derive the equation for conservation of kinetic energy in a one-dimensional elastic collision. (5 marks)",
        "(b) Calculate the velocities of two equal masses after a head-on elastic collision. (5 marks)",
        "SECTION B: THERMODYNAMICS",
        "4. State the second law of thermodynamics and explain the working of a Carnot heat engine. (15 marks)",
        "5. Design an experiment to measure the specific heat of an unknown metal and evaluate its main sources of error. (10 marks)",
    ]),
    "physics_draft_revised.pdf": ("PHY-201 Final Examination (Revised Draft) - Fall 2026", [
        "SECTION A: MECHANICS",
        "1. A flywheel of moment of inertia 4 kg m^2 is brought to rest from 30 rad/s by a constant torque in 10 s. Determine the torque and the work done. (10 marks)",
        "2. Analyse the motion of a cylinder rolling without slipping down an incline and compare its speed with that of a sliding block. (10 marks)",
        "3. A satellite orbits the Earth in a circular path. Justify, using energy arguments, why it does not need fuel to stay in orbit. (10 marks)",
        "SECTION B: THERMODYNAMICS",
        "4. Design an experiment to measure the specific heat of an unknown metal and evaluate its main sources of error. (10 marks)",
        "5. Compare the efficiencies of a real heat engine and an ideal Carnot engine operating between 500 K and 300 K. (10 marks)",
    ]),
}


def seed_reference_data(db) -> dict:
    departments = {}
    for code, name in DEPARTMENTS:
        dept = db.scalar(select(Department).where(Department.code == code))
        if dept is None:
            dept = Department(code=code, name=name)
            db.add(dept)
        departments[code] = dept
    db.flush()

    for (dept_code, course_code), (title, units) in COURSES.items():
        course = db.scalar(select(Course).where(Course.department_id == departments[dept_code].id, Course.code == course_code))
        if course is None:
            course = Course(department_id=departments[dept_code].id, code=course_code, title=title, academic_year="2026-2027")
            db.add(course)
            db.flush()
        if not course.syllabus_units:
            for number, unit_title, weight, keywords in units:
                course.syllabus_units.append(
                    SyllabusUnit(unit_number=number, title=unit_title, target_weightage_percent=weight, keywords=keywords)
                )

    for email, name, role, dept_code in USERS:
        if db.scalar(select(User).where(User.email == email)) is None:
            db.add(User(
                email=email,
                full_name=name,
                password_hash=hash_password(DEMO_PASSWORD),
                role=role,
                department_id=departments[dept_code].id if dept_code else None,
            ))
    db.commit()

    sync_system_roles(db)
    for email, name, role_key in DEMO_ADMINS:
        if db.scalar(select(AdminUser).where(AdminUser.email == email)) is None:
            role = db.scalar(select(AdminRole).where(AdminRole.key == role_key))
            db.add(AdminUser(email=email, full_name=name, password_hash=hash_password(DEMO_ADMIN_PASSWORD), role_id=role.id))
    db.commit()
    return departments


def ingest_archive(db, dept_code: str, course_code: str, papers) -> int:
    storage = get_storage_provider()
    archivist = db.scalar(select(User).where(User.email == "archivist@qpi-demo.edu"))
    course = db.scalar(select(Course).join(Department).where(Department.code == dept_code, Course.code == course_code))
    ingested = 0
    for academic_year, term, exam_type, lines in papers:
        # Generated PDFs embed timestamps, so identify seeded papers by their metadata, not file hash.
        if db.scalar(select(QuestionPaperDraft.id).where(
            QuestionPaperDraft.course_id == course.id,
            QuestionPaperDraft.uploader_id == archivist.id,
            QuestionPaperDraft.is_historical_archive.is_(True),
            QuestionPaperDraft.academic_year == academic_year,
            QuestionPaperDraft.term == term,
            QuestionPaperDraft.exam_type == exam_type,
        )):
            continue
        pdf = build_pdf(lines, title=f"{course_code} {exam_type} - {term} {academic_year}")
        file_hash = hashlib.sha256(pdf).hexdigest()
        paper_id = uuid.uuid4()
        rel_path = f"{dept_code}/{course_code}/{academic_year}/{paper_id}.pdf"
        storage.save_file(io.BytesIO(pdf), rel_path)
        db.add(QuestionPaperDraft(
            id=paper_id,
            uploader_id=archivist.id,
            course_id=course.id,
            academic_year=academic_year,
            term=term,
            exam_type=exam_type,
            total_marks=sum(int(m) for m in re.findall(r"\((\d+) marks\)", " ".join(lines))) or 100,
            original_filename=f"{course_code}_{academic_year}_{term}_{exam_type.split()[0]}.pdf",
            file_path=rel_path,
            file_mime_type=PDF_MIME,
            file_size_bytes=len(pdf),
            file_hash=file_hash,
            is_historical_archive=True,
            status=PaperStatus.QUEUED,
            current_step="Queued for analysis",
        ))
        db.commit()
        process_paper(str(paper_id))
        status = db.scalar(select(QuestionPaperDraft.status).where(QuestionPaperDraft.id == paper_id))
        print(f"  archived {course_code} {term} {academic_year} {exam_type}: {status.value}")
        ingested += 1
    return ingested


def write_samples(samples_dir: Path) -> None:
    samples_dir.mkdir(parents=True, exist_ok=True)
    for filename, (title, lines) in SAMPLE_DRAFTS.items():
        (samples_dir / filename).write_bytes(build_pdf(lines, title=title))
        print(f"  wrote sample draft {samples_dir / filename}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples-dir", default=str(Path(__file__).resolve().parents[2] / "samples"))
    parser.add_argument("--skip-archive", action="store_true", help="Only seed departments, courses and users")
    args = parser.parse_args()

    with SessionLocal() as db:
        print("Seeding departments, courses, syllabi and demo users...")
        seed_reference_data(db)
        if not args.skip_archive:
            print("Ingesting historical archive papers (runs the analysis pipeline)...")
            n = ingest_archive(db, "PHY", "PHY-201", PHY_ARCHIVE) + ingest_archive(db, "CS", "CS-101", CS_ARCHIVE)
            print(f"  {n} new archive paper(s) ingested")
    write_samples(Path(args.samples_dir))
    # Don't echo a password supplied via SEED_PASSWORD (e.g. into hosted deploy logs).
    shown = "from SEED_PASSWORD" if "SEED_PASSWORD" in os.environ else DEMO_PASSWORD
    print(f"\nDemo accounts (password: {shown}):")
    for email, _, role, dept in USERS:
        print(f"  {email:<30} {role.value:<15} {dept or '-'}")
    shown = "from SEED_ADMIN_PASSWORD" if "SEED_ADMIN_PASSWORD" in os.environ else DEMO_ADMIN_PASSWORD
    print(f"\nAdmin panel accounts (password: {shown}):")
    for email, _, role_key in DEMO_ADMINS:
        print(f"  {email:<30} {role_key}")


if __name__ == "__main__":
    main()
