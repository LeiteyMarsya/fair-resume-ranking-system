
import sqlite3

from esco_db import get_esco_connection


# ============================================================
# PART 1: GET OCCUPATION REVIEW COUNTS
# ============================================================

def get_occupation_review_counts():
    """
    Retrieve the number of pending, approved and rejected
    ESCO occupation mapping proposals.
    """

    conn = get_esco_connection()

    try:

        cursor = conn.cursor()

        cursor.execute("""
            SELECT

                COALESCE(
                    SUM(
                        CASE
                            WHEN mapping_status = 'PENDING'
                            AND reviewed = 0
                            THEN 1 ELSE 0
                        END
                    ), 0
                ) AS pending_count,

                COALESCE(
                    SUM(
                        CASE
                            WHEN mapping_status = 'APPROVED'
                            AND reviewed = 1
                            THEN 1 ELSE 0
                        END
                    ), 0
                ) AS approved_count,

                COALESCE(
                    SUM(
                        CASE
                            WHEN mapping_status = 'REJECTED'
                            AND reviewed = 1
                            THEN 1 ELSE 0
                        END
                    ), 0
                ) AS rejected_count

            FROM job_esco_occupation_mappings
        """)

        result = cursor.fetchone()

        return dict(result)

    finally:

        conn.close()


# ============================================================
# PART 2: GET PENDING OCCUPATION PROPOSALS
# ============================================================

def get_pending_occupation_proposals():
    """
    Retrieve all pending ESCO occupation proposals.

    Job information and ESCO occupation information are
    retrieved using SQL JOIN operations.
    """

    conn = get_esco_connection()

    try:

        cursor = conn.cursor()

        cursor.execute("""
            SELECT

                m.mapping_id,
                m.job_id,
                m.occupation_uri,
                m.mapping_method,
                m.mapping_score,
                m.mapping_status,
                m.reviewed,
                m.created_at,

                j.job_title,
                j.seniority_level,
                j.description,

                o.preferred_label,
                o.code,
                o.isco_group,
                o.definition,
                o.scope_note

            FROM job_esco_occupation_mappings AS m

            INNER JOIN jobs AS j
                ON m.job_id = j.job_id

            INNER JOIN esco_occupations AS o
                ON m.occupation_uri = o.occupation_uri

            WHERE
                m.mapping_status = 'PENDING'
                AND m.reviewed = 0

            ORDER BY m.created_at DESC
        """)

        results = cursor.fetchall()

        return [dict(row) for row in results]

    finally:

        conn.close()


# ============================================================
# PART 3: SAVE RECRUITER REVIEW DECISION
# ============================================================

def save_occupation_review(mapping_id, decision):
    """
    Save a recruiter's approval or rejection decision.

    Only pending and unreviewed proposals can be updated.

    Approved:
        mapping_status = 'APPROVED'
        reviewed = 1

    Rejected:
        mapping_status = 'REJECTED'
        reviewed = 1
    """

    decision = str(decision).strip().upper()

    # Validate the review decision.

    if decision not in ("APPROVED", "REJECTED"):

        return {
            "status": "INVALID_DECISION"
        }

    # Validate the mapping ID.

    try:

        mapping_id = int(mapping_id)

        if mapping_id <= 0:
            raise ValueError

    except (TypeError, ValueError):

        return {
            "status": "INVALID_MAPPING_ID"
        }

    conn = get_esco_connection()

    try:

        cursor = conn.cursor()

        cursor.execute("""
            UPDATE job_esco_occupation_mappings

            SET
                mapping_status = ?,
                reviewed = 1

            WHERE
                mapping_id = ?
                AND mapping_status = 'PENDING'
                AND reviewed = 0

        """, (
            decision,
            mapping_id
        ))

        # Check whether a pending proposal was updated.

        if cursor.rowcount == 0:

            conn.rollback()

            return {
                "status": "NOT_PENDING_OR_NOT_FOUND"
            }

        conn.commit()

        return {
            "status": "SUCCESS",
            "mapping_id": mapping_id,
            "decision": decision
        }

    except Exception:

        conn.rollback()

        raise

    finally:

        conn.close()


# ============================================================
# PART 4: GET JOB REQUIREMENTS FOR OCCUPATION REVIEW
# ============================================================

def get_job_requirements_for_occupation_review(job_id):
    """
    Retrieve job requirements and their ESCO skill mappings
    for recruiter occupation review.

    Requirements are separated into recruiter-confirmed
    and unconfirmed groups.

    No database records are modified.
    """

    try:

        job_id = int(job_id)

        if job_id <= 0:
            raise ValueError

    except (TypeError, ValueError):

        return {
            "status": "INVALID_JOB_ID",
            "confirmed": [],
            "unconfirmed": []
        }

    conn = get_esco_connection()

    try:

        cursor = conn.cursor()

        cursor.execute("""
            SELECT

                r.requirement_id,
                r.requirement_text,
                r.category,
                r.requirement_type,
                r.importance_weight,
                r.mandatory,
                r.confidence,
                r.recruiter_verified,

                m.skill_uri,
                m.mapping_method,
                m.mapping_score,
                m.mapping_status,
                m.reviewed,

                s.preferred_label AS esco_skill_label

            FROM job_requirements AS r

            LEFT JOIN job_requirement_esco_mappings AS m
                ON r.requirement_id = m.requirement_id

            LEFT JOIN esco_skills AS s
                ON m.skill_uri = s.skill_uri

            WHERE r.job_id = ?

            ORDER BY
                r.recruiter_verified DESC,
                r.requirement_id ASC

        """, (job_id,))

        rows = cursor.fetchall()

        confirmed = []
        unconfirmed = []

        # Group multiple ESCO skill mappings under
        # their original job requirement.

        grouped_requirements = {}

        for row in rows:

            requirement_id = row["requirement_id"]

            if requirement_id not in grouped_requirements:

                grouped_requirements[requirement_id] = {

                    "requirement_id": requirement_id,
                    "requirement_text": row["requirement_text"],
                    "category": row["category"],
                    "requirement_type": row["requirement_type"],
                    "importance_weight": row["importance_weight"],
                    "mandatory": row["mandatory"],
                    "confidence": row["confidence"],
                    "recruiter_verified": row["recruiter_verified"],
                    "esco_skills": []

                }

            if row["skill_uri"]:

                grouped_requirements[requirement_id][
                    "esco_skills"
                ].append({

                    "skill_uri": row["skill_uri"],
                    "skill_label": row["esco_skill_label"],
                    "mapping_method": row["mapping_method"],
                    "mapping_score": row["mapping_score"],
                    "mapping_status": row["mapping_status"],
                    "reviewed": row["reviewed"]

                })

        for requirement in grouped_requirements.values():

            if requirement["recruiter_verified"] == 1:

                confirmed.append(requirement)

            else:

                unconfirmed.append(requirement)

        return {

            "status": "SUCCESS",
            "confirmed": confirmed,
            "unconfirmed": unconfirmed,
            "total_requirements": len(grouped_requirements)

        }

    finally:

        conn.close()
