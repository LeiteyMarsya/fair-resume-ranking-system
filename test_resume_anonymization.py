
import db
import re

db.init_database()

application_id = 20

connection = db.get_connection()

try:
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            c.name,
            c.email,
            c.phone,
            r.extracted_text
        FROM applications a
        JOIN candidates c
            ON a.candidate_id = c.candidate_id
        JOIN resumes r
            ON a.resume_id = r.resume_id
        WHERE a.application_id = ?
        """,
        (application_id,)
    )

    record = cursor.fetchone()

finally:
    connection.close()


print("===== RESUME ANONYMIZATION TEST =====")

if record is None:
    print("Application not found.")

else:
    resume_text = record["extracted_text"] or ""

    # Normalize text for comparison
    normalized_resume = re.sub(
        r"\s+",
        " ",
        resume_text
    ).casefold()

    # Check candidate's stored name
    candidate_name = (record["name"] or "").strip()

    name_found = (
        candidate_name.casefold() in normalized_resume
        if candidate_name else False
    )

    # Check candidate's stored email
    candidate_email = (record["email"] or "").strip()

    email_found = (
        candidate_email.casefold() in normalized_resume
        if candidate_email else False
    )

    # Check candidate's stored phone number
    candidate_phone = re.sub(
        r"\D",
        "",
        record["phone"] or ""
    )

    resume_digits = re.sub(
        r"\D",
        "",
        resume_text
    )

    phone_found = (
        candidate_phone in resume_digits
        if candidate_phone else False
    )

    # Check for any email address in the resume
    email_pattern_found = bool(
        re.search(
            r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",
            resume_text
        )
    )

    print("Application ID:", application_id)
    print("Resume text available:", bool(resume_text))

    print("\n===== PERSONAL INFORMATION CHECK =====")
    print("Candidate's full name found:", name_found)
    print("Candidate's email found:", email_found)
    print("Candidate's phone found:", phone_found)
    print("Any email pattern found:", email_pattern_found)

    print("\n===== TEST COMPLETED =====")
