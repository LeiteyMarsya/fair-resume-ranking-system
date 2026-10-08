from __future__ import annotations

import sqlite3
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

DB_PATH = DATABASE_DIR / "resume_system.db"


# DATABASE CONNECTION

def get_connection() -> sqlite3.Connection:
    """
    Create a SQLite database connection.
    """

    connection = sqlite3.connect(
        DB_PATH
    )

    connection.row_factory = sqlite3.Row

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


# RESUME ENTITY FUNCTIONS

def delete_resume_entities(
    resume_id: int
) -> None:
    """
    Delete previous NER results for a resume.

    This allows the resume to be analyzed again after
    the NER pipeline has been improved.
    """

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            DELETE FROM resume_entities
            WHERE resume_id = ?
            """,
            (resume_id,)
        )

        connection.commit()

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