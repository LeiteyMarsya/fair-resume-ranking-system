"""
Resume entity extraction.

Combines three sources of entities:
    1. spaCy's statistical NER (names, organisations, dates, ...)
    2. An EntityRuler for resume-specific terms (skills, certifications, education)
    3. Regex and section heuristics (email, phone, experience, resume sections)

Overlapping results are resolved so each piece of text is labelled only once.

Main entry point:
    extract_resume_entities(text) -> {"entities": [...], "summary": {...}, ...}
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

import spacy

from job_analyzer import COMMON_SKILLS

# One extracted entity: text, label, start, end, confidence, source.
Entity = dict[str, Any]

MODEL_NAME = "en_core_web_sm"
NER_VERSION = "resume-ner-0.1"

# Section lines shorter than this are ignored (usually noise).
MIN_SECTION_LINE_LENGTH = 8


# Load the spaCy model

try:
    nlp = spacy.load(MODEL_NAME)
except OSError as error:
    raise RuntimeError(
        "The spaCy English model is not installed.\n\n"
        "Run this command in your terminal:\n"
        "python -m spacy download en_core_web_sm"
    ) from error


# Custom terms for the EntityRuler

CERTIFICATION_TERMS = (
    "CCNA",
    "PMP",
    "CompTIA",
    "AWS Certified",
    "Microsoft Certified",
    "Azure Certification",
    "Certified Ethical Hacker",
    "CEH",
    "CISSP",
    "Cisco Certified",
)

EDUCATION_PHRASES = (
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
    "Doctor of Philosophy",
    "PhD",
    "Diploma in Information Technology",
    "Diploma in Computer Science",
    "Diploma in Information Systems",
    "Diploma",
)


def _make_patterns(label: str, terms) -> list[dict[str, str]]:
    """Convert a list of terms into EntityRuler patterns with one label."""
    return [{"label": label, "pattern": term} for term in terms]


# The ruler runs before spaCy's NER so our resume-specific terms take priority.
if "entity_ruler" in nlp.pipe_names:
    ruler = nlp.get_pipe("entity_ruler")
else:
    ruler = nlp.add_pipe(
        "entity_ruler",
        before="ner",
        config={"phrase_matcher_attr": "LOWER"},  # case-insensitive matching
    )

ruler.add_patterns(
    # Skip one-letter skills (e.g. "r"), they cause too many false positives.
    _make_patterns("SKILL", [s for s in COMMON_SKILLS if len(s.strip()) >= 2])
    + _make_patterns("CERTIFICATION", CERTIFICATION_TERMS)
    + _make_patterns("EDUCATION", EDUCATION_PHRASES)
)


# Regex patterns

EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

# Malaysian phone numbers, e.g. "+60 12-345 6789" or "012 345 6789".
PHONE_PATTERN = re.compile(
    r"(?<!\w)(?:\+?60|0)[\s-]?\d{2,3}[\s-]?\d{3,4}[\s-]?\d{3,4}(?!\w)"
)

# Durations such as "3 years of relevant experience".
EXPERIENCE_PATTERN = re.compile(
    r"\b(\d+(?:\.\d+)?)\+?\s+years?(?:\s+of)?(?:\s+relevant)?\s+experience\b",
    flags=re.IGNORECASE,
)

# (label, pattern) pairs handled by extract_regex_entities.
REGEX_ENTITY_PATTERNS = (
    ("EMAIL", EMAIL_PATTERN),
    ("PHONE", PHONE_PATTERN),
    ("EXPERIENCE_DURATION", EXPERIENCE_PATTERN),
)

# Bullet characters at the start of a line.
BULLET_PATTERN = re.compile(r"^[•●▪◦*\-]+\s*")


# Resume section headings

SECTION_PATTERNS = {
    "EDUCATION": {
        "education",
        "academic background",
        "academic qualification",
        "qualifications",
    },
    "EXPERIENCE": {
        "experience",
        "work experience",
        "professional experience",
        "employment history",
        "work history",
        "internship",
    },
    "PROJECT": {
        "projects",
        "academic projects",
        "university projects",
        "relevant projects",
        "personal projects",
    },
    "COURSE": {
        "courses",
        "relevant coursework",
        "coursework",
        "relevant courses",
    },
    "CERTIFICATION": {
        "certifications",
        "certificates",
        "professional certifications",
    },
}

# Reverse lookup: heading text -> section type (built once).
_HEADING_TO_SECTION = {
    heading: section
    for section, headings in SECTION_PATTERNS.items()
    for heading in headings
}


def _make_entity(
    text: str,
    label: str,
    start: int,
    end: int,
    confidence: float | None,
    source: str,
) -> Entity:
    """Build an entity dictionary with a consistent format."""
    return {
        "text": text,
        "label": label,
        "start": start,
        "end": end,
        "confidence": confidence,
        "source": source,
    }


def normalize_heading(line: str) -> str:
    """Lowercase a line and strip punctuation, e.g. 'Work Experience:' -> 'work experience'."""
    cleaned = re.sub(r"[^a-zA-Z0-9 ]", "", line)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip().lower()


def get_section_type(line: str) -> str | None:
    """Return the section type if the line is a known heading, else None."""
    return _HEADING_TO_SECTION.get(normalize_heading(line))


def extract_section_entities(text: str) -> list[Entity]:
    """
    Label each meaningful line with the resume section it appears in.

    Temporary baseline: a trained NER model will later replace this
    heuristic with learned entity detection.
    """
    entities = []
    current_section = None
    cursor = 0  # character offset of the current line in `text`

    # keepends=True keeps "\n" / "\r\n" so the offsets stay exact.
    for raw_line in text.splitlines(keepends=True):
        line_start = cursor
        cursor += len(raw_line)
        line = raw_line.rstrip("\r\n")

        # A heading starts a new section.
        heading_type = get_section_type(line)
        if heading_type:
            current_section = heading_type
            continue

        cleaned_line = line.strip()
        if not current_section or len(cleaned_line) < MIN_SECTION_LINE_LENGTH:
            continue

        display_text = BULLET_PATTERN.sub("", cleaned_line).strip()
        if display_text:
            entities.append(
                _make_entity(
                    display_text,
                    current_section,
                    line_start,
                    line_start + len(line),
                    confidence=None,
                    source="SECTION_BASED_EXTRACTION",
                )
            )

    return entities


def extract_regex_entities(text: str) -> list[Entity]:
    """Find emails, phone numbers and experience durations with regex."""
    return [
        _make_entity(match.group(0), label, match.start(), match.end(), 1.0, "REGEX")
        for label, pattern in REGEX_ENTITY_PATTERNS
        for match in pattern.finditer(text)
    ]


def sort_entities(entities: list[Entity]) -> list[Entity]:
    """
    Remove overlapping entities and return the rest in reading order.

    When two entities overlap, the longer span wins. On a tie, the one
    that appears first wins.
    """
    # Consider the longest spans first.
    by_priority = sorted(
        entities,
        key=lambda e: (-(e["end"] - e["start"]), e["start"], e["label"]),
    )

    accepted: list[Entity] = []

    for entity in by_priority:
        overlaps = any(
            entity["start"] < kept["end"] and entity["end"] > kept["start"]
            for kept in accepted
        )
        if not overlaps:
            accepted.append(entity)

    return sorted(accepted, key=lambda e: (e["start"], e["end"]))


def extract_resume_entities(text: str) -> dict[str, Any]:
    """
    Run the complete resume NER pipeline.

    Returns:
        {
            "entities": [...],
            "summary":  {label: count},
            "model":    spaCy model name,
            "version":  NER version,
        }
    """
    doc = nlp(text)

    # spaCy's Doc.ents does not expose a per-entity confidence score.
    entities = [
        _make_entity(ent.text, ent.label_, ent.start_char, ent.end_char, None, "SPACY_NER")
        for ent in doc.ents
    ]
    entities += extract_regex_entities(text)
    entities += extract_section_entities(text)

    entities = sort_entities(entities)

    return {
        "entities": entities,
        "summary": dict(Counter(e["label"] for e in entities)),
        "model": MODEL_NAME,
        "version": NER_VERSION,
    }