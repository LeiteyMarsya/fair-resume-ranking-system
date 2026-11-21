
import shutil
import tempfile
from pathlib import Path

import db
import esco_db

from job_requirement_esco_mapper import (
    generate_job_requirement_esco_proposals,
)


original_db_path = db.DB_PATH
original_esco_path = esco_db.DATABASE_PATH

with tempfile.TemporaryDirectory() as temp_directory:

    test_database = Path(temp_directory) / "test_resume_system.db"

    shutil.copy2(original_db_path, test_database)

    # Redirect BOTH database connections.
    db.DB_PATH = test_database
    esco_db.DATABASE_PATH = test_database

    try:
        print("=" * 60)
        print("PART 5E END-TO-END WORKFLOW TEST")
        print("=" * 60)

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

        finally:
            conn.close()

        if job is None:
            raise RuntimeError(
                "No job with SKILL requirements was found."
            )

        job_id = job["job_id"]

        requirements = db.get_job_requirements(job_id)

        print(f"\nTesting Job ID: {job_id}")
        print(f"Requirements found: {len(requirements)}")

        # ------------------------------------------------
        # TEST 1: Preserve requirement IDs and mappings
        # ------------------------------------------------

        print("\nTEST 1: REQUIREMENT UPDATE")

        original_ids = {
            item["requirement_id"]
            for item in requirements
        }

        # Add a temporary test mapping if necessary.
        # This guarantees that mapping preservation
        # can be tested even when no mapping exists yet.

        conn = db.get_connection()

        try:
            first_skill = next(
                item for item in requirements
                if item["category"] == "SKILL"
            )

            existing_mapping = conn.execute("""
                SELECT mapping_id
                FROM job_requirement_esco_mappings
                WHERE requirement_id = ?
            """, (first_skill["requirement_id"],)).fetchone()

            if existing_mapping is None:

                skill = conn.execute("""
                    SELECT skill_uri
                    FROM esco_skills
                    LIMIT 1
                """).fetchone()

                if skill is None:
                    raise RuntimeError(
                        "No ESCO skills available for testing."
                    )

                conn.execute("""
                    INSERT INTO job_requirement_esco_mappings (
                        requirement_id,
                        skill_uri,
                        mapping_method,
                        mapping_score,
                        mapping_status,
                        reviewed
                    )
                    VALUES (?, ?, 'TEST_SENTINEL', 100, 'PENDING', 0)
                """, (
                    first_skill["requirement_id"],
                    skill["skill_uri"],
                ))

                conn.commit()

        finally:
            conn.close()

        # Snapshot existing mappings.
        conn = db.get_connection()

        try:
            original_mappings = {
                row["mapping_id"]: tuple(row)
                for row in conn.execute("""
                    SELECT *
                    FROM job_requirement_esco_mappings
                    ORDER BY mapping_id
                """).fetchall()
            }

            resume_mapping_count_before = conn.execute("""
                SELECT COUNT(*)
                FROM resume_entity_esco_mappings
            """).fetchone()[0]

        finally:
            conn.close()

        # Simulate recruiter confirmation:
        # Update existing records without recreating them.

        for item in requirements:

            db.update_job_requirement(
                requirement_id=item["requirement_id"],
                job_id=job_id,
                requirement_text=item["requirement_text"],
                category=item["category"],
                requirement_type=item["requirement_type"],
                importance_weight=item["importance_weight"],
                mandatory=item["mandatory"],
                confidence=1.0,
                source="RECRUITER_VERIFIED",
                recruiter_verified=True,
            )

        db.confirm_job_requirements(job_id)

        updated_requirements = db.get_job_requirements(job_id)

        updated_ids = {
            item["requirement_id"]
            for item in updated_requirements
        }

        assert original_ids == updated_ids, (
            "Requirement IDs changed!"
        )

        print("PASS: Existing requirement IDs preserved.")

        # ------------------------------------------------
        # TEST 2: Existing ESCO mappings preserved
        # ------------------------------------------------

        conn = db.get_connection()

        try:
            current_mappings = {
                row["mapping_id"]: tuple(row)
                for row in conn.execute("""
                    SELECT *
                    FROM job_requirement_esco_mappings
                    ORDER BY mapping_id
                """).fetchall()
            }

        finally:
            conn.close()

        for mapping_id, original_record in original_mappings.items():

            assert current_mappings.get(mapping_id) == original_record, (
                f"Existing mapping {mapping_id} was changed or deleted."
            )

        print("PASS: Existing ESCO mappings preserved.")

        # ------------------------------------------------
        # TEST 3: Generate ESCO proposals
        # ------------------------------------------------

        print("\nTEST 3: ESCO PROPOSAL GENERATION")

        result = generate_job_requirement_esco_proposals(job_id)

        assert result["status"] == "SUCCESS", (
            "Proposal generation failed."
        )

        print("Status:", result["status"])
        print("New proposals:", result["inserted"])

        # ------------------------------------------------
        # TEST 4: Pending status and human review
        # ------------------------------------------------

        conn = db.get_connection()

        try:
            new_mappings = conn.execute("""
                SELECT *
                FROM job_requirement_esco_mappings
                ORDER BY mapping_id
            """).fetchall()

            new_proposals = [
                row for row in new_mappings
                if row["mapping_id"] not in original_mappings
            ]

            for proposal in new_proposals:

                assert proposal["mapping_status"] == "PENDING"
                assert proposal["reviewed"] == 0

        finally:
            conn.close()

        print("PASS: New proposals are PENDING and unreviewed.")

        # ------------------------------------------------
        # TEST 5: Mapper does not modify requirements
        # ------------------------------------------------

        requirements_before_mapper = [
            tuple(item)
            for item in updated_requirements
        ]

        requirements_after_mapper = [
            tuple(item)
            for item in db.get_job_requirements(job_id)
        ]

        assert (
            requirements_before_mapper
            == requirements_after_mapper
        ), "Mapper modified recruiter-confirmed requirements."

        print("PASS: Recruiter-confirmed requirements unchanged.")

        # ------------------------------------------------
        # TEST 6: Part 5D mappings remain untouched
        # ------------------------------------------------

        conn = db.get_connection()

        try:
            resume_mapping_count_after = conn.execute("""
                SELECT COUNT(*)
                FROM resume_entity_esco_mappings
            """).fetchone()[0]

            foreign_key_errors = conn.execute("""
                PRAGMA foreign_key_check
            """).fetchall()

        finally:
            conn.close()

        assert (
            resume_mapping_count_before
            == resume_mapping_count_after
        ), "Part 5D mapping count changed!"

        assert not foreign_key_errors, (
            f"Foreign key errors: {foreign_key_errors}"
        )

        print("PASS: Part 5D mapping count unchanged.")
        print("PASS: No foreign key violations.")

        print("\n" + "=" * 60)
        print("ALL PART 5E WORKFLOW TESTS PASSED")
        print("=" * 60)

    finally:

        # Restore original database paths.
        db.DB_PATH = original_db_path
        esco_db.DATABASE_PATH = original_esco_path

print("\nOriginal database was not modified.")
