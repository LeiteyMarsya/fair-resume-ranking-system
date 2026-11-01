import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

DATABASE_PATH = BASE_DIR / "data" / "database" / "resume_system.db"


def get_esco_connection():
    """Connect to the existing resume system database."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def create_esco_tables():
    """Create ESCO taxonomy and mapping tables."""

    conn = get_esco_connection()

    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS esco_skills (
                skill_uri TEXT PRIMARY KEY,
                concept_type TEXT,
                skill_type TEXT,
                reuse_level TEXT,
                preferred_label TEXT NOT NULL,
                alt_labels TEXT,
                hidden_labels TEXT,
                status TEXT,
                modified_date TEXT,
                scope_note TEXT,
                definition TEXT,
                in_scheme TEXT,
                description TEXT,
                language TEXT DEFAULT 'en',
                version TEXT
            );

            CREATE TABLE IF NOT EXISTS esco_occupations (
                occupation_uri TEXT PRIMARY KEY,
                concept_type TEXT,
                isco_group TEXT,
                preferred_label TEXT NOT NULL,
                alt_labels TEXT,
                hidden_labels TEXT,
                status TEXT,
                modified_date TEXT,
                regulated_profession_note TEXT,
                scope_note TEXT,
                definition TEXT,
                in_scheme TEXT,
                description TEXT,
                code TEXT,
                nace_code TEXT,
                language TEXT DEFAULT 'en',
                version TEXT
            );

            CREATE TABLE IF NOT EXISTS esco_occupation_skill_relations (
                relation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                occupation_uri TEXT NOT NULL,
                skill_uri TEXT NOT NULL,
                relation_type TEXT,
                skill_type TEXT,
                FOREIGN KEY (occupation_uri)
                    REFERENCES esco_occupations(occupation_uri),
                FOREIGN KEY (skill_uri)
                    REFERENCES esco_skills(skill_uri),
                UNIQUE (occupation_uri, skill_uri, relation_type)
            );

            CREATE TABLE IF NOT EXISTS resume_entity_esco_mappings (
                mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_id INTEGER NOT NULL,
                skill_uri TEXT NOT NULL,
                mapping_method TEXT,
                mapping_score REAL,
                mapping_status TEXT DEFAULT 'PENDING',
                reviewed INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (entity_id)
                    REFERENCES resume_entities(entity_id),
                FOREIGN KEY (skill_uri)
                    REFERENCES esco_skills(skill_uri),
                UNIQUE (entity_id, skill_uri)
            );

            CREATE TABLE IF NOT EXISTS job_requirement_esco_mappings (
                mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
                requirement_id INTEGER NOT NULL,
                skill_uri TEXT NOT NULL,
                mapping_method TEXT,
                mapping_score REAL,
                mapping_status TEXT DEFAULT 'PENDING',
                reviewed INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (requirement_id)
                    REFERENCES job_requirements(requirement_id),
                FOREIGN KEY (skill_uri)
                    REFERENCES esco_skills(skill_uri),
                UNIQUE (requirement_id, skill_uri)
            );

            CREATE TABLE IF NOT EXISTS job_esco_occupation_mappings (
                mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                occupation_uri TEXT NOT NULL,
                mapping_method TEXT,
                mapping_score REAL,
                mapping_status TEXT DEFAULT 'PENDING',
                reviewed INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (job_id)
                    REFERENCES jobs(job_id),
                FOREIGN KEY (occupation_uri)
                    REFERENCES esco_occupations(occupation_uri),
                UNIQUE (job_id, occupation_uri)
            );

            CREATE INDEX IF NOT EXISTS idx_esco_skills_label
                ON esco_skills(preferred_label);

            CREATE INDEX IF NOT EXISTS idx_esco_occupations_label
                ON esco_occupations(preferred_label);

            CREATE INDEX IF NOT EXISTS idx_resume_esco_entity
                ON resume_entity_esco_mappings(entity_id);

            CREATE INDEX IF NOT EXISTS idx_job_requirement_esco
                ON job_requirement_esco_mappings(requirement_id);

            CREATE INDEX IF NOT EXISTS idx_job_occupation_esco
                ON job_esco_occupation_mappings(job_id);
        """)

        conn.commit()
        print("ESCO tables created successfully.")

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()