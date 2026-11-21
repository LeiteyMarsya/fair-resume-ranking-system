
import shutil
import tempfile
from pathlib import Path

import db


def insert_entity(
    conn,
    resume_id,
    text,
    label,
    start,
    end,
):
    cursor = conn.execute(
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
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            resume_id,
            text,
            label,
            start,
            end,
            0.95,
            "REGEX",
            "2026-11-21T00:00:00+00:00",
        )
    )

    return cursor.lastrowid


def insert_mapping(conn, entity_id, skill_uri, reviewed=0):
    conn.execute(
        """
        INSERT INTO resume_entity_esco_mappings (
            entity_id,
            skill_uri,
            mapping_method,
            mapping_score,
            mapping_status,
            reviewed
        )
        VALUES (?, ?, 'TEST', NULL, 'PENDING', ?)
        """,
        (entity_id, skill_uri, reviewed)
    )


def clear_resume_entities(conn, resume_id):
    conn.execute(
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

    conn.execute(
        """
        DELETE FROM resume_entities
        WHERE resume_id = ?
        """,
        (resume_id,)
    )

    conn.commit()


def get_entities(conn, resume_id):
    return conn.execute(
        """
        SELECT *
        FROM resume_entities
        WHERE resume_id = ?
        ORDER BY start_char, entity_id
        """,
        (resume_id,)
    ).fetchall()


def run_test():

    original_db = Path(db.DB_PATH)

    with tempfile.TemporaryDirectory() as temp_dir:

        test_db = Path(temp_dir) / "resume_system_test.db"

        shutil.copy2(original_db, test_db)

        # Redirect all db.py operations to the temporary copy.
        db.DB_PATH = test_db

        conn = db.get_connection()

        try:

            resume = conn.execute(
                """
                SELECT resume_id
                FROM resumes
                LIMIT 1
                """
            ).fetchone()

            skill = conn.execute(
                """
                SELECT skill_uri
                FROM esco_skills
                LIMIT 1
                """
            ).fetchone()

            assert resume is not None, "No resume found."
            assert skill is not None, "No ESCO skill found."

            resume_id = resume["resume_id"]
            skill_uri = skill["skill_uri"]

            clear_resume_entities(conn, resume_id)

            # ==========================================
            # TEST 1: EXACT MATCH AND DUPLICATE SKILLS
            # ==========================================

            python_1 = insert_entity(
                conn, resume_id, "Python", "SKILL", 10, 16
            )

            python_2 = insert_entity(
                conn, resume_id, "Python", "SKILL", 30, 36
            )

            insert_mapping(conn, python_1, skill_uri)
            insert_mapping(conn, python_2, skill_uri)

            conn.commit()
            conn.close()

            result = db.reconcile_resume_entities(
                resume_id,
                [
                    {
                        "text": "Python",
                        "label": "SKILL",
                        "start": 10,
                        "end": 16,
                        "confidence": 0.95,
                        "source": "REGEX",
                    },
                    {
                        "text": "Python",
                        "label": "SKILL",
                        "start": 30,
                        "end": 36,
                        "confidence": 0.95,
                        "source": "REGEX",
                    },
                ]
            )

            conn = db.get_connection()

            entities = get_entities(conn, resume_id)

            ids = {row["entity_id"] for row in entities}

            mappings = conn.execute(
                """
                SELECT COUNT(*)
                FROM resume_entity_esco_mappings
                WHERE entity_id IN (?, ?)
                """,
                (python_1, python_2)
            ).fetchone()[0]

            assert ids == {python_1, python_2}
            assert mappings == 2
            assert result["preserved"] == 2

            print("TEST 1 - Exact duplicate matching: PASS")

            # ==========================================
            # TEST 2: SHIFTED ENTITY POSITIONS
            # ==========================================

            conn.close()

            result = db.reconcile_resume_entities(
                resume_id,
                [
                    {
                        "text": "Python",
                        "label": "SKILL",
                        "start": 12,
                        "end": 18,
                        "confidence": 0.90,
                        "source": "SPACY_NER",
                    },
                    {
                        "text": "Python",
                        "label": "SKILL",
                        "start": 32,
                        "end": 38,
                        "confidence": 0.90,
                        "source": "SPACY_NER",
                    },
                ]
            )

            conn = db.get_connection()

            entities = get_entities(conn, resume_id)

            ids = {row["entity_id"] for row in entities}

            assert ids == {python_1, python_2}
            assert result["updated"] == 2

            mappings = conn.execute(
                """
                SELECT COUNT(*)
                FROM resume_entity_esco_mappings
                WHERE entity_id IN (?, ?)
                """,
                (python_1, python_2)
            ).fetchone()[0]

            assert mappings == 2

            print("TEST 2 - Shifted positions: PASS")

            # ==========================================
            # TEST 3: INSERT NEW AND REMOVE OBSOLETE
            # ==========================================

            obsolete = insert_entity(
                conn, resume_id, "OldSkill", "SKILL", 50, 58
            )

            obsolete_without_mapping = insert_entity(
                conn, resume_id, "OldProject", "PROJECT", 70, 80
            )

            insert_mapping(conn, obsolete, skill_uri)

            conn.commit()
            conn.close()

            result = db.reconcile_resume_entities(
                resume_id,
                [
                    {
                        "text": "Python",
                        "label": "SKILL",
                        "start": 12,
                        "end": 18,
                        "confidence": 0.90,
                        "source": "SPACY_NER",
                    },
                    {
                        "text": "Python",
                        "label": "SKILL",
                        "start": 32,
                        "end": 38,
                        "confidence": 0.90,
                        "source": "SPACY_NER",
                    },
                    {
                        "text": "SQL",
                        "label": "SKILL",
                        "start": 90,
                        "end": 93,
                        "confidence": 0.98,
                        "source": "REGEX",
                    },
                ]
            )

            conn = db.get_connection()

            entities = get_entities(conn, resume_id)

            texts = [row["entity_text"] for row in entities]

            assert "SQL" in texts
            assert "OldSkill" not in texts
            assert "OldProject" not in texts
            assert result["inserted"] == 1
            assert result["removed"] == 2
            assert result["mappings_removed"] == 1

            remaining_mapping = conn.execute(
                """
                SELECT COUNT(*)
                FROM resume_entity_esco_mappings
                WHERE entity_id IN (?, ?)
                """,
                (python_1, python_2)
            ).fetchone()[0]

            assert remaining_mapping == 2

            print("TEST 3 - Insert and remove obsolete entities: PASS")

            # ==========================================
            # TEST 4: PROTECT REVIEWED MAPPINGS
            # ==========================================

            protected = insert_entity(
                conn, resume_id, "ProtectedSkill", "SKILL", 110, 124
            )

            insert_mapping(
                conn,
                protected,
                skill_uri,
                reviewed=1
            )

            conn.commit()
            conn.close()

            try:

                db.reconcile_resume_entities(
                    resume_id,
                    [
                        {
                            "text": "Python",
                            "label": "SKILL",
                            "start": 12,
                            "end": 18,
                            "confidence": 0.90,
                            "source": "SPACY_NER",
                        },
                        {
                            "text": "Python",
                            "label": "SKILL",
                            "start": 32,
                            "end": 38,
                            "confidence": 0.90,
                            "source": "SPACY_NER",
                        },
                        {
                            "text": "SQL",
                            "label": "SKILL",
                            "start": 90,
                            "end": 93,
                            "confidence": 0.98,
                            "source": "REGEX",
                        },
                    ]
                )

                raise AssertionError(
                    "Reviewed mapping was not protected."
                )

            except ValueError as error:

                assert "Manual review is required" in str(error)

            conn = db.get_connection()

            protected_entity = conn.execute(
                """
                SELECT entity_id
                FROM resume_entities
                WHERE entity_id = ?
                """,
                (protected,)
            ).fetchone()

            assert protected_entity is not None

            sql_count = conn.execute(
                """
                SELECT COUNT(*)
                FROM resume_entities
                WHERE resume_id = ?
                AND entity_text = 'SQL'
                """,
                (resume_id,)
            ).fetchone()[0]

            assert sql_count == 1

            print("TEST 4 - Reviewed mapping protection and rollback: PASS")

            # ==========================================
            # TEST 5: FOREIGN KEY INTEGRITY
            # ==========================================

            violations = conn.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()

            assert not violations, violations

            print("TEST 5 - Foreign key integrity: PASS")

        finally:

            conn.close()

    # Restore the original path in this test process.
    db.DB_PATH = original_db

    print("\nALL RECONCILIATION TESTS PASSED.")
    print("Original database was not modified.")


if __name__ == "__main__":
    run_test()
