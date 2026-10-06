from __future__ import annotations

import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DATABASE_DIR = BASE_DIR / "data" / "database"
DATABASE_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATABASE_DIR / "resume_system.db"


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection() -> sqlite3.Connection:
    """
    Create a connection to the SQLite database.

    SQLite is used for the first local prototype because
    it does not require a separate database server.
    """

    connection = sqlite3.connect(DB_PATH)

    # Allows us to access database columns by column name.
    connection.row_factory = sqlite3.Row

    return connection


# ============================================================
# INITIALIZE DATABASE
# ============================================================

def init_database() -> None:
    """
    Create all initial database tables if they do not exist.
    """

    connection = get_connection()

    try:
        cursor = connection.cursor()

        # ----------------------------------------------------
        # JOBS
        # ----------------------------------------------------

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                job_id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_title TEXT NOT NULL,
                seniority_level TEXT NOT NULL,
                description TEXT NOT NULL,
                source_filename TEXT,
                status TEXT NOT NULL DEFAULT 'DRAFT',
                created_at TEXT NOT NULL
            )
            """
        )

        # ----------------------------------------------------
        # CANDIDATES
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # RESUMES
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # APPLICATIONS
        # ----------------------------------------------------

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS applications (
                application_id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER NOT NULL,
                job_id INTEGER NOT NULL,
                resume_id INTEGER NOT NULL,
                application_status TEXT NOT NULL DEFAULT 'RECEIVED',
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

        connection.commit()

    finally:
        connection.close()


# ============================================================
# JOB FUNCTIONS
# ============================================================

def create_job(
    job_title: str,
    seniority_level: str,
    description: str,
    source_filename: Optional[str]
) -> int:
    """
    Insert a new job into the database.

    Returns:
        The newly created job ID.
    """

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
                created_at
            )
            VALUES (?, ?, ?, ?, 'DRAFT', ?)
            """,
            (
                job_title.strip(),
                seniority_level,
                description,
                source_filename,
                created_at,
            ),
        )

        connection.commit()

        return int(cursor.lastrowid)

    finally:
        connection.close()


def get_all_jobs():
    """
    Return all jobs, newest first.
    """

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


def get_job(job_id: int):
    """
    Return one job using its ID.
    """

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT *
            FROM jobs
            WHERE job_id = ?
            """,
            (job_id,),
        )

        return cursor.fetchone()

    finally:
        connection.close()


def update_job_status(
    job_id: int,
    status: str
) -> None:
    """
    Update job status.

    Allowed values:
        DRAFT
        ACTIVE
        CLOSED
    """

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

        cursor.execute(
            """
            UPDATE jobs
            SET status = ?
            WHERE job_id = ?
            """,
            (
                status,
                job_id,
            ),
        )

        connection.commit()

    finally:
        connection.close()


# ============================================================
# CANDIDATE FUNCTIONS
# ============================================================

def create_candidate(
    blind_id: str
) -> int:
    """
    Create an anonymous candidate record.

    The ranking engine can later use the blind ID
    instead of the candidate's personal identity.
    """

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
            VALUES (?, ?)
            """,
            (
                blind_id,
                created_at,
            ),
        )

        connection.commit()

        return int(cursor.lastrowid)

    finally:
        connection.close()


# ============================================================
# RESUME FUNCTIONS
# ============================================================

def resume_hash_exists(
    file_hash: str
) -> bool:
    """
    Check whether this exact file has already
    been uploaded before.
    """

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
            (file_hash,),
        )

        return cursor.fetchone() is not None

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
    """
    Save resume information and extracted text.
    """

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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            ),
        )

        connection.commit()

        return int(cursor.lastrowid)

    finally:
        connection.close()


# ============================================================
# APPLICATION FUNCTIONS
# ============================================================

def create_application(
    candidate_id: int,
    job_id: int,
    resume_id: int,
) -> Optional[int]:
    """
    Link a candidate and resume to a particular job.

    Returns:
        Application ID if successful.
        None if the application already exists.
    """

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
                VALUES (?, ?, ?, 'RECEIVED', ?)
                """,
                (
                    candidate_id,
                    job_id,
                    resume_id,
                    created_at,
                ),
            )

            connection.commit()

            return int(cursor.lastrowid)

        except sqlite3.IntegrityError:
            return None

    finally:
        connection.close()


def get_job_applications(job_id: int):
    """
    Get all applications belonging to one job.
    """

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
            (job_id,),
        )

        return cursor.fetchall()

    finally:
        connection.close()