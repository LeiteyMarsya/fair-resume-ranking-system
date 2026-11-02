import re


def normalize_skill_label(text):
    """Normalize formatting for matching without changing original text."""
    if not text:
        return ""

    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip().casefold()


def build_esco_label_index(conn):
    """
    Build an exact-label lookup for ESCO skills.

    Preferred labels take priority over alternative labels,
    which take priority over hidden labels.

    Ambiguous labels are excluded from automatic matching.
    """
    label_index = {}

    rows = conn.execute("""
        SELECT skill_uri, preferred_label, alt_labels, hidden_labels
        FROM esco_skills
        WHERE language = 'en'
    """).fetchall()

    for row in rows:
        skill_uri = row["skill_uri"]

        labels = [
            (row["preferred_label"], "EXACT_LABEL", 1),
        ]

        if row["alt_labels"]:
            labels.extend(
                (label, "ALT_LABEL", 2)
                for label in row["alt_labels"].splitlines()
            )

        if row["hidden_labels"]:
            labels.extend(
                (label, "HIDDEN_LABEL", 3)
                for label in row["hidden_labels"].splitlines()
            )

        for label, method, priority in labels:
            normalized = normalize_skill_label(label)

            if not normalized:
                continue

            current = label_index.get(normalized)

            if current is None or priority < current["priority"]:
                label_index[normalized] = {
                    "skill_uri": skill_uri,
                    "preferred_label": row["preferred_label"],
                    "mapping_method": method,
                    "priority": priority,
                    "ambiguous": False,
                }

            elif priority == current["priority"]:
                if skill_uri != current["skill_uri"]:
                    current["ambiguous"] = True

    return label_index

def get_resume_skill_entities(conn):
    """Retrieve original extracted resume skill entities."""
    return conn.execute("""
        SELECT entity_id, resume_id, entity_text
        FROM resume_entities
        WHERE entity_label = 'SKILL'
        ORDER BY entity_id
    """).fetchall()

def generate_resume_skill_proposals(skills, label_index):
    """
    Generate ESCO mapping proposals without changing the database.

    All generated proposals require human review.
    """
    proposals = []
    excluded = []
    unmatched = []

    for row in skills:
        entity_id = row["entity_id"]
        original_text = row["entity_text"]
        normalized = normalize_skill_label(original_text)

        # Exclude the questionable data analysis -> statistics match.
        if normalized == "data analysis":
            excluded.append({
                "entity_id": entity_id,
                "entity_text": original_text,
                "reason": "QUESTIONABLE_MATCH",
            })
            continue

        match = label_index.get(normalized)

        if not match:
            unmatched.append({
                "entity_id": entity_id,
                "entity_text": original_text,
            })
            continue

        if match["ambiguous"]:
            excluded.append({
                "entity_id": entity_id,
                "entity_text": original_text,
                "reason": "AMBIGUOUS_MATCH",
            })
            continue

        proposals.append({
            "entity_id": entity_id,
            "skill_uri": match["skill_uri"],
            "mapping_method": match["mapping_method"],
            "mapping_score": None,
            "mapping_status": "PENDING",
            "reviewed": 0,
        })

    return {
        "proposals": proposals,
        "excluded": excluded,
        "unmatched": unmatched,
    }

def save_resume_skill_proposals(conn, proposals):
    """
    Save mapping proposals without overwriting existing mappings.
    All new mappings remain pending human review.
    """
    inserted = 0

    try:
        for proposal in proposals:
            cursor = conn.execute("""
                INSERT INTO resume_entity_esco_mappings (
                    entity_id,
                    skill_uri,
                    mapping_method,
                    mapping_score,
                    mapping_status,
                    reviewed
                )
                VALUES (?, ?, ?, ?, 'PENDING', 0)
                ON CONFLICT(entity_id, skill_uri) DO NOTHING
            """, (
                proposal["entity_id"],
                proposal["skill_uri"],
                proposal["mapping_method"],
                proposal["mapping_score"],
            ))

            inserted += cursor.rowcount

        conn.commit()
        return inserted

    except Exception:
        conn.rollback()
        raise