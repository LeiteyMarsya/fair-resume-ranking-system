
from esco_db import get_esco_connection
from rapidfuzz import process, fuzz


FUZZY_MATCH_THRESHOLD = 85


def normalize_requirement_label(label):
    """Normalize requirement text for case- and whitespace-insensitive lookup."""
    return " ".join(str(label or "").casefold().split())


def build_esco_requirement_label_index(conn):
    """
    Build an exact-label lookup for English ESCO concepts.

    Preferred labels have priority over alternative labels,
    which have priority over hidden labels.

    Ambiguous labels are preserved and excluded from automatic matching.
    """

    label_index = {}

    rows = conn.execute("""
        SELECT
            skill_uri,
            preferred_label,
            alt_labels,
            hidden_labels
        FROM esco_skills
        WHERE language = 'en'
          AND status = 'released'
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
            normalized = normalize_requirement_label(label)

            if not normalized:
                continue

            current = label_index.get(normalized)

            if current is None:
                label_index[normalized] = {
                    "skill_uri": skill_uri,
                    "preferred_label": row["preferred_label"],
                    "mapping_method": method,
                    "priority": priority,
                    "ambiguous": False,
                    "candidate_uris": {skill_uri},
                }

                continue

            current["candidate_uris"].add(skill_uri)

            if priority < current["priority"]:
                current["skill_uri"] = skill_uri
                current["preferred_label"] = row["preferred_label"]
                current["mapping_method"] = method
                current["priority"] = priority

            if len(current["candidate_uris"]) > 1:
                current["ambiguous"] = True

    return label_index


def match_esco_requirement(
    requirement,
    label_index,
    threshold=FUZZY_MATCH_THRESHOLD
):
    """
    Match a job requirement against ESCO labels.

    Matching priority:
    1. EXACT_LABEL
    2. ALT_LABEL
    3. HIDDEN_LABEL
    4. FUZZY_LABEL
    5. NO_MATCH

    Ambiguous labels are not automatically mapped.
    """

    normalized = normalize_requirement_label(requirement)

    if not normalized:
        return {
            "skill_uri": None,
            "preferred_label": None,
            "mapping_method": "NO_MATCH",
            "similarity_score": 0,
            "ambiguous": False,
        }

    # First, check exact, alternative and hidden labels.
    exact_match = label_index.get(normalized)

    if exact_match is not None:

        if exact_match["ambiguous"]:
            return {
                "skill_uri": None,
                "preferred_label": None,
                "mapping_method": exact_match["mapping_method"],
                "similarity_score": 100,
                "ambiguous": True,
            }

        return {
            "skill_uri": exact_match["skill_uri"],
            "preferred_label": exact_match["preferred_label"],
            "mapping_method": exact_match["mapping_method"],
            "similarity_score": 100,
            "ambiguous": False,
        }

    fuzzy_matches = process.extract(
    normalized,
    label_index.keys(),
    scorer=fuzz.ratio,
    score_cutoff=threshold,
    limit=10,
    )

    if not fuzzy_matches:
        return {
            "skill_uri": None,
            "preferred_label": None,
            "mapping_method": "NO_MATCH",
            "similarity_score": 0,
            "ambiguous": False,
        }

    best_score = fuzzy_matches[0][1]

    # Check all candidates tied at the highest score.
    best_matches = [
        match
        for match in fuzzy_matches
        if match[1] == best_score
    ]

    best_items = [
        label_index[match[0]]
        for match in best_matches
    ]
    candidate_uris = set()

    for item in best_items:
        candidate_uris.update(item["candidate_uris"])

    # Reject uncertain or ambiguous fuzzy matches.
    if (
        len(candidate_uris) > 1
        or any(item["ambiguous"] for item in best_items)
    ):
        return {
            "skill_uri": None,
            "preferred_label": None,
            "mapping_method": "FUZZY_LABEL",
            "similarity_score": best_score,
            "ambiguous": True,
        }

    best_item = best_items[0]

    return {
        "skill_uri": best_item["skill_uri"],
        "preferred_label": best_item["preferred_label"],
        "mapping_method": "FUZZY_LABEL",
        "similarity_score": best_score,
        "ambiguous": False,
    }


# Requirements that should not be mapped automatically.
EXCLUDED_REQUIREMENTS = {
    "r": "SHORT_OR_AMBIGUOUS_TERM",
    "data analysis": "QUESTIONABLE_MATCH",
}


def generate_job_requirement_esco_proposals(job_id):
    """
    Generate pending ESCO mapping proposals for a confirmed job.

    Only recruiter-verified SKILL requirements are processed.
    Ambiguous, excluded and unmatched requirements are not saved.
    """

    conn = get_esco_connection()

    results = []

    try:
        # Step 1: Check whether the job exists and is confirmed.
        job = conn.execute("""
            SELECT requirements_confirmed
            FROM jobs
            WHERE job_id = ?
        """, (job_id,)).fetchone()

        if job is None:
            raise ValueError(f"Job ID {job_id} does not exist.")

        if not job["requirements_confirmed"]:
            return {
                "job_id": job_id,
                "status": "NOT_CONFIRMED",
                "inserted": 0,
                "results": [],
            }

        # Step 2: Retrieve verified skill requirements.
        requirements = conn.execute("""
            SELECT
                requirement_id,
                requirement_text
            FROM job_requirements
            WHERE job_id = ?
              AND category = 'SKILL'
              AND recruiter_verified = 1
        """, (job_id,)).fetchall()

        # Step 3: Build the ESCO label index.
        label_index = build_esco_requirement_label_index(conn)

        inserted_count = 0

        # Step 4: Match each requirement.
        for requirement in requirements:

            requirement_id = requirement["requirement_id"]
            requirement_text = requirement["requirement_text"]

            normalized = normalize_requirement_label(
                requirement_text
            )

            # Check excluded requirements first.
            if normalized in EXCLUDED_REQUIREMENTS:

                results.append({
                    "requirement_id": requirement_id,
                    "requirement_text": requirement_text,
                    "status": "EXCLUDED",
                    "reason": EXCLUDED_REQUIREMENTS[normalized],
                })

                continue

            # Match against ESCO.
            match = match_esco_requirement(
                requirement_text,
                label_index
            )

            # Reject ambiguous matches.
            if match["ambiguous"]:

                results.append({
                    "requirement_id": requirement_id,
                    "requirement_text": requirement_text,
                    "status": "AMBIGUOUS",
                    "reason": "MULTIPLE_POSSIBLE_MATCHES",
                })

                continue

            # Report requirements without an ESCO match.
            if not match["skill_uri"]:

                results.append({
                    "requirement_id": requirement_id,
                    "requirement_text": requirement_text,
                    "status": "NO_MATCH",
                    "reason": "NO_ESCO_CONCEPT_FOUND",
                })

                continue

            # Step 5: Save the mapping as a pending proposal.
            cursor = conn.execute("""
                INSERT INTO job_requirement_esco_mappings (
                    requirement_id,
                    skill_uri,
                    mapping_method,
                    mapping_score,
                    mapping_status,
                    reviewed
                )
                VALUES (?, ?, ?, ?, 'PENDING', 0)
                ON CONFLICT(requirement_id, skill_uri)
                DO NOTHING
            """, (
                requirement_id,
                match["skill_uri"],
                match["mapping_method"],
                match["similarity_score"],
            ))

            if cursor.rowcount == 1:
                inserted_count += 1
                proposal_status = "PROPOSED"
            else:
                proposal_status = "ALREADY_EXISTS"

            results.append({
                "requirement_id": requirement_id,
                "requirement_text": requirement_text,
                "preferred_label": match["preferred_label"],
                "skill_uri": match["skill_uri"],
                "mapping_method": match["mapping_method"],
                "similarity_score": match["similarity_score"],
                "status": proposal_status,
            })

        # Step 6: Commit all new proposals.
        conn.commit()

        return {
            "job_id": job_id,
            "status": "SUCCESS",
            "total_requirements": len(requirements),
            "inserted": inserted_count,
            "results": results,
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

