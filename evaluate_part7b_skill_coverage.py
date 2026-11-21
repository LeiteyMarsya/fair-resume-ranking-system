import re
import sqlite3
from statistics import mean

DB_PATH = "file:data/database/resume_system.db?mode=ro"

def normalize(value):
    value = (value or "").casefold().strip()
    value = re.sub(r"[-_/]", " ", value)
    value = re.sub(r"[^a-z0-9+#. ]", "", value)
    return re.sub(r"\s+", " ", value).strip()

conn = sqlite3.connect(DB_PATH, uri=True)
conn.row_factory = sqlite3.Row

JOB_ID = 2

requirements = conn.execute("""
    SELECT requirement_text, requirement_type, mandatory
    FROM job_requirements
    WHERE job_id = ?
      AND category = 'SKILL'
      AND recruiter_verified = 1
    ORDER BY requirement_id
""", (JOB_ID,)).fetchall()

required_skills = {
    normalize(row["requirement_text"]): row["requirement_text"]
    for row in requirements
}

applications = conn.execute("""
    SELECT application_id, resume_id
    FROM applications
    WHERE job_id = ?
    ORDER BY application_id
""", (JOB_ID,)).fetchall()

print("=" * 75)
print("PART 7B: READ-ONLY RESUME-TO-JOB SKILL COVERAGE")
print("=" * 75)

print("\nJOB:", JOB_ID)
print("VERIFIED SKILL REQUIREMENTS:", len(required_skills))

for row in requirements:
    print(
        f"  - {row['requirement_text']} "
        f"| Type: {row['requirement_type']} "
        f"| Mandatory: {row['mandatory']}"
    )

results = []

print("\n===== APPLICATION RESULTS =====")

for app in applications:
    rows = conn.execute("""
        SELECT entity_text
        FROM resume_entities
        WHERE resume_id = ?
          AND entity_label = 'SKILL'
    """, (app["resume_id"],)).fetchall()

    resume_skills = {
        normalize(row["entity_text"])
        for row in rows
        if normalize(row["entity_text"])
    }

    matched = [
        label for key, label in required_skills.items()
        if key in resume_skills
    ]

    missing = [
        label for key, label in required_skills.items()
        if key not in resume_skills
    ]

    coverage = (
        len(matched) / len(required_skills) * 100
        if required_skills else 0
    )

    results.append(coverage)

    print(
        f"\nApplication {app['application_id']} "
        f"| Resume {app['resume_id']}"
    )
    print(f"Matched: {len(matched)}/{len(required_skills)}")
    print(f"Diagnostic coverage: {coverage:.2f}%")
    print("Matched skills:", ", ".join(matched) if matched else "None")
    print("Unmatched requirements:", ", ".join(missing) if missing else "None")

print("\n===== SUMMARY =====")
print("Applications evaluated:", len(results))
print("Average diagnostic coverage:", f"{mean(results):.2f}%" if results else "N/A")
print("Highest coverage:", f"{max(results):.2f}%" if results else "N/A")
print("Lowest coverage:", f"{min(results):.2f}%" if results else "N/A")
print("Applications with zero extracted skills:", sum(
    1 for app in applications
    if conn.execute("""
        SELECT COUNT(*)
        FROM resume_entities
        WHERE resume_id = ? AND entity_label = 'SKILL'
    """, (app["resume_id"],)).fetchone()[0] == 0
))

conn.close()

print("\nREAD-ONLY EVALUATION COMPLETED.")
