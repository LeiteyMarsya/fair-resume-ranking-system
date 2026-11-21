import shutil
import sqlite3
import tempfile
from pathlib import Path

import db
import esco_db
import job_occupation_esco_mapper as occupation_mapper
import job_occupation_esco_review as occupation_review


# Save original database settings and imported functions.
original_db_path = db.DB_PATH
original_esco_path = esco_db.DATABASE_PATH

original_mapper_connection = occupation_mapper.get_esco_connection
original_review_connection = occupation_review.get_esco_connection


# Protect against copying a database with active WAL files.
original_path = Path(original_db_path)

if Path(str(original_path) + "-wal").exists():
    raise RuntimeError("Original database has a WAL file. Test stopped.")

if Path(str(original_path) + "-shm").exists():
    raise RuntimeError("Original database has a SHM file. Test stopped.")


try:
    with tempfile.TemporaryDirectory() as temp_directory:

        test_database = Path(temp_directory) / "test_part5f.db"

        # Copy the original database.
        shutil.copy2(original_path, test_database)

        # Redirect all database connections.
        db.DB_PATH = test_database
        esco_db.DATABASE_PATH = test_database

        occupation_mapper.get_esco_connection = (
            esco_db.get_esco_connection
        )

        occupation_review.get_esco_connection = (
            esco_db.get_esco_connection
        )

        print("=" * 60)
        print("PART 5F DATA INTEGRITY TEST")
        print("=" * 60)

        # ------------------------------------------------
        # Find a job with existing SKILL requirements.
        # ------------------------------------------------

        conn = db.get_connection()

        try:
            job = conn.execute("""
                SELECT j.job_id
                FROM jobs j
                JOIN job_requirements r
                    ON j.job_id = r.job_id
                WHERE r.category = 'SKILL'
                GROUP BY j.job_id
                ORDER BY j.job_id
                LIMIT 1
            """).fetchone()

            occupation = conn.execute("""
                SELECT occupation_uri
                FROM esco_occupations
                ORDER BY occupation_uri
                LIMIT 1
            """).fetchone()

        finally:
            conn.close()

        if job is None:
            raise RuntimeError(
                "No job with SKILL requirements found."
            )

        if occupation is None:
            raise RuntimeError(
                "No ESCO occupations found."
            )

        job_id = job["job_id"]
        occupation_uri = occupation["occupation_uri"]

        print("\nTesting Job ID:", job_id)

        # ------------------------------------------------
        # TEST 1: Insert an occupation mapping.
        # ------------------------------------------------

        print("\nTEST 1: INSERT OCCUPATION MAPPING")

        conn = esco_db.get_esco_connection()

        try:
            cursor = conn.execute("""
                INSERT INTO job_esco_occupation_mappings (
                    job_id,
                    occupation_uri,
                    mapping_method,
                    mapping_score,
                    mapping_status,
                    reviewed
                )
                VALUES (?, ?, 'TEST_SENTINEL', 100, 'PENDING', 0)
            """, (job_id, occupation_uri))

            mapping_id = cursor.lastrowid
            conn.commit()

            print("PASS: Test occupation mapping inserted.")

        finally:
            conn.close()

        # ------------------------------------------------
        # TEST 2: Duplicate prevention.
        # ------------------------------------------------

        print("\nTEST 2: DUPLICATE PREVENTION")

        conn = esco_db.get_esco_connection()

        try:
            duplicate_rejected = False

            try:
                conn.execute("""
                    INSERT INTO job_esco_occupation_mappings (
                        job_id,
                        occupation_uri,
                        mapping_method,
                        mapping_score,
                        mapping_status,
                        reviewed
                    )
                    VALUES (?, ?, 'TEST_DUPLICATE', 100, 'PENDING', 0)
                """, (job_id, occupation_uri))

                conn.commit()

            except sqlite3.IntegrityError:
                duplicate_rejected = True
                conn.rollback()

            assert duplicate_rejected, (
                "Duplicate job-occupation mapping was accepted."
            )

            print("PASS: Duplicate mapping rejected.")

        finally:
            conn.close()

        # ------------------------------------------------
        # TEST 3: Preserve mapping during requirement update.
        # ------------------------------------------------

        print("\nTEST 3: REQUIREMENT UPDATE PRESERVATION")

        requirements = db.get_job_requirements(job_id)

        requirement = next(
            (
                item for item in requirements
                if item["category"] == "SKILL"
            ),
            None
        )

        if requirement is None:
            raise RuntimeError(
                "No SKILL requirement available for update testing."
            )

        conn = esco_db.get_esco_connection()

        try:
            original_mapping = conn.execute("""
                SELECT *
                FROM job_esco_occupation_mappings
                WHERE mapping_id = ?
            """, (mapping_id,)).fetchone()

            original_mapping = tuple(original_mapping)

        finally:
            conn.close()

        db.update_job_requirement(
            requirement_id=requirement["requirement_id"],
            job_id=job_id,
            requirement_text=requirement["requirement_text"],
            category=requirement["category"],
            requirement_type=requirement["requirement_type"],
            importance_weight=requirement["importance_weight"],
            mandatory=requirement["mandatory"],
            confidence=1.0,
            source="RECRUITER_VERIFIED",
            recruiter_verified=True,
        )

        conn = esco_db.get_esco_connection()

        try:
            current_mapping = conn.execute("""
                SELECT *
                FROM job_esco_occupation_mappings
                WHERE mapping_id = ?
            """, (mapping_id,)).fetchone()

            assert current_mapping is not None, (
                "Occupation mapping was deleted during requirement update."
            )

            assert tuple(current_mapping) == original_mapping, (
                "Occupation mapping was changed during requirement update."
            )

            print(
                "PASS: Occupation mapping preserved after "
                "requirement update."
            )

        finally:
            conn.close()

        # ------------------------------------------------
        # TEST 4: Prevent deletion of referenced job.
        # ------------------------------------------------

        print("\nTEST 4: REFERENCED JOB DELETION")

        conn = db.get_connection()

        try:
            deletion_blocked = False

            try:
                conn.execute(
                    "DELETE FROM jobs WHERE job_id = ?",
                    (job_id,)
                )

                conn.commit()

            except sqlite3.IntegrityError:
                deletion_blocked = True
                conn.rollback()

            assert deletion_blocked, (
                "Referenced job deletion was not blocked."
            )

            print("PASS: Referenced job deletion blocked.")

        finally:
            conn.close()

        # ------------------------------------------------
        # TEST 5: Foreign-key integrity.
        # ------------------------------------------------

        print("\nTEST 5: FOREIGN KEY INTEGRITY")

        conn = esco_db.get_esco_connection()

        try:
            violations = conn.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()

            assert not violations, (
                f"Foreign key violations found: {violations}"
            )

            print("PASS: No foreign-key violations.")

            # Verify the test mapping still exists.
            final_mapping = conn.execute("""
                SELECT mapping_status, reviewed
                FROM job_esco_occupation_mappings
                WHERE mapping_id = ?
            """, (mapping_id,)).fetchone()

            assert final_mapping is not None
            assert final_mapping["mapping_status"] == "PENDING"
            assert final_mapping["reviewed"] == 0

            print("PASS: Mapping remains PENDING and unreviewed.")

        finally:
            conn.close()

        print("\n" + "=" * 60)
        print("ALL PART 5F INTEGRITY TESTS PASSED")
        print("=" * 60)

finally:
    # Restore all original paths and imported functions.
    db.DB_PATH = original_db_path
    esco_db.DATABASE_PATH = original_esco_path

    occupation_mapper.get_esco_connection = (
        original_mapper_connection
    )

    occupation_review.get_esco_connection = (
        original_review_connection
    )

print("\nOriginal database was not modified.")
