import csv
import sqlite3
from pathlib import Path

from esco_db import get_esco_connection


BASE_DIR = Path(__file__).resolve().parent
ESCO_DIR = BASE_DIR / "data" / "esco" / "extracted"

SKILLS_FILE = ESCO_DIR / "skills_en.csv"
OCCUPATIONS_FILE = ESCO_DIR / "occupations_en.csv"
RELATIONS_FILE = ESCO_DIR / "occupationSkillRelations_en.csv"

ESCO_VERSION = "1.2.1"
ESCO_LANGUAGE = "en"

def validate_csv_file(file_path, required_columns):
    """Check that a CSV file exists and contains required columns."""

    if not file_path.exists():
        raise FileNotFoundError(f"ESCO file not found: {file_path}")

    with file_path.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as csv_file:

        reader = csv.DictReader(csv_file)

        if not reader.fieldnames:
            raise ValueError(f"CSV file has no header: {file_path}")

        missing_columns = set(required_columns) - set(reader.fieldnames)

        if missing_columns:
            raise ValueError(
                f"Missing columns in {file_path.name}: {missing_columns}"
            )

    print(f"Validated: {file_path.name}")

def validate_esco_files():
    """Validate the three core ESCO classification files."""

    validate_csv_file(
        SKILLS_FILE,
        ["conceptUri", "preferredLabel", "skillType"]
    )

    validate_csv_file(
        OCCUPATIONS_FILE,
        ["conceptUri", "preferredLabel", "iscoGroup"]
    )

    validate_csv_file(
        RELATIONS_FILE,
        [
            "occupationUri",
            "occupationLabel",
            "relationType",
            "skillType",
            "skillUri",
            "skillLabel"
        ]
    )

    print("\nAll three ESCO files passed validation.")


def import_esco_skills(conn):
    """Import ESCO skill concepts into the database."""

    query = """
    INSERT INTO esco_skills (
        skill_uri,
        concept_type,
        skill_type,
        reuse_level,
        preferred_label,
        alt_labels,
        hidden_labels,
        status,
        modified_date,
        scope_note,
        definition,
        in_scheme,
        description,
        language,
        version
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(skill_uri) DO UPDATE SET
        concept_type = excluded.concept_type,
        skill_type = excluded.skill_type,
        reuse_level = excluded.reuse_level,
        preferred_label = excluded.preferred_label,
        alt_labels = excluded.alt_labels,
        hidden_labels = excluded.hidden_labels,
        status = excluded.status,
        modified_date = excluded.modified_date,
        scope_note = excluded.scope_note,
        definition = excluded.definition,
        in_scheme = excluded.in_scheme,
        description = excluded.description,
        language = excluded.language,
        version = excluded.version
    """

    records = []

    try:
        with SKILLS_FILE.open(
            "r",
            encoding="utf-8-sig",
            newline=""
        ) as csv_file:

            reader = csv.DictReader(csv_file)

            for row in reader:
                records.append((
                    row["conceptUri"],
                    row["conceptType"],
                    row["skillType"],
                    row["reuseLevel"],
                    row["preferredLabel"],
                    row["altLabels"],
                    row["hiddenLabels"],
                    row["status"],
                    row["modifiedDate"],
                    row["scopeNote"],
                    row["definition"],
                    row["inScheme"],
                    row["description"],
                    ESCO_LANGUAGE,
                    ESCO_VERSION
                ))

        conn.executemany(query, records)

        print(f"Successfully imported {len(records)} ESCO skills.")

    except Exception:
     raise


def import_esco_occupations(conn):
    """Import ESCO occupation concepts into the database."""

    query = """
        INSERT INTO esco_occupations (
            occupation_uri,
            concept_type,
            isco_group,
            preferred_label,
            alt_labels,
            hidden_labels,
            status,
            modified_date,
            regulated_profession_note,
            scope_note,
            definition,
            in_scheme,
            description,
            code,
            nace_code,
            language,
            version
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(occupation_uri) DO UPDATE SET
            concept_type = excluded.concept_type,
            isco_group = excluded.isco_group,
            preferred_label = excluded.preferred_label,
            alt_labels = excluded.alt_labels,
            hidden_labels = excluded.hidden_labels,
            status = excluded.status,
            modified_date = excluded.modified_date,
            regulated_profession_note = excluded.regulated_profession_note,
            scope_note = excluded.scope_note,
            definition = excluded.definition,
            in_scheme = excluded.in_scheme,
            description = excluded.description,
            code = excluded.code,
            nace_code = excluded.nace_code,
            language = excluded.language,
            version = excluded.version
    """

    records = []

    try:
        with OCCUPATIONS_FILE.open(
            "r",
            encoding="utf-8-sig",
            newline=""
        ) as csv_file:

            reader = csv.DictReader(csv_file)

            for row in reader:
                records.append((
                    row["conceptUri"],
                    row["conceptType"],
                    row["iscoGroup"],
                    row["preferredLabel"],
                    row["altLabels"],
                    row["hiddenLabels"],
                    row["status"],
                    row["modifiedDate"],
                    row["regulatedProfessionNote"],
                    row["scopeNote"],
                    row["definition"],
                    row["inScheme"],
                    row["description"],
                    row["code"],
                    row["naceCode"],
                    ESCO_LANGUAGE,
                    ESCO_VERSION
                ))

        conn.executemany(query, records)

        print(f"Successfully imported {len(records)} ESCO occupations.")

    except Exception:
        raise

def import_esco_occupation_skill_relations(conn):
    """Import relationships between ESCO occupations and skills."""

    query = """
        INSERT INTO esco_occupation_skill_relations (
            occupation_uri,
            skill_uri,
            relation_type,
            skill_type
        )
        VALUES (?, ?, ?, ?)
        ON CONFLICT(occupation_uri, skill_uri, relation_type)
        DO UPDATE SET
            skill_type = excluded.skill_type
    """

    records = []

    try:
        with RELATIONS_FILE.open(
            "r",
            encoding="utf-8-sig",
            newline=""
        ) as csv_file:

            reader = csv.DictReader(csv_file)

            for row in reader:
                records.append((
                    row["occupationUri"],
                    row["skillUri"],
                    row["relationType"],
                    row["skillType"]
                ))

        conn.executemany(query, records)

        print(
            f"Successfully imported "
            f"{len(records)} occupation-skill relationships."
        )

    except Exception:
        raise

def import_all_esco_data():
    """Import all ESCO datasets in one database transaction."""

    print("\nStarting ESCO taxonomy import...\n")

    conn = get_esco_connection()

    try:
        import_esco_skills(conn)
        import_esco_occupations(conn)
        import_esco_occupation_skill_relations(conn)

        conn.commit()
        print("\nESCO taxonomy import completed successfully.")

    except Exception:
        conn.rollback()
        print("\nESCO import failed. All changes have been rolled back.")
        raise

    finally:
        conn.close()

if __name__ == "__main__":
    validate_esco_files()
    import_all_esco_data()