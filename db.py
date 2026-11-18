from __future__ import annotations

import sqlite3
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional


# DATABASE CONFIGURATION

BASE_DIR = Path(__file__).resolve().parent

DATABASE_DIR = BASE_DIR / "data" / "database"

DATABASE_DIR.mkdir(
    parents=True,
    exist_ok=True
)

DEFAULT_DB_PATH = DATABASE_DIR / "resume_system.db"

configured_database_path = os.environ.get(
    "ESCO_DATABASE_PATH"
)

if configured_database_path:

    DB_PATH = Path(configured_database_path)

    if not DB_PATH.is_absolute():

        DB_PATH = BASE_DIR / DB_PATH

else:

    DB_PATH = DEFAULT_DB_PATH


# DATABASE CONNECTION

def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection

# DATABASE INITIALIZATION

def init_database() -> None:
    """
    Create all database tables.
    """

    connection = get_connection()

    try:

        cursor = connection.cursor()

        # JOBS

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                job_id INTEGER PRIMARY KEY AUTOINCREMENT,

                job_title TEXT NOT NULL,

                seniority_level TEXT NOT NULL,

                description TEXT NOT NULL,

                source_filename TEXT,

                status TEXT NOT NULL DEFAULT 'DRAFT',

                requirements_confirmed
                    INTEGER NOT NULL DEFAULT 0,

                created_at TEXT NOT NULL
            )
            """
        )


        # CANDIDATES

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS candidates (
                candidate_id INTEGER PRIMARY KEY AUTOINCREMENT,

                blind_id TEXT NOT NULL UNIQUE,

                name TEXT,

                email TEXT,

                phone TEXT,

                created_at TEXT NOT NULL
            )
            """
        )


        # RESUMES

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS resumes (
                resume_id INTEGER PRIMARY KEY AUTOINCREMENT,

                candidate_id INTEGER NOT NULL,

                original_filename TEXT NOT NULL,

                stored_filename TEXT NOT NULL,

                stored_path TEXT NOT NULL,

                file_hash TEXT NOT NULL,

                extracted_text TEXT,

                extraction_status TEXT NOT NULL,

                parser_version TEXT NOT NULL,

                created_at TEXT NOT NULL,

                FOREIGN KEY (candidate_id)
                    REFERENCES candidates(candidate_id)
            )
            """
        )

        # APPLICATIONS

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS applications (
                application_id INTEGER PRIMARY KEY AUTOINCREMENT,

                candidate_id INTEGER NOT NULL,

                job_id INTEGER NOT NULL,

                resume_id INTEGER NOT NULL,

                application_status
                    TEXT NOT NULL DEFAULT 'RECEIVED',

                created_at TEXT NOT NULL,

                FOREIGN KEY (candidate_id)
                    REFERENCES candidates(candidate_id),

                FOREIGN KEY (job_id)
                    REFERENCES jobs(job_id),

                FOREIGN KEY (resume_id)
                    REFERENCES resumes(resume_id),

                UNIQUE(candidate_id, job_id)
            )
            """
        )


        # JOB REQUIREMENTS

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS job_requirements (
                requirement_id INTEGER PRIMARY KEY AUTOINCREMENT,

                job_id INTEGER NOT NULL,

                requirement_text TEXT NOT NULL,

                category TEXT NOT NULL,

                requirement_type TEXT NOT NULL,

                importance_weight
                    REAL NOT NULL DEFAULT 1.0,

                mandatory
                    INTEGER NOT NULL DEFAULT 0,

                confidence
                    REAL NOT NULL DEFAULT 0.0,

                source TEXT,

                recruiter_verified
                    INTEGER NOT NULL DEFAULT 0,

                created_at TEXT NOT NULL,

                FOREIGN KEY (job_id)
                    REFERENCES jobs(job_id)
            )
            """
        )


        # RESUME ENTITIES

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS resume_entities (

                entity_id INTEGER PRIMARY KEY AUTOINCREMENT,

                resume_id INTEGER NOT NULL,

                entity_text TEXT NOT NULL,

                entity_label TEXT NOT NULL,

                start_char INTEGER,

                end_char INTEGER,

                confidence REAL,

                source TEXT NOT NULL,

                created_at TEXT NOT NULL,

                FOREIGN KEY (resume_id)
                    REFERENCES resumes(resume_id)
            )
            """
        )


        # ====================================================
        # DATABASE MIGRATION
        # ====================================================
        #
        # Existing database from previous versions may not have
        # the requirements_confirmed column.
        #
        # Check before adding.
        #
        # ====================================================

        cursor.execute(
            """
            PRAGMA table_info(jobs)
            """
        )

        job_columns = {
            row["name"]
            for row in cursor.fetchall()
        }

        if "requirements_confirmed" not in job_columns:

            cursor.execute(
                """
                ALTER TABLE jobs
                ADD COLUMN requirements_confirmed
                INTEGER NOT NULL DEFAULT 0
                """
            )

        # ====================================================
        # PART 6 - FAIRNESS EVALUATION TABLES
        # ====================================================

        # DEMOGRAPHIC AUDIT DATA
        # Demographic attributes are stored separately from resumes.
        # They must never be used for candidate screening.


# DEMOGRAPHIC AUDIT DATA
# Demographic attributes are stored separately from resumes.
# They must never be used for candidate screening.

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS fairness_audit_data (
                audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id INTEGER NOT NULL,
                attribute_name TEXT NOT NULL,
                attribute_value TEXT,
                availability_status TEXT NOT NULL DEFAULT 'UNKNOWN',
                data_source TEXT,
                is_simulated INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,

                FOREIGN KEY (application_id)
                    REFERENCES applications(application_id),

                UNIQUE(application_id, attribute_name),

                CHECK (availability_status IN (
                    'AVAILABLE',
                    'MISSING',
                    'DECLINED',
                    'NOT_COLLECTED',
                    'UNKNOWN'
                )),

                CHECK (is_simulated IN (0, 1))
            )
            """
        )

# Migration: add is_simulated to existing fairness audit table


        cursor.execute("""
            PRAGMA table_info(fairness_audit_data)
            """)

        audit_columns = {
            row["name"]
            for row in cursor.fetchall()
        }

        if "is_simulated" not in audit_columns:
            cursor.execute("""
                ALTER TABLE fairness_audit_data
                ADD COLUMN is_simulated INTEGER NOT NULL DEFAULT 0
                """)

        # SCREENING OUTCOMES
        # Records actual or explicitly simulated outcomes.
        # 1 = selected, 0 = not selected.
        # No outcome is recorded until a decision exists.

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS fairness_screening_outcomes (
                outcome_id INTEGER PRIMARY KEY AUTOINCREMENT,

                application_id INTEGER NOT NULL UNIQUE,

                favourable_outcome INTEGER NOT NULL,

                is_simulated INTEGER NOT NULL DEFAULT 0,

                outcome_source TEXT,

                recorded_at TEXT NOT NULL,

                FOREIGN KEY (application_id)
                    REFERENCES applications(application_id),

                CHECK (favourable_outcome IN (0, 1)),

                CHECK (is_simulated IN (0, 1))
            )
            """
        )


        # PART 6C - QUALIFICATION LABELS
        # Qualification must be independently assessed using job-related criteria.

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS fairness_qualification_labels (
                qualification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id INTEGER NOT NULL UNIQUE,
                is_qualified INTEGER NOT NULL,
                is_simulated INTEGER NOT NULL DEFAULT 0,
                qualification_source TEXT,
                recorded_at TEXT NOT NULL,

                FOREIGN KEY (application_id)
                    REFERENCES applications(application_id),

                CHECK (is_qualified IN (0, 1)),
                CHECK (is_simulated IN (0, 1))
            )
            """
        )


        connection.commit()

    finally:

        connection.close()


# JOB CREATION

def create_job(
    job_title: str,
    seniority_level: str,
    description: str,
    source_filename: Optional[str]
) -> int:

    connection = get_connection()

    try:

        cursor = connection.cursor()

        created_at = datetime.now(
            timezone.utc
        ).isoformat()

        cursor.execute(
            """
            INSERT INTO jobs (
                job_title,
                seniority_level,
                description,
                source_filename,
                status,
                requirements_confirmed,
                created_at
            )
            VALUES (
                ?,
                ?,
                ?,
                ?,
                'DRAFT',
                0,
                ?
            )
            """,
            (
                job_title.strip(),
                seniority_level,
                description,
                source_filename,
                created_at,
            )
        )

        connection.commit()

        return int(
            cursor.lastrowid
        )

    finally:

        connection.close()


# GET ALL JOBS

def get_all_jobs():

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT *
            FROM jobs
            ORDER BY job_id DESC
            """
        )

        return cursor.fetchall()

    finally:

        connection.close()


# GET ONE JOB

def get_job(
    job_id: int
):

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT *
            FROM jobs
            WHERE job_id = ?
            """,
            (job_id,)
        )

        return cursor.fetchone()

    finally:

        connection.close()


# UPDATE JOB STATUS

def update_job_status(
    job_id: int,
    status: str
) -> None:

    allowed_statuses = {
        "DRAFT",
        "ACTIVE",
        "CLOSED"
    }

    if status not in allowed_statuses:

        raise ValueError(
            f"Invalid job status: {status}"
        )

    connection = get_connection()

    try:

        cursor = connection.cursor()

        # ----------------------------------------------------
        # A job must have recruiter-confirmed requirements
        # before becoming ACTIVE.
        # ----------------------------------------------------

        if status == "ACTIVE":

            cursor.execute(
                """
                SELECT requirements_confirmed
                FROM jobs
                WHERE job_id = ?
                """,
                (job_id,)
            )

            row = cursor.fetchone()

            if row is None:

                raise ValueError(
                    "Job does not exist."
                )

            if row["requirements_confirmed"] != 1:

                raise ValueError(
                    "Requirements must be confirmed "
                    "before the job can become ACTIVE."
                )

        cursor.execute(
            """
            UPDATE jobs
            SET status = ?
            WHERE job_id = ?
            """,
            (
                status,
                job_id
            )
        )

        connection.commit()

    finally:

        connection.close()


# JOB REQUIREMENT FUNCTIONS

def delete_job_requirements(
    job_id: int
) -> None:

    connection = get_connection()

    try:

        cursor = connection.cursor()

        # Delete existing ESCO mappings first.
        cursor.execute(
            """
            DELETE FROM job_requirement_esco_mappings
            WHERE requirement_id IN (
                SELECT requirement_id
                FROM job_requirements
                WHERE job_id = ?
            )
            """,
            (job_id,)
        )

        # Delete the original job requirements.
        cursor.execute(
            """
            DELETE FROM job_requirements
            WHERE job_id = ?
            """,
            (job_id,)
        )

        cursor.execute(
            """
            UPDATE jobs
            SET requirements_confirmed = 0
            WHERE job_id = ?
            """,
            (job_id,)
        )

        connection.commit()

    except Exception:

        connection.rollback()
        raise

    finally:

        connection.close()


def create_job_requirement(
    job_id: int,
    requirement_text: str,
    category: str,
    requirement_type: str,
    importance_weight: float,
    mandatory: bool,
    confidence: float,
    source: str,
    recruiter_verified: bool = False,
) -> int:

    connection = get_connection()

    try:

        cursor = connection.cursor()

        created_at = datetime.now(
            timezone.utc
        ).isoformat()

        cursor.execute(
            """
            INSERT INTO job_requirements (
                job_id,
                requirement_text,
                category,
                requirement_type,
                importance_weight,
                mandatory,
                confidence,
                source,
                recruiter_verified,
                created_at
            )
            VALUES (
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?
            )
            """,
            (
                job_id,
                requirement_text.strip(),
                category,
                requirement_type,
                importance_weight,
                int(mandatory),
                confidence,
                source,
                int(recruiter_verified),
                created_at,
            )
        )

        connection.commit()

        return int(
            cursor.lastrowid
        )

    finally:

        connection.close()


def get_job_requirements(
    job_id: int
):

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT *
            FROM job_requirements
            WHERE job_id = ?
            ORDER BY mandatory DESC,
                     importance_weight DESC,
                     requirement_id ASC
            """,
            (job_id,)
        )

        return cursor.fetchall()

    finally:

        connection.close()


def update_job_requirement(
    requirement_id: int,
    job_id: int,
    requirement_text: str,
    category: str,
    requirement_type: str,
    importance_weight: float,
    mandatory: bool,
    confidence: float,
    source: str,
    recruiter_verified: bool = True,
) -> None:

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            UPDATE job_requirements
            SET requirement_text = ?,
                category = ?,
                requirement_type = ?,
                importance_weight = ?,
                mandatory = ?,
                confidence = ?,
                source = ?,
                recruiter_verified = ?
            WHERE requirement_id = ?
              AND job_id = ?
            """,
            (
                requirement_text.strip(),
                category,
                requirement_type,
                importance_weight,
                int(mandatory),
                confidence,
                source,
                int(recruiter_verified),
                requirement_id,
                job_id,
            )
        )

        if cursor.rowcount != 1:
            raise ValueError(
                f"Requirement ID {requirement_id} "
                "was not found for this job."
            )

        connection.commit()

    except Exception:

        connection.rollback()
        raise

    finally:

        connection.close()


def confirm_job_requirements(
    job_id: int
) -> None:

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT COUNT(*) AS requirement_count
            FROM job_requirements
            WHERE job_id = ?
            """,
            (job_id,)
        )

        result = cursor.fetchone()

        if result["requirement_count"] == 0:

            raise ValueError(
                "At least one requirement is needed "
                "before confirmation."
            )

        cursor.execute(
            """
            UPDATE job_requirements
            SET recruiter_verified = 1
            WHERE job_id = ?
            """,
            (job_id,)
        )

        cursor.execute(
            """
            UPDATE jobs
            SET requirements_confirmed = 1,
                status = 'DRAFT'
            WHERE job_id = ?
            """,
            (job_id,)
        )

        connection.commit()

    finally:

        connection.close()


# CANDIDATE FUNCTIONS

def create_candidate(
    blind_id: str
) -> int:

    connection = get_connection()

    try:

        cursor = connection.cursor()

        created_at = datetime.now(
            timezone.utc
        ).isoformat()

        cursor.execute(
            """
            INSERT INTO candidates (
                blind_id,
                created_at
            )
            VALUES (
                ?,
                ?
            )
            """,
            (
                blind_id,
                created_at
            )
        )

        connection.commit()

        return int(
            cursor.lastrowid
        )

    finally:

        connection.close()


# RESUME FUNCTIONS

def resume_hash_exists(
    file_hash: str
) -> bool:

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT resume_id
            FROM resumes
            WHERE file_hash = ?
            LIMIT 1
            """,
            (file_hash,)
        )

        return (
            cursor.fetchone()
            is not None
        )

    finally:

        connection.close()


def create_resume(
    candidate_id: int,
    original_filename: str,
    stored_filename: str,
    stored_path: str,
    file_hash: str,
    extracted_text: str,
    extraction_status: str,
    parser_version: str,
) -> int:

    connection = get_connection()

    try:

        cursor = connection.cursor()

        created_at = datetime.now(
            timezone.utc
        ).isoformat()

        cursor.execute(
            """
            INSERT INTO resumes (
                candidate_id,
                original_filename,
                stored_filename,
                stored_path,
                file_hash,
                extracted_text,
                extraction_status,
                parser_version,
                created_at
            )
            VALUES (
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?
            )
            """,
            (
                candidate_id,
                original_filename,
                stored_filename,
                stored_path,
                file_hash,
                extracted_text,
                extraction_status,
                parser_version,
                created_at,
            )
        )

        connection.commit()

        return int(
            cursor.lastrowid
        )

    finally:

        connection.close()


# GET ALL RESUMES

def get_all_resumes():

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                r.*,
                c.blind_id
            FROM resumes r
            JOIN candidates c
                ON r.candidate_id = c.candidate_id
            ORDER BY r.resume_id DESC
            """
        )

        return cursor.fetchall()

    finally:

        connection.close()


# GET RESUMES FOR JOB

def get_job_resumes(
    job_id: int
):

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                r.*,
                c.blind_id,
                a.application_status
            FROM applications a

            JOIN resumes r
                ON a.resume_id = r.resume_id

            JOIN candidates c
                ON a.candidate_id = c.candidate_id

            WHERE a.job_id = ?

            ORDER BY r.resume_id DESC
            """,
            (job_id,)
        )

        return cursor.fetchall()

    finally:

        connection.close()


# APPLICATION FUNCTIONS

def create_application(
    candidate_id: int,
    job_id: int,
    resume_id: int,
) -> Optional[int]:

    connection = get_connection()

    try:

        cursor = connection.cursor()

        created_at = datetime.now(
            timezone.utc
        ).isoformat()

        try:

            cursor.execute(
                """
                INSERT INTO applications (
                    candidate_id,
                    job_id,
                    resume_id,
                    application_status,
                    created_at
                )
                VALUES (
                    ?,
                    ?,
                    ?,
                    'RECEIVED',
                    ?
                )
                """,
                (
                    candidate_id,
                    job_id,
                    resume_id,
                    created_at,
                )
            )

            connection.commit()

            return int(
                cursor.lastrowid
            )

        except sqlite3.IntegrityError:

            return None

    finally:

        connection.close()


def get_job_applications(
    job_id: int
):

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                a.application_id,
                a.application_status,
                a.created_at,

                c.blind_id,

                r.resume_id,
                r.original_filename,
                r.extraction_status

            FROM applications a

            JOIN candidates c
                ON a.candidate_id = c.candidate_id

            JOIN resumes r
                ON a.resume_id = r.resume_id

            WHERE a.job_id = ?

            ORDER BY a.application_id DESC
            """,
            (job_id,)
        )

        return cursor.fetchall()

    finally:

        connection.close()


# GET APPLICATION DETAILS FOR QUALIFICATION ASSESSMENT

def get_application_assessment_details(
    application_id: Optional[int] = None
):
    """
    Retrieve application, candidate, resume and job details
    for the independent qualification assessment workflow.
    """

    connection = get_connection()

    try:

        cursor = connection.cursor()

        query = """
            SELECT
                a.application_id,
                a.application_status,
                a.created_at AS application_created_at,
                c.blind_id,
                c.name AS candidate_name,
                c.email AS candidate_email,
                c.phone AS candidate_phone,
                r.resume_id,
                r.original_filename,
                r.extracted_text,
                r.extraction_status,
                j.job_id,
                j.job_title,
                j.seniority_level,
                j.description AS job_description,
                j.status AS job_status,
                j.requirements_confirmed
            FROM applications a
            JOIN candidates c ON a.candidate_id = c.candidate_id
            JOIN resumes r ON a.resume_id = r.resume_id
            JOIN jobs j ON a.job_id = j.job_id
        """

        parameters = ()

        if application_id is not None:

            query += """
                WHERE a.application_id = ?
            """

            parameters = (application_id,)

        query += """
            ORDER BY a.application_id DESC
        """

        cursor.execute(query, parameters)

        if application_id is not None:
            return cursor.fetchone()

        return cursor.fetchall()

    finally:

        connection.close()


# RESUME ENTITY FUNCTIONS

def delete_resume_entities(
    resume_id: int
) -> None:
    """
    Delete previous NER results and their ESCO mappings.

    This allows the resume to be analyzed again after
    the NER pipeline has been improved.
    """

    connection = get_connection()

    try:

        cursor = connection.cursor()

        # Delete existing ESCO mappings first.
        cursor.execute(
            """
            DELETE FROM resume_entity_esco_mappings
            WHERE entity_id IN (
                SELECT entity_id
                FROM resume_entities
                WHERE resume_id = ?
            )
            """,
            (resume_id,)
        )

        # Delete the original resume entities.
        cursor.execute(
            """
            DELETE FROM resume_entities
            WHERE resume_id = ?
            """,
            (resume_id,)
        )

        connection.commit()

    except Exception:

        connection.rollback()
        raise

    finally:

        connection.close()


def create_resume_entity(
    resume_id: int,
    entity_text: str,
    entity_label: str,
    start_char: Optional[int],
    end_char: Optional[int],
    confidence: Optional[float],
    source: str,
) -> int:
    """
    Save one entity extracted from a resume.
    """

    connection = get_connection()

    try:

        cursor = connection.cursor()

        created_at = datetime.now(
            timezone.utc
        ).isoformat()

        cursor.execute(
            """
            INSERT INTO resume_entities (
                resume_id,
                entity_text,
                entity_label,
                start_char,
                end_char,
                confidence,
                source,
                created_at
            )
            VALUES (
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?
            )
            """,
            (
                resume_id,
                entity_text,
                entity_label,
                start_char,
                end_char,
                confidence,
                source,
                created_at,
            )
        )

        connection.commit()

        return int(
            cursor.lastrowid
        )

    finally:

        connection.close()


def get_resume_entities(
    resume_id: int
):

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT *
            FROM resume_entities
            WHERE resume_id = ?
            ORDER BY start_char ASC,
                     entity_id ASC
            """,
            (resume_id,)
        )

        return cursor.fetchall()

    finally:

        connection.close()


# ============================================================
# PART 6 - FAIRNESS EVALUATION DATABASE FUNCTIONS
# ============================================================


# SAVE DEMOGRAPHIC AUDIT DATA

def save_fairness_audit_data(
    application_id: int,
    attribute_name: str,
    attribute_value: Optional[str],
    availability_status: str,
    data_source: Optional[str] = None,
    is_simulated: bool = False,
) -> int:
    """
    Save or update demographic audit information.

    Demographic information is used only for fairness
    evaluation, not candidate screening.
    """

    allowed_statuses = {
        "AVAILABLE",
        "MISSING",
        "DECLINED",
        "NOT_COLLECTED",
        "UNKNOWN",
    }

    if availability_status not in allowed_statuses:
        raise ValueError("Invalid availability status.")

    if not isinstance(is_simulated, bool):
        raise ValueError("is_simulated must be True or False.")

    if not attribute_name or not attribute_name.strip():
        raise ValueError("Attribute name cannot be empty.")

    attribute_name = attribute_name.strip()

    if availability_status == "AVAILABLE":
        if attribute_value is None or not attribute_value.strip():
            raise ValueError(
                "An attribute value is required when status is AVAILABLE."
            )
        attribute_value = attribute_value.strip()
    else:
        if attribute_value is not None:
            raise ValueError(
                "Do not store demographic values when data is unavailable."
            )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        created_at = datetime.now(timezone.utc).isoformat()

        cursor.execute(
            """
            INSERT INTO fairness_audit_data (
                application_id,
                attribute_name,
                attribute_value,
                availability_status,
                data_source,
                is_simulated,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(application_id, attribute_name)
            DO UPDATE SET
                attribute_value = excluded.attribute_value,
                availability_status = excluded.availability_status,
                data_source = excluded.data_source,
                is_simulated = excluded.is_simulated,
                created_at = excluded.created_at
            """,
            (
                application_id,
                attribute_name,
                attribute_value,
                availability_status,
                data_source,
                int(is_simulated),
                created_at,
            )
        )

        connection.commit()

        cursor.execute(
            """
            SELECT audit_id
            FROM fairness_audit_data
            WHERE application_id = ?
              AND attribute_name = ?
            """,
            (application_id, attribute_name)
        )

        return int(cursor.fetchone()["audit_id"])

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# GET DEMOGRAPHIC AUDIT DATA

def get_fairness_audit_data(
    application_id: Optional[int] = None,
    include_simulated: bool = False
):
    """
    Retrieve demographic audit information.

    By default, simulated records are excluded.
    """

    if not isinstance(include_simulated, bool):
        raise ValueError("include_simulated must be True or False.")

    connection = get_connection()

    try:
        cursor = connection.cursor()

        query = """
            SELECT *
            FROM fairness_audit_data
        """

        conditions = []
        parameters = []

        if application_id is not None:
            conditions.append("application_id = ?")
            parameters.append(application_id)

        if not include_simulated:
            conditions.append("is_simulated = 0")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY application_id, attribute_name"

        cursor.execute(query, parameters)

        return cursor.fetchall()

    finally:
        connection.close()


# RECORD SCREENING OUTCOME

def record_screening_outcome(
    application_id: int,
    favourable_outcome: int,
    is_simulated: bool = False,
    outcome_source: Optional[str] = None,
) -> int:
    """
    Record a screening decision.

    favourable_outcome:
        1 = Selected
        0 = Not selected

    is_simulated:
        False = Actual outcome
        True = Simulated outcome
    """

    if favourable_outcome not in (0, 1):
        raise ValueError(
            "Favourable outcome must be 0 or 1."
        )

    if is_simulated not in (True, False, 0, 1):
        raise ValueError(
            "is_simulated must be True or False."
        )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        recorded_at = datetime.now(timezone.utc).isoformat()

        cursor.execute(
            """
            INSERT INTO fairness_screening_outcomes (
                application_id,
                favourable_outcome,
                is_simulated,
                outcome_source,
                recorded_at
            )
            VALUES (?, ?, ?, ?, ?)

            ON CONFLICT(application_id)
            DO UPDATE SET
                favourable_outcome = excluded.favourable_outcome,
                is_simulated = excluded.is_simulated,
                outcome_source = excluded.outcome_source,
                recorded_at = excluded.recorded_at
            """,
            (
                application_id,
                int(favourable_outcome),
                int(is_simulated),
                outcome_source,
                recorded_at,
            )
        )

        connection.commit()

        cursor.execute(
            """
            SELECT outcome_id
            FROM fairness_screening_outcomes
            WHERE application_id = ?
            """,
            (application_id,)
        )

        return int(cursor.fetchone()["outcome_id"])

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# GET SCREENING OUTCOMES

def get_screening_outcomes(
    include_simulated: bool = False
):
    """
    Retrieve screening outcomes.

    By default, only actual screening outcomes
    are returned.
    """

    connection = get_connection()

    try:
        cursor = connection.cursor()

        if include_simulated:

            cursor.execute(
                """
                SELECT *
                FROM fairness_screening_outcomes
                ORDER BY application_id
                """
            )

        else:

            cursor.execute(
                """
                SELECT *
                FROM fairness_screening_outcomes
                WHERE is_simulated = 0
                ORDER BY application_id
                """
            )

        return cursor.fetchall()

    finally:
        connection.close()


def save_qualification_label(
    application_id: int,
    is_qualified: bool,
    is_simulated: bool = False,
    qualification_source: str = None
):
    """Save or update an independently verified qualification label."""

    if not isinstance(is_qualified, bool):
        raise ValueError("is_qualified must be True or False.")

    if not isinstance(is_simulated, bool):
        raise ValueError("is_simulated must be True or False.")

    from datetime import datetime

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO fairness_qualification_labels (
                application_id,
                is_qualified,
                is_simulated,
                qualification_source,
                recorded_at
            )
            VALUES (?, ?, ?, ?, ?)

            ON CONFLICT(application_id)
            DO UPDATE SET
                is_qualified = excluded.is_qualified,
                is_simulated = excluded.is_simulated,
                qualification_source = excluded.qualification_source,
                recorded_at = excluded.recorded_at
            """,
            (
                application_id,
                int(is_qualified),
                int(is_simulated),
                qualification_source,
                datetime.now().isoformat(timespec="seconds")
            )
        )

        connection.commit()

    finally:
        connection.close()


def get_qualification_labels(include_simulated=False):
    """Retrieve qualification labels, excluding simulated data by default."""

    if not isinstance(include_simulated, bool):
        raise ValueError("include_simulated must be True or False.")

    connection = get_connection()

    try:
        cursor = connection.cursor()

        query = """
            SELECT *
            FROM fairness_qualification_labels
        """

        if not include_simulated:
            query += " WHERE is_simulated = 0"

        query += " ORDER BY application_id"

        cursor.execute(query)

        return cursor.fetchall()

    finally:
        connection.close()