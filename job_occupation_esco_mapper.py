
from esco_db import get_esco_connection
from rapidfuzz import process, fuzz


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

FUZZY_MATCH_THRESHOLD = 85

# If two different occupations have fuzzy scores within this
# margin of the highest score, the result is treated as ambiguous.
FUZZY_AMBIGUITY_MARGIN = 3


# ---------------------------------------------------------
# 1. NORMALIZE OCCUPATION TITLES
# ---------------------------------------------------------

def normalize_occupation_title(title):
    """
    Normalize a job title or ESCO occupation label
    for consistent comparison.
    """
    return " ".join(str(title or "").casefold().split())


def extract_core_occupation_title(title):
    """
    Remove recognised seniority and employment-level
    modifiers from a job title for matching purposes only.

    The original job title is never modified.
    """

    normalized_title = normalize_occupation_title(title)

    modifiers = {
        "junior",
        "senior",
        "graduate",
        "trainee",
        "intern",
        "internship",
        "entry level",
        "entry-level",
        "associate",
    }

    words = normalized_title.split()

    # Remove modifiers from the beginning.
    while words:
        matched = None

        for modifier in sorted(modifiers, key=len, reverse=True):
            modifier_words = modifier.split()

            if words[:len(modifier_words)] == modifier_words:
                matched = modifier_words
                break

        if matched:
            words = words[len(matched):]
        else:
            break

    # Remove modifiers from the end.
    while words:
        matched = None

        for modifier in sorted(modifiers, key=len, reverse=True):
            modifier_words = modifier.split()

            if words[-len(modifier_words):] == modifier_words:
                matched = modifier_words
                break

        if matched:
            words = words[:-len(matched)]
        else:
            break

    return " ".join(words)

# ---------------------------------------------------------
# 2. BUILD ESCO OCCUPATION LABEL INDEX
# ---------------------------------------------------------

def build_esco_occupation_label_index(conn):
    """
    Build an index of English, released ESCO occupations.

    Preferred labels have priority over alternative labels,
    which have priority over hidden labels.

    Labels shared by multiple occupation URIs are marked
    as ambiguous.
    """

    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            occupation_uri,
            preferred_label,
            alt_labels,
            hidden_labels,
            code,
            isco_group
        FROM esco_occupations
        WHERE language = 'en'
          AND status = 'released'
    """)

    rows = cursor.fetchall()

    label_index = {}

    label_sources = [
        ("preferred_label", "EXACT_LABEL", 1),
        ("alt_labels", "ALT_LABEL", 2),
        ("hidden_labels", "HIDDEN_LABEL", 3),
    ]

    for row in rows:
        occupation_uri = row["occupation_uri"]
        preferred_label = row["preferred_label"]
        code = row["code"]
        isco_group = row["isco_group"]

        occupation_data = {
            "occupation_uri": occupation_uri,
            "preferred_label": preferred_label,
            "code": code,
            "isco_group": isco_group,
        }

        for column, mapping_method, priority in label_sources:
            raw_value = row[column]

            if not raw_value:
                continue

            if column == "preferred_label":
                labels = [raw_value]
            else:
                labels = str(raw_value).splitlines()

            for label in labels:
                normalized_label = normalize_occupation_title(label)

                if not normalized_label:
                    continue

                if normalized_label not in label_index:
                    label_index[normalized_label] = {
                        "candidate_occupations": {},
                        "ambiguous": False,
                    }

                entry = label_index[normalized_label]

                # Keep one record per occupation URI.
                existing = entry["candidate_occupations"].get(
                    occupation_uri
                )

                if existing is None or priority < existing["priority"]:
                    entry["candidate_occupations"][occupation_uri] = {
                        **occupation_data,
                        "mapping_method": mapping_method,
                        "priority": priority,
                    }

                # A label belonging to multiple occupation URIs
                # must never be selected automatically.
                if len(entry["candidate_occupations"]) > 1:
                    entry["ambiguous"] = True

    return label_index


# ---------------------------------------------------------
# 3. MATCH A JOB TITLE TO AN ESCO OCCUPATION
# ---------------------------------------------------------



def match_esco_occupation(
    job_title,
    label_index,
    threshold=FUZZY_MATCH_THRESHOLD
):
    """
    Match a job title against the ESCO occupation label index.

    Matching priority:
    1. Core-title exact match when a modifier exists.
    2. Original-title exact match when no modifier exists.
    3. Fuzzy matching using the appropriate title.

    Seniority modifiers are removed only for matching.
    The original job title is never modified.
    """

    normalized_title = normalize_occupation_title(job_title)
    core_title = extract_core_occupation_title(job_title)

    if not normalized_title:
        return {
            "status": "NO_MATCH",
            "reason": "EMPTY_JOB_TITLE",
            "occupation_uri": None,
        }

    if not label_index:
        return {
            "status": "NO_MATCH",
            "reason": "EMPTY_ESCO_LABEL_INDEX",
            "occupation_uri": None,
        }

    # -----------------------------------------------------
    # HELPER: RETURN AN EXACT MATCH
    # -----------------------------------------------------

    def exact_match(entry, reason):
        if entry["ambiguous"]:
            return {
                "status": "AMBIGUOUS",
                "reason": "EXACT_LABEL_SHARED_BY_MULTIPLE_OCCUPATIONS",
                "occupation_uri": None,
                "similarity_score": 100.0,
                "candidates": list(
                    entry["candidate_occupations"].values()
                ),
                "original_job_title": normalized_title,
                "core_title": core_title,
            }

        occupation = next(
            iter(entry["candidate_occupations"].values())
        )

        matched_label = (
            normalized_title
            if reason == "EXACT_MATCH"
            else core_title
        )

        return {
            "status": "MATCHED",
            "reason": reason,
            "occupation_uri": occupation["occupation_uri"],
            "preferred_label": occupation["preferred_label"],
            "code": occupation["code"],
            "isco_group": occupation["isco_group"],
            "mapping_method": occupation["mapping_method"],
            "similarity_score": 100.0,
            "matched_label": matched_label,
            "original_job_title": normalized_title,
            "core_title": core_title,
        }

    # -----------------------------------------------------
    # 1. SELECT THE APPROPRIATE TITLE FOR MATCHING
    # -----------------------------------------------------

    if core_title and core_title != normalized_title:
        search_title = core_title
        exact_reason = "CORE_TITLE_EXACT_MATCH"
    else:
        search_title = normalized_title
        exact_reason = "EXACT_MATCH"

    # -----------------------------------------------------
    # 2. EXACT MATCH
    # -----------------------------------------------------

    exact_entry = label_index.get(search_title)

    if exact_entry is not None:
        return exact_match(exact_entry, exact_reason)

    # -----------------------------------------------------
    # 3. FUZZY MATCH
    # -----------------------------------------------------

    fuzzy_matches = process.extract(
        search_title,
        label_index.keys(),
        scorer=fuzz.ratio,
        score_cutoff=threshold,
        limit=None,
    )

    if not fuzzy_matches:
        return {
            "status": "NO_MATCH",
            "reason": "NO_FUZZY_MATCH_ABOVE_THRESHOLD",
            "occupation_uri": None,
            "original_job_title": normalized_title,
            "core_title": core_title,
        }

    best_score = fuzzy_matches[0][1]

    close_matches = [
        match
        for match in fuzzy_matches
        if match[1] >= best_score - FUZZY_AMBIGUITY_MARGIN
    ]

    candidate_occupations = {}
    ambiguous_label_found = False

    for matched_label, score, _ in close_matches:

        entry = label_index[matched_label]

        if entry["ambiguous"]:
            ambiguous_label_found = True

        for uri, occupation in entry["candidate_occupations"].items():

            if (
                uri not in candidate_occupations
                or score > candidate_occupations[uri]["similarity_score"]
            ):
                candidate_occupations[uri] = {
                    **occupation,
                    "similarity_score": float(score),
                    "matched_label": matched_label,
                }

    # -----------------------------------------------------
    # 4. REJECT AMBIGUOUS FUZZY RESULTS
    # -----------------------------------------------------

    if ambiguous_label_found or len(candidate_occupations) > 1:
        return {
            "status": "AMBIGUOUS",
            "reason": "FUZZY_MATCH_HAS_COMPETING_CANDIDATES",
            "occupation_uri": None,
            "similarity_score": float(best_score),
            "candidates": list(candidate_occupations.values()),
            "original_job_title": normalized_title,
            "core_title": core_title,
        }

    if not candidate_occupations:
        return {
            "status": "NO_MATCH",
            "reason": "NO_UNAMBIGUOUS_FUZZY_CANDIDATE",
            "occupation_uri": None,
        }

    occupation = next(iter(candidate_occupations.values()))

    return {
        "status": "MATCHED",
        "reason": "FUZZY_MATCH",
        "occupation_uri": occupation["occupation_uri"],
        "preferred_label": occupation["preferred_label"],
        "code": occupation["code"],
        "isco_group": occupation["isco_group"],
        "mapping_method": "FUZZY_LABEL",
        "similarity_score": occupation["similarity_score"],
        "matched_label": occupation["matched_label"],
        "original_job_title": normalized_title,
        "core_title": core_title,
    }


# ---------------------------------------------------------
# 4. GENERATE JOB-TO-OCCUPATION ESCO PROPOSALS
# ---------------------------------------------------------

def generate_job_occupation_esco_proposals(job_id):
    """
    Generate a pending ESCO occupation proposal for a job.

    Only jobs with confirmed requirements are processed.
    The function does not automatically approve mappings.
    """

    conn = get_esco_connection()

    try:
        cursor = conn.cursor()

        # -------------------------------------------------
        # CHECK JOB
        # -------------------------------------------------

        cursor.execute("""
            SELECT
                job_id,
                job_title,
                seniority_level,
                requirements_confirmed
            FROM jobs
            WHERE job_id = ?
        """, (job_id,))

        job = cursor.fetchone()

        if job is None:
            raise ValueError(
                f"Job ID {job_id} does not exist."
            )

        job_title = job["job_title"]
        seniority_level = job["seniority_level"]

        # Follow the existing Part 5E confirmation gate.
        if not job["requirements_confirmed"]:
            return {
                "job_id": job_id,
                "job_title": job_title,
                "status": "NOT_CONFIRMED",
                "inserted": 0,
                "results": [],
            }

        # -------------------------------------------------
        # BUILD INDEX AND MATCH JOB TITLE
        # -------------------------------------------------

        label_index = build_esco_occupation_label_index(conn)

        match_result = match_esco_occupation(
            job_title,
            label_index,
        )

        result = {
            "job_id": job_id,
            "job_title": job_title,
            "seniority_level": seniority_level,
            **match_result,
        }

        # Do not insert unmatched or ambiguous results.
        if match_result["status"] != "MATCHED":
            conn.commit()

            return {
                "job_id": job_id,
                "job_title": job_title,
                "status": match_result["status"],
                "inserted": 0,
                "results": [result],
            }

        # -------------------------------------------------
        # INSERT PENDING PROPOSAL
        # -------------------------------------------------

        cursor.execute("""
            INSERT INTO job_esco_occupation_mappings (
                job_id,
                occupation_uri,
                mapping_method,
                mapping_score,
                mapping_status,
                reviewed
            )
            VALUES (?, ?, ?, ?, 'PENDING', 0)
            ON CONFLICT(job_id, occupation_uri) DO NOTHING
        """, (
            job_id,
            match_result["occupation_uri"],
            match_result["mapping_method"],
            match_result["similarity_score"],
        ))

        inserted = cursor.rowcount

        conn.commit()

        result["proposal_status"] = (
            "PROPOSED" if inserted == 1 else "ALREADY_EXISTS"
        )

        return {
            "job_id": job_id,
            "job_title": job_title,
            "status": "SUCCESS",
            "inserted": inserted,
            "results": [result],
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()
