"""
Storage and helper functions for reviewing annotation suggestions.

How the review workflow uses the two files:
    bootstrap_candidates.jsonl   Automatic suggestions (read only here).
    reviewed_annotations.jsonl   Human review work (saved here).

Each resume record keeps two lists:
    entities          The original automatic suggestions (never changed).
    review_entities   The reviewer's decisions (accepted, edited, added).

A .jsonl file holds one JSON record per line.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# One resume record, and one (start, end) character range in its text.
Record = dict[str, Any]
Span = tuple[int, int]

BASE_DIR = Path(__file__).resolve().parent
ANNOTATION_DIR = BASE_DIR / "data" / "annotations"

BOOTSTRAP_PATH = ANNOTATION_DIR / "bootstrap_candidates.jsonl"
REVIEWED_PATH = ANNOTATION_DIR / "reviewed_annotations.jsonl"

# Labels allowed in the training dataset. Personal identity labels
# (name, email, phone) are left out on purpose: they are not needed
# for job-relevance ranking.
ALLOWED_LABELS = [
    "SKILL",
    "EDUCATION",
    "COURSE",
    "PROJECT",
    "EXPERIENCE",
    "EXPERIENCE_DURATION",
    "CERTIFICATION",
    "JOB_TITLE",
    "ORGANIZATION",
]


# Reading and writing JSONL files

def read_jsonl(path: Path) -> list[Record]:
    """
    Read a JSON Lines file.

    Returns an empty list if the file does not exist.
    Raises ValueError if a line is not valid JSON or not a JSON object.
    """
    if not path.exists():
        return []

    records = []

    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()
            if not line:  # skip blank lines
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSON on line {line_number} "
                    f"of {path.name}: {error}"
                ) from error

            if not isinstance(record, dict):
                raise ValueError(
                    f"Line {line_number} of {path.name} "
                    "must contain a JSON object."
                )

            records.append(record)

    return records


def write_jsonl(path: Path, records: list[Record]) -> None:
    """
    Write records to a JSONL file.

    The data goes to a temporary file first and is then moved into place,
    so an interrupted write is unlikely to leave a half-written dataset.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = path.with_name(path.name + ".tmp")

    with temporary_path.open("w", encoding="utf-8", newline="\n") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")

    temporary_path.replace(path)


# Loading the review workspace

def _new_review_record(source_record: Record) -> Record:
    """Turn a bootstrap record into a fresh record ready for review."""
    record = dict(source_record)

    # Every suggestion starts as accepted. The reviewer rejects or edits
    # the wrong ones.
    record["review_entities"] = [
        {
            **entity,
            "review_id": f"bootstrap_{index}",
            "accepted": True,
            "origin": "BOOTSTRAP",
        }
        for index, entity in enumerate(source_record.get("entities", []))
    ]
    record["review_status"] = "PENDING"

    return record


def load_review_workspace() -> list[Record]:
    """
    Combine bootstrap suggestions with any saved review work.

    - Resumes already reviewed: use the saved review record.
    - Resumes not reviewed yet: start a new review record.
    - Reviewed resumes missing from the bootstrap file (for example after
      it was regenerated) are still kept at the end.

    Raises FileNotFoundError if the bootstrap file does not exist.
    """
    if not BOOTSTRAP_PATH.exists():
        raise FileNotFoundError(
            "Bootstrap dataset was not found. Run bootstrap.py first."
        )

    # Saved work, looked up by resume ID.
    reviewed_by_id = {
        str(record["resume_id"]): record
        for record in read_jsonl(REVIEWED_PATH)
        if "resume_id" in record
    }

    workspace = []

    for source_record in read_jsonl(BOOTSTRAP_PATH):
        resume_key = str(source_record["resume_id"])

        if resume_key in reviewed_by_id:
            # pop() so the leftovers can be added below.
            workspace.append(reviewed_by_id.pop(resume_key))
        else:
            workspace.append(_new_review_record(source_record))

    workspace.extend(reviewed_by_id.values())

    return workspace


# Finding text in a resume

def find_occurrences(text: str, phrase: str) -> list[Span]:
    """
    Find every case-insensitive occurrence of a phrase.

    Returns (start, end) character ranges in the original text.
    """
    if not phrase or not phrase.strip():
        return []

    pattern = re.compile(re.escape(phrase), flags=re.IGNORECASE)

    return [match.span() for match in pattern.finditer(text)]


def find_nth_occurrence(
    text: str,
    phrase: str,
    occurrence_number: int,
) -> Span | None:
    """
    Find one occurrence of a phrase, counting from 1.

    Example: occurrence_number=1 is the first match.
    Returns None if there is no such occurrence.
    """
    if occurrence_number < 1:
        return None

    occurrences = find_occurrences(text, phrase)
    index = occurrence_number - 1

    return occurrences[index] if index < len(occurrences) else None


def locate_edited_entity(
    original_text: str,
    edited_phrase: str,
    previous_start: int,
) -> tuple[int, int, str] | None:
    """
    Find where a reviewer's corrected entity text appears in the resume.

    If the phrase appears more than once, the match closest to the
    entity's previous position is used.

    Returns (start, end, text_from_resume), or None if the phrase is
    empty or not found. The returned text is copied from the resume, so
    it has the resume's exact capitalization.
    """
    edited_phrase = edited_phrase.strip()
    if not edited_phrase:
        return None

    matches = find_occurrences(original_text, edited_phrase)
    if not matches:
        return None

    start, end = min(matches, key=lambda span: abs(span[0] - previous_start))

    return start, end, original_text[start:end]


# Checking for problems

def find_overlaps(entities: list[Record]) -> list[tuple[Record, Record]]:
    """
    Find pairs of accepted entities whose text ranges overlap.

    Standard spaCy NER training cannot handle overlapping spans, so the
    reviewer must fix these before training. Exact duplicates (same range
    and same label) are not reported.
    """
    accepted = sorted(
        (entity for entity in entities if entity.get("accepted", False)),
        key=lambda entity: (entity["start"], entity["end"]),
    )

    overlaps = []

    for index, current in enumerate(accepted):
        for previous in accepted[:index]:
            overlapping = (
                current["start"] < previous["end"]
                and current["end"] > previous["start"]
            )
            if not overlapping:
                continue

            is_duplicate = (
                current["start"] == previous["start"]
                and current["end"] == previous["end"]
                and current["label"] == previous["label"]
            )
            if not is_duplicate:
                overlaps.append((previous, current))

    return overlaps


# Saving

def _resume_key(record: Record) -> str:
    """Resume ID as a string (IDs may be stored as int or str)."""
    return str(record.get("resume_id", ""))


def save_reviewed_record(record: Record) -> None:
    """
    Save one reviewed resume without touching the others.

    Replaces the saved record with the same resume ID, or adds it if new.
    """
    key = _resume_key(record)
    existing_records = read_jsonl(REVIEWED_PATH)

    updated_records = [
        record if _resume_key(existing) == key else existing
        for existing in existing_records
    ]

    if not any(_resume_key(existing) == key for existing in existing_records):
        updated_records.append(record)

    # Keep the file in a consistent order for easier inspection.
    updated_records.sort(key=_resume_key)

    write_jsonl(REVIEWED_PATH, updated_records)