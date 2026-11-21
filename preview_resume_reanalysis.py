
import sqlite3
from collections import Counter
from pathlib import Path
from urllib.parse import quote

import db
from resume_ner import extract_resume_entities


DB_PATH = Path(db.DB_PATH)
BACKUP_PATH = DB_PATH.with_name(
    "resume_system_before_part7a_reanalysis_20261121.db"
)


def get_value(entity, *keys):
    """Get the first available value from an entity dictionary."""
    for key in keys:
        if key in entity:
            return entity[key]
    return None


def normalize_new_entity(entity):
    return {
        "text": str(get_value(entity, "text", "entity_text") or "").strip(),
        "label": str(get_value(entity, "label", "entity_label") or "").strip(),
        "start": get_value(entity, "start", "start_char"),
        "end": get_value(entity, "end", "end_char"),
    }


def match_entities(old_entities, new_entities):
    """
    Match entities one-to-one using the same general strategy
    as the reconciliation function:
    1. Exact text, label and offsets.
    2. Same text and label, closest start offset.
    """

    unmatched_old = set(range(len(old_entities)))
    unmatched_new = set(range(len(new_entities)))

    exact_matches = 0
    shifted_matches = 0

    # First pass: exact occurrence matching.
    for new_index, new in enumerate(new_entities):
        for old_index in list(unmatched_old):
            old = old_entities[old_index]

            if (
                old["text"] == new["text"]
                and old["label"] == new["label"]
                and old["start"] == new["start"]
                and old["end"] == new["end"]
            ):
                unmatched_old.remove(old_index)
                unmatched_new.remove(new_index)
                exact_matches += 1
                break

    # Second pass: same text and label, closest start offset.
    for new_index in list(unmatched_new):
        new = new_entities[new_index]

        candidates = [
            old_index
            for old_index in unmatched_old
            if (
                old_entities[old_index]["text"] == new["text"]
                and old_entities[old_index]["label"] == new["label"]
            )
        ]

        if candidates:
            def distance(old_index):
                old_start = old_entities[old_index]["start"]
                new_start = new["start"]

                if old_start is None or new_start is None:
                    return float("inf")

                return abs(old_start - new_start)

            best_old_index = min(candidates, key=distance)

            unmatched_old.remove(best_old_index)
            unmatched_new.remove(new_index)
            shifted_matches += 1

    return {
        "exact": exact_matches,
        "shifted": shifted_matches,
        "obsolete_indices": unmatched_old,
        "new_indices": unmatched_new,
    }


def main():
    print("RESUME RE-ANALYSIS PREVIEW")
    print("=" * 65)
    print("DATABASE:", DB_PATH)
    print("MODE: READ ONLY")
    print("BACKUP EXISTS:", BACKUP_PATH.exists())
    print()

    if not DB_PATH.exists():
        print("ERROR: Database file was not found.")
        return

    db_uri = (
    "file:"
    + quote(DB_PATH.resolve().as_posix(), safe="/:")
    + "?mode=ro"
)

    connection = sqlite3.connect(
        db_uri,
        uri=True
        )
    connection.row_factory = sqlite3.Row

    totals = Counter()
    errors = []

    try:
        resumes = connection.execute(
            """
            SELECT resume_id, extracted_text
            FROM resumes
            ORDER BY resume_id
            """
        ).fetchall()

        print("RESUMES FOUND:", len(resumes))
        print("-" * 65)

        for resume in resumes:
            resume_id = resume["resume_id"]
            resume_text = resume["extracted_text"] or ""

            try:
                old_rows = connection.execute(
                    """
                    SELECT entity_id, entity_text, entity_label,
                           start_char, end_char
                    FROM resume_entities
                    WHERE resume_id = ?
                    ORDER BY entity_id
                    """,
                    (resume_id,)
                ).fetchall()

                old_entities = [
                    {
                        "entity_id": row["entity_id"],
                        "text": row["entity_text"].strip(),
                        "label": row["entity_label"].strip(),
                        "start": row["start_char"],
                        "end": row["end_char"],
                    }
                    for row in old_rows
                ]

                if resume_text.strip():
                    extraction_result = extract_resume_entities(resume_text)
                    raw_new_entities = extraction_result["entities"]
                    new_entities = [
                        normalize_new_entity(entity)
                        for entity in raw_new_entities
                    ]
                    new_entities = [
                        entity for entity in new_entities
                        if entity["text"] and entity["label"]
                    ]
                else:
                    new_entities = []

                matches = match_entities(old_entities, new_entities)

                obsolete_indices = matches["obsolete_indices"]
                new_indices = matches["new_indices"]

                obsolete_entity_ids = [
                    old_entities[index]["entity_id"]
                    for index in obsolete_indices
                ]

                affected_mappings = 0

                if obsolete_entity_ids:
                    placeholders = ",".join(
                        "?" for _ in obsolete_entity_ids
                    )
                    affected_mappings = connection.execute(
                        f"""
                        SELECT COUNT(*)
                        FROM resume_entity_esco_mappings
                        WHERE entity_id IN ({placeholders})
                        """,
                        obsolete_entity_ids
                    ).fetchone()[0]

                result = {
                    "old": len(old_entities),
                    "new": len(new_entities),
                    "exact": matches["exact"],
                    "shifted": matches["shifted"],
                    "obsolete": len(obsolete_indices),
                    "inserted": len(new_indices),
                    "mappings": affected_mappings,
                }

                for key, value in result.items():
                    totals[key] += value

                print(
                    f"Resume {resume_id:>3} | "
                    f"Old: {result['old']:>3} | "
                    f"New: {result['new']:>3} | "
                    f"Exact: {result['exact']:>3} | "
                    f"Shifted: {result['shifted']:>3} | "
                    f"Remove: {result['obsolete']:>3} | "
                    f"Insert: {result['inserted']:>3} | "
                    f"Mappings affected: {result['mappings']:>3}"
                )

            except Exception as error:
                errors.append((resume_id, str(error)))
                print(f"Resume {resume_id}: ERROR - {error}")

        print()
        print("=" * 65)
        print("OVERALL PREVIEW")
        print("=" * 65)
        print("Old entities:", totals["old"])
        print("New extracted entities:", totals["new"])
        print("Exact matches:", totals["exact"])
        print("Shifted matches:", totals["shifted"])
        print("Potentially obsolete entities:", totals["obsolete"])
        print("Potentially inserted entities:", totals["inserted"])
        print("Existing mappings potentially affected:", totals["mappings"])
        print("Resumes with errors:", len(errors))

        if errors:
            print()
            print("ERROR DETAILS:")
            for resume_id, error in errors:
                print(f"Resume {resume_id}: {error}")

        print()
        print("PREVIEW COMPLETE - NO DATABASE WRITES PERFORMED.")

    finally:
        connection.close()


if __name__ == "__main__":
    main()
