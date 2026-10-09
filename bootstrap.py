"""
Bootstrap annotation suggestions for resume NER training.

What this script does:
    1. Reads stored resumes from the database.
    2. Uses simple rules (dictionaries + regex) to suggest entities:
       SKILL, EDUCATION, CERTIFICATION and EXPERIENCE_DURATION.
    3. Writes one JSON record per resume to a .jsonl file.

The output is a starting point for human review. These are automatic
suggestions, NOT verified training labels.

Run it with:  python bootstrap_annotations.py
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from db import get_all_resumes
from job_analyzer import COMMON_SKILLS

# One suggested entity: start, end, text, label, source, rule_strength.
Candidate = dict[str, Any]

BASE_DIR = Path(__file__).resolve().parent
ANNOTATION_DIR = BASE_DIR / "data" / "annotations"
OUTPUT_PATH = ANNOTATION_DIR / "bootstrap_candidates.jsonl"

BOOTSTRAP_VERSION = "bootstrap-0.1"

# Resumes shorter than this (in characters) are skipped.
MIN_RESUME_LENGTH = 50

# How strongly we trust each rule. These are NOT calibrated probabilities.
RULE_STRENGTH = {
    "SKILL": 0.80,
    "EDUCATION": 0.80,
    "CERTIFICATION": 0.80,
    "EXPERIENCE_DURATION": 0.90,
}

# When two suggestions overlap, the higher priority label is kept.
LABEL_PRIORITY = {
    "EDUCATION": 100,
    "CERTIFICATION": 95,
    "EXPERIENCE_DURATION": 90,
    "SKILL": 80,
}

# Skills that often mean something else ("R" the letter, "node" the word),
# so we don't label them automatically.
AMBIGUOUS_SKILLS = {"r", "node"}


# Rules

EDUCATION_PHRASES = [
    "Bachelor of Computer Science",
    "Bachelor of Information Technology",
    "Bachelor of Information Systems",
    "Bachelor of Software Engineering",
    "Bachelor of Data Science",
    "Bachelor of Business",
    "Bachelor's Degree",
    "Bachelor Degree",
    "Master of Computer Science",
    "Master of Information Technology",
    "Master of Information Systems",
    "Master's Degree",
    "Master Degree",
    "Diploma in Information Technology",
    "Diploma in Computer Science",
    "Diploma in Information Systems",
]

# Catches degree names missing from the list above, e.g.
# "Bachelor of Science in Electrical Engineering".
# This is a heuristic and may over- or under-match.
DEGREE_PATTERN = re.compile(
    r"\b(?:"
    r"bachelor(?:'s)?|"
    r"master(?:'s)?|"
    r"associate(?:'s)?|"
    r"diploma"
    r")"
    r"(?:\s+(?:degree|of|in))"
    r"(?:\s+(?:"
    r"science|arts|engineering|technology|computer|"
    r"information|business|data|software|systems|"
    r"management|accounting|finance|mathematics|"
    r"honours|honors|analytics|analysis|commerce|"
    r"economics|cybersecurity|networking|statistics|"
    r"computing|electrical|mechanical|and"
    r")){0,7}\b",
    flags=re.IGNORECASE,
)

CERTIFICATION_TERMS = [
    "CompTIA Security+",
    "CompTIA Network+",
    "Certified Ethical Hacker",
    "Google Data Analytics Professional Certificate",
    "Microsoft Certified",
    "AWS Certified",
    "Cisco Certified",
    "CCNA",
    "CISSP",
    "CISA",
    "CISM",
    "CEH",
    "PMP",
    "ITIL",
]

# Durations such as "3 years of relevant experience".
EXPERIENCE_PATTERN = re.compile(
    r"\b\d+(?:\.\d+)?\+?\s+years?"
    r"(?:\s+of)?"
    r"(?:\s+(?:relevant|professional|related))?"
    r"\s+experience\b",
    flags=re.IGNORECASE,
)

# Resume section headings and the section type each one starts.
# These are hints for annotators, not NER labels.
# "OTHER" marks sections we don't track; they just end the previous section.
SECTION_HEADINGS = {
    "education": "EDUCATION",
    "academic background": "EDUCATION",
    "academic qualifications": "EDUCATION",
    "work experience": "EXPERIENCE",
    "professional experience": "EXPERIENCE",
    "employment history": "EXPERIENCE",
    "experience": "EXPERIENCE",
    "internship": "EXPERIENCE",
    "projects": "PROJECT",
    "academic projects": "PROJECT",
    "university projects": "PROJECT",
    "personal projects": "PROJECT",
    "relevant projects": "PROJECT",
    "courses": "COURSE",
    "coursework": "COURSE",
    "relevant coursework": "COURSE",
    "certifications": "CERTIFICATION",
    "certificates": "CERTIFICATION",
    "professional certifications": "CERTIFICATION",
    "skills": "OTHER",
    "technical skills": "OTHER",
    "summary": "OTHER",
    "professional summary": "OTHER",
    "profile": "OTHER",
    "career objective": "OTHER",
    "objective": "OTHER",
    "languages": "OTHER",
    "achievements": "OTHER",
    "publications": "OTHER",
    "volunteer experience": "OTHER",
    "interests": "OTHER",
    "references": "OTHER",
    "contact": "OTHER",
    "contact information": "OTHER",
    "additional information": "OTHER",
}

# Only lines inside these sections are saved as hints.
HINT_SECTIONS = {"PROJECT", "COURSE", "EXPERIENCE"}


# Text helpers

def make_phrase_pattern(phrase: str) -> re.Pattern:
    """
    Build a case-insensitive pattern that matches a whole phrase.

    Words may be separated by any amount of whitespace, and the match
    offsets still point to the original text.
    """
    words = r"\s+".join(re.escape(word) for word in phrase.split())
    return re.compile(r"(?<!\w)" + words + r"(?!\w)", flags=re.IGNORECASE)


def normalize_heading(line: str) -> str:
    """Simplify a line so headings match: '2. Projects:' -> 'projects'."""
    value = line.strip().lower()
    value = re.sub(r"^\d+\s*[.)-]?\s*", "", value)    # leading number
    value = re.sub(r"[:\-–—]+$", "", value)           # trailing punctuation
    value = re.sub(r"[^a-z0-9 &/+-]", "", value)      # other symbols
    return re.sub(r"\s+", " ", value).strip()


# Pre-built patterns (compiled once, reused for every resume)
_SKILL_PATTERNS = [
    make_phrase_pattern(skill)
    for skill in dict.fromkeys(COMMON_SKILLS)  # removes duplicates, keeps order
    if len(skill.strip()) >= 2 and skill.strip().lower() not in AMBIGUOUS_SKILLS
]
_EDUCATION_PATTERNS = [make_phrase_pattern(p) for p in EDUCATION_PHRASES]
_CERTIFICATION_PATTERNS = [make_phrase_pattern(p) for p in CERTIFICATION_TERMS]


# Section hints

def extract_section_hints(text: str) -> list[dict[str, Any]]:
    """
    Collect the lines inside project, course and experience sections.

    These help annotators find the right text later. They are not
    accepted automatically as NER training labels.
    """
    hints = []
    current_section: str | None = None
    offset = 0  # position of the current line in `text`

    # keepends=True keeps the line breaks so offsets stay exact.
    for raw_line in text.splitlines(keepends=True):
        line = raw_line.rstrip("\r\n")
        line_start = offset
        offset += len(raw_line)

        heading_type = SECTION_HEADINGS.get(normalize_heading(line))

        # A recognized heading starts a new section ("OTHER" = untracked).
        if heading_type is not None:
            current_section = None if heading_type == "OTHER" else heading_type
            continue

        if current_section in HINT_SECTIONS and line.strip():
            hints.append(
                {
                    "section": current_section,
                    "start": line_start,
                    "end": line_start + len(line),
                    "text": line.strip(),
                }
            )

    return hints


# Entity suggestions

def pattern_candidates(
    text: str,
    pattern: re.Pattern,
    label: str,
    source: str,
) -> list[Candidate]:
    """Return one suggestion for every place the pattern matches."""
    return [
        {
            "start": match.start(),
            "end": match.end(),
            "text": match.group(0),
            "label": label,
            "source": source,
            "rule_strength": RULE_STRENGTH[label],
        }
        for match in pattern.finditer(text)
        if match.end() > match.start()  # ignore empty matches
    ]


def find_skill_candidates(text: str) -> list[Candidate]:
    """Suggest skills from the skill dictionary."""
    return [
        candidate
        for pattern in _SKILL_PATTERNS
        for candidate in pattern_candidates(text, pattern, "SKILL", "SKILL_DICTIONARY")
    ]


def find_education_candidates(text: str) -> list[Candidate]:
    """Suggest education terms from the phrase list and the degree regex."""
    from_phrases = [
        candidate
        for pattern in _EDUCATION_PATTERNS
        for candidate in pattern_candidates(
            text, pattern, "EDUCATION", "EDUCATION_DICTIONARY"
        )
    ]
    from_regex = pattern_candidates(text, DEGREE_PATTERN, "EDUCATION", "EDUCATION_PATTERN")

    return from_phrases + from_regex


def find_certification_candidates(text: str) -> list[Candidate]:
    """Suggest certifications from the certification list."""
    return [
        candidate
        for pattern in _CERTIFICATION_PATTERNS
        for candidate in pattern_candidates(
            text, pattern, "CERTIFICATION", "CERTIFICATION_DICTIONARY"
        )
    ]


def find_experience_candidates(text: str) -> list[Candidate]:
    """Suggest years-of-experience phrases."""
    return pattern_candidates(
        text, EXPERIENCE_PATTERN, "EXPERIENCE_DURATION", "EXPERIENCE_REGEX"
    )


def resolve_overlaps(candidates: list[Candidate]) -> list[Candidate]:
    """
    Make sure no two suggestions cover the same text.

    NER training data needs non-overlapping spans. When suggestions
    overlap, we keep the higher-priority label, then the longer span.
    Human review should catch anything dropped by mistake.
    """
    # Remove exact duplicates (same span and same label).
    unique: dict[tuple[int, int, str], Candidate] = {}
    for candidate in candidates:
        key = (candidate["start"], candidate["end"], candidate["label"])
        unique.setdefault(key, candidate)

    # Best candidates first.
    by_priority = sorted(
        unique.values(),
        key=lambda c: (
            -LABEL_PRIORITY.get(c["label"], 0),
            -(c["end"] - c["start"]),
            c["start"],
        ),
    )

    # Keep a candidate only if it doesn't overlap one we already kept.
    accepted: list[Candidate] = []
    for candidate in by_priority:
        overlaps = any(
            candidate["start"] < kept["end"] and candidate["end"] > kept["start"]
            for kept in accepted
        )
        if not overlaps:
            accepted.append(candidate)

    return sorted(accepted, key=lambda c: (c["start"], c["end"]))


# Building the dataset

def bootstrap_one_resume(resume: Any) -> dict[str, Any] | None:
    """
    Create the weak-label record for one stored resume.

    Returns None if the resume text is empty or too short.
    """
    text = (resume["extracted_text"] or "").strip()

    if len(text) < MIN_RESUME_LENGTH:
        return None

    candidates = [
        *find_skill_candidates(text),
        *find_education_candidates(text),
        *find_certification_candidates(text),
        *find_experience_candidates(text),
    ]

    # Safety check: every span must match the text at its offsets.
    entities = [
        entity
        for entity in resolve_overlaps(candidates)
        if text[entity["start"]:entity["end"]] == entity["text"]
    ]

    return {
        "resume_id": resume["resume_id"],
        "blind_id": resume["blind_id"],
        "text": text,
        "entities": entities,
        "section_hints": extract_section_hints(text),
        "labeling_method": "BOOTSTRAP_RULES",
        "bootstrap_version": BOOTSTRAP_VERSION,
        "review_status": "PENDING",  # a human still needs to review it
    }


def generate_bootstrap_dataset() -> dict[str, Any]:
    """
    Read all stored resumes and write the JSONL dataset.

    Any existing output file is replaced.
    Returns a report with counts for display.
    """
    ANNOTATION_DIR.mkdir(parents=True, exist_ok=True)

    resumes = get_all_resumes()

    included = 0
    skipped_short = 0
    without_suggestions = 0
    entity_counts: Counter[str] = Counter()

    with OUTPUT_PATH.open("w", encoding="utf-8", newline="\n") as output_file:
        for resume in resumes:
            record = bootstrap_one_resume(resume)

            if record is None:
                skipped_short += 1
                continue

            included += 1

            if not record["entities"]:
                without_suggestions += 1

            entity_counts.update(e["label"] for e in record["entities"])

            # One JSON object per line.
            output_file.write(json.dumps(record, ensure_ascii=False) + "\n")

    return {
        "total_resumes_in_database": len(resumes),
        "resumes_in_dataset": included,
        "skipped_empty_or_short": skipped_short,
        "resumes_without_suggestions": without_suggestions,
        "total_suggested_entities": sum(entity_counts.values()),
        "entities_by_label": dict(entity_counts),
        "output_path": str(OUTPUT_PATH),
    }


# Command-line entry point

def print_report(report: dict[str, Any]) -> None:
    """Print the bootstrap report in a readable format."""
    print("\nBOOTSTRAP COMPLETED")
    print("=" * 50)
    print("Resumes in database:", report["total_resumes_in_database"])
    print("Resumes in dataset:", report["resumes_in_dataset"])
    print("Skipped empty/short resumes:", report["skipped_empty_or_short"])
    print("Resumes without suggestions:", report["resumes_without_suggestions"])
    print("Suggested entities:", report["total_suggested_entities"])

    print("\nEntities by label:")
    for label, count in sorted(report["entities_by_label"].items()):
        print(f"  {label}: {count}")

    print("\nOutput file:")
    print(report["output_path"])
    print("\nNote: These are automatic suggestions, not verified training labels.")


if __name__ == "__main__":
    print_report(generate_bootstrap_dataset())