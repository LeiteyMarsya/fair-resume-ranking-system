# SQLite data layer for the resume screening system.
# Handles job creation, requirement tracking, candidate uploads,
# and the application workflow used by the Fair Resume Ranking System.

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional


# Configuration
BASE_DIR = Path(__file__).resolve().parent
DATABASE_DIR = BASE_DIR / "data" / "database"
DB_PATH = DATABASE_DIR / "resume_system.db"

DATABASE_DIR.mkdir(parents=True, exist_ok=True)

JOB_STATUS_DRAFT = "DRAFT"
JOB_STATUS_ACTIVE = "ACTIVE"
JOB_STATUS_CLOSED = "CLOSED"
ALLOWED_JOB_STATUSES = {JOB_STATUS_DRAFT, JOB_STATUS_ACTIVE, JOB_STATUS_CLOSED}

APPLICATION_STATUS_RECEIVED = "RECEIVED"


# Connection helpers

def get_connection() -> sqlite3.Connection:
    """
    Open a new SQLite connection.

    - Rows can be read like dictionaries (row["column_name"]).
    - Foreign keys are switched ON. SQLite ignores them by default,
      which would allow rows that point to records that don't exist.
    """
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    """
    Run a block of database work as a single transaction.

    - Commits automatically if the block succeeds.
    - Rolls back everything if an error is raised, so we never end up
      with half-finished changes.
    - Always closes the connection.

    Usage:
        with transaction() as conn:
            conn.execute("UPDATE ...")
    """
    connection = get_connection()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _utc_now() -> str:
    """Current UTC time as an ISO-8601 string (used for created_at columns)."""
    return datetime.now(timezone.utc).isoformat()


# Database initialization
_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS jobs (
        job_id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        job_title               TEXT    NOT NULL,
        seniority_level         TEXT    NOT NULL,
        description             TEXT    NOT NULL,
        source_filename         TEXT,
        status                  TEXT    NOT NULL DEFAULT 'DRAFT',
        requirements_confirmed  INTEGER NOT NULL DEFAULT 0,
        created_at              TEXT    NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS candidates (
        candidate_id  INTEGER PRIMARY KEY AUTOINCREMENT,
        blind_id      TEXT NOT NULL UNIQUE,
        name          TEXT,
        email         TEXT,
        phone         TEXT,
        created_at    TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS resumes (
        resume_id          INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_id       INTEGER NOT NULL,
        original_filename  TEXT    NOT NULL,
        stored_filename    TEXT    NOT NULL,
        stored_path        TEXT    NOT NULL,
        file_hash          TEXT    NOT NULL,
        extracted_text     TEXT,
        extraction_status  TEXT    NOT NULL,
        parser_version     TEXT    NOT NULL,
        created_at         TEXT    NOT NULL,

        FOREIGN KEY (candidate_id) REFERENCES candidates(candidate_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS applications (
        application_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_id        INTEGER NOT NULL,
        job_id              INTEGER NOT NULL,
        resume_id           INTEGER NOT NULL,
        application_status  TEXT    NOT NULL DEFAULT 'RECEIVED',
        created_at          TEXT    NOT NULL,

        FOREIGN KEY (candidate_id) REFERENCES candidates(candidate_id),
        FOREIGN KEY (job_id)       REFERENCES jobs(job_id),
        FOREIGN KEY (resume_id)    REFERENCES resumes(resume_id),

        UNIQUE (candidate_id, job_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS job_requirements (
        requirement_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id              INTEGER NOT NULL,
        requirement_text    TEXT    NOT NULL,
        category            TEXT    NOT NULL,
        requirement_type    TEXT    NOT NULL,
        importance_weight   REAL    NOT NULL DEFAULT 1.0,
        mandatory           INTEGER NOT NULL DEFAULT 0,
        confidence          REAL    NOT NULL DEFAULT 0.0,
        source              TEXT,
        recruiter_verified  INTEGER NOT NULL DEFAULT 0,
        created_at          TEXT    NOT NULL,

        FOREIGN KEY (job_id) REFERENCES jobs(job_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_requirements_job ON job_requirements(job_id)",
    "CREATE INDEX IF NOT EXISTS idx_applications_job  ON applications(job_id)",
    "CREATE INDEX IF NOT EXISTS idx_resumes_hash      ON resumes(file_hash)",
)


def _add_column_if_missing(
    connection: sqlite3.Connection,
    table: str,
    column: str,
    definition: str,
) -> None:
    """
    Lightweight migration helper.

    CREATE TABLE IF NOT EXISTS does NOT add new columns to a table that
    already exists. If an older database is missing a column, this adds it.

    NOTE: `table`, `column` and `definition` are inserted directly into the
    SQL, so only pass hard-coded strings here, never user input.
    """
    existing_columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table})")
    }

    if column not in existing_columns:
        connection.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
        )


def init_database() -> None:
    """Create all tables and indexes, and upgrade older databases."""
    with transaction() as connection:

        for statement in _SCHEMA_STATEMENTS:
            connection.execute(statement)

        # Migration: older databases were created without this column.
        _add_column_if_missing(
            connection,
            table="jobs",
            column="requirements_confirmed",
            definition="INTEGER NOT NULL DEFAULT 0",
        )


# Jobs

def create_job(
    job_title: str,
    seniority_level: str,
    description: str,
    source_filename: Optional[str],
) -> int:
    """
    Create a new job in DRAFT status.

    Returns the new job_id.
    """
    with transaction() as connection:
        cursor = connection.execute(
            """
            INSERT INTO jobs (
                job_title, seniority_level, description,
                source_filename, status, requirements_confirmed, created_at
            )
            VALUES (?, ?, ?, ?, ?, 0, ?)
            """,
            (
                job_title.strip(),
                seniority_level,
                description,
                source_filename,
                JOB_STATUS_DRAFT,
                _utc_now(),
            ),
        )
        return int(cursor.lastrowid)


def get_all_jobs() -> list[sqlite3.Row]:
    """Return every job, newest first."""
    with transaction() as connection:
        return connection.execute(
            "SELECT * FROM jobs ORDER BY job_id DESC"
        ).fetchall()


def get_job(job_id: int) -> Optional[sqlite3.Row]:
    """Return one job, or None if it doesn't exist."""
    with transaction() as connection:
        return connection.execute(
            "SELECT * FROM jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()


def update_job_status(job_id: int, status: str) -> None:
    """
    Change a job's status (DRAFT, ACTIVE or CLOSED).

    Fairness rule:
        A job cannot become ACTIVE until the recruiter has confirmed its
        requirements. This stops candidates being scored against
        requirements nobody has reviewed.

    Raises:
        ValueError: invalid status, unknown job, or unconfirmed requirements.
    """
    if status not in ALLOWED_JOB_STATUSES:
        raise ValueError(f"Invalid job status: {status}")

    with transaction() as connection:

        if status == JOB_STATUS_ACTIVE:
            row = connection.execute(
                "SELECT requirements_confirmed FROM jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()

            if row is None:
                raise ValueError("Job does not exist.")

            if row["requirements_confirmed"] != 1:
                raise ValueError(
                    "Requirements must be confirmed by the recruiter "
                    "before the job can become ACTIVE."
                )

        connection.execute(
            "UPDATE jobs SET status = ? WHERE job_id = ?",
            (status, job_id),
        )


# Job requirements

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
    """
    Save one requirement for a job.

    Returns the new requirement_id.
    """
    with transaction() as connection:
        cursor = connection.execute(
            """
            INSERT INTO job_requirements (
                job_id, requirement_text, category, requirement_type,
                importance_weight, mandatory, confidence, source,
                recruiter_verified, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                requirement_text.strip(),
                category,
                requirement_type,
                importance_weight,
                int(mandatory),          # SQLite stores booleans as 0/1
                confidence,
                source,
                int(recruiter_verified),
                _utc_now(),
            ),
        )
        return int(cursor.lastrowid)


def get_job_requirements(job_id: int) -> list[sqlite3.Row]:
    """
    Return a job's requirements, most important first:
    mandatory ones, then by weight (highest first), then in creation order.
    """
    with transaction() as connection:
        return connection.execute(
            """
            SELECT *
            FROM job_requirements
            WHERE job_id = ?
            ORDER BY mandatory DESC,
                     importance_weight DESC,
                     requirement_id ASC
            """,
            (job_id,),
        ).fetchall()


def delete_job_requirements(job_id: int) -> None:
    """
    Delete all requirements for a job.

    Use this before re-analyzing a job description. It also resets the
    job's "confirmed" flag, because new requirements need a new review.
    Both steps happen in one transaction, so they succeed or fail together.
    """
    with transaction() as connection:
        connection.execute(
            "DELETE FROM job_requirements WHERE job_id = ?",
            (job_id,),
        )
        connection.execute(
            "UPDATE jobs SET requirements_confirmed = 0 WHERE job_id = ?",
            (job_id,),
        )


def confirm_job_requirements(job_id: int) -> None:
    """
    Recruiter sign-off: mark every requirement as verified and flag the
    job as confirmed. The job stays in DRAFT until explicitly activated.

    Raises:
        ValueError: if the job has no requirements to confirm.
    """
    with transaction() as connection:

        count = connection.execute(
            "SELECT COUNT(*) AS n FROM job_requirements WHERE job_id = ?",
            (job_id,),
        ).fetchone()["n"]

        if count == 0:
            raise ValueError(
                "At least one requirement is needed before confirmation."
            )

        connection.execute(
            "UPDATE job_requirements SET recruiter_verified = 1 WHERE job_id = ?",
            (job_id,),
        )
        connection.execute(
            """
            UPDATE jobs
            SET requirements_confirmed = 1,
                status = ?
            WHERE job_id = ?
            """,
            (JOB_STATUS_DRAFT, job_id),
        )


# Candidates

def create_candidate(blind_id: str) -> int:
    """
    Create a candidate identified only by an anonymous blind_id.

    Returns the new candidate_id.

    Raises:
        sqlite3.IntegrityError: if the blind_id already exists.
    """
    with transaction() as connection:
        cursor = connection.execute(
            "INSERT INTO candidates (blind_id, created_at) VALUES (?, ?)",
            (blind_id, _utc_now()),
        )
        return int(cursor.lastrowid)


# Resumes

def resume_hash_exists(file_hash: str) -> bool:
    """Return True if a resume with this file hash was already uploaded."""
    with transaction() as connection:
        row = connection.execute(
            "SELECT 1 FROM resumes WHERE file_hash = ? LIMIT 1",
            (file_hash,),
        ).fetchone()
        return row is not None


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
    Save a resume record.

    Returns the new resume_id.
    """
    with transaction() as connection:
        cursor = connection.execute(
            """
            INSERT INTO resumes (
                candidate_id, original_filename, stored_filename,
                stored_path, file_hash, extracted_text,
                extraction_status, parser_version, created_at
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
                _utc_now(),
            ),
        )
        return int(cursor.lastrowid)


# Applications

def create_application(
    candidate_id: int,
    job_id: int,
    resume_id: int,
) -> Optional[int]:
    """
    Register a candidate's application to a job.

    Returns the new application_id, or None if the candidate has already
    applied to this job (or a referenced record doesn't exist).
    """
    try:
        with transaction() as connection:
            cursor = connection.execute(
                """
                INSERT INTO applications (
                    candidate_id, job_id, resume_id,
                    application_status, created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    job_id,
                    resume_id,
                    APPLICATION_STATUS_RECEIVED,
                    _utc_now(),
                ),
            )
            return int(cursor.lastrowid)

    except sqlite3.IntegrityError:
        # Duplicate (candidate_id, job_id) or a broken foreign key.
        return None


def get_job_applications(job_id: int) -> list[sqlite3.Row]:
    """
    Return all applications for a job, newest first.

    Only the candidate's blind_id is exposed (no name/email/phone),
    which keeps the review process anonymous.
    """
    with transaction() as connection:
        return connection.execute(
            """
            SELECT
                a.application_id,
                a.application_status,
                a.created_at,
                c.blind_id,
                r.resume_id,
                r.original_filename,
                r.extraction_status
            FROM applications AS a
            JOIN candidates   AS c ON a.candidate_id = c.candidate_id
            JOIN resumes      AS r ON a.resume_id    = r.resume_id
            WHERE a.job_id = ?
            ORDER BY a.application_id DESC
            """,
            (job_id,),
        ).fetchall()
