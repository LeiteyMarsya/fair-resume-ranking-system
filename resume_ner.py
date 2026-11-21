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


from pathlib import Path
from spacy.util import compile_infix_regex

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "models" / "resume_ner" / "model-best"

MODEL_NAME = "resume_ner/model-best"
NER_VERSION = "resume-ner-0.4"

# Load the trained resume-specific NER model.
if not (MODEL_PATH / "config.cfg").is_file():
    raise FileNotFoundError(
        f"Trained resume NER model not found at: {MODEL_PATH}"
    )

nlp = spacy.load(MODEL_PATH)

# Split adjacent parentheses into separate tokens, for example:
# "Analysis(Advanced)" -> "Analysis", "(", "Advanced", ")"
infixes = list(nlp.Defaults.infixes)
infixes.extend([
    r"(?<=[^\s(])(?=\()",
    r"(?<=\()(?=[A-Za-z0-9])",
    r"(?<=\))(?=[A-Za-z0-9])",
])
nlp.tokenizer.infix_finditer = compile_infix_regex(infixes).finditer


# Section lines shorter than this are ignored (usually noise).
MIN_SECTION_LINE_LENGTH = 8

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
BULLET_PATTERN = re.compile(r"^[\s•●▪◦‣*\-]+\s*")


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
        "training",
        "training courses",
        "training and courses",
        "professional development",
        "training courses",
        "training and courses",
        "training courses and development",
    },
    "CERTIFICATION": {
        "certifications",
        "certificates",
        "professional certifications",
    },
    "SKILL": {
        "skills",
        "technical skills",
        "key skills",
        "core skills",
        "core competencies",
        "areas of expertise",
        "technical competencies",
        "professional skills",
        "technical expertise",
    },
}

# Reverse lookup: heading text -> section type (built once).
_HEADING_TO_SECTION = {
    heading: section
    for section, headings in SECTION_PATTERNS.items()
    for heading in headings
}

# Sections that should stop the previous extraction section.
# These sections are not currently used for entity extraction.
NON_ENTITY_SECTION_HEADINGS = {
    "languages",
    "language",
    "language proficiency",
    "language skills",
    "volunteering",
    "volunteer experience",
    "volunteering activities",
    "volunteering activities and extracurriculars",
    "extracurricular activities",
    "extracurriculars",
    "interests",
    "hobbies",
    "interests hobbies",
    "references",
    "personal details",
    "personal information",
    "contact",
    "contact details",
    "awards",
    "achievements",
    "awards achievements",
    "activities",
    "declaration",
    "other",
    "additional information",
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
    """
    Normalize resume section headings.

    Examples:
        Work Experience: -> work experience
        Interests & Hobbies -> interests hobbies
        Training / Courses -> training courses
    """

    cleaned = re.sub(r"[^a-zA-Z0-9 ]", " ", line)
    cleaned = re.sub(r"\s+", " ", cleaned)

    return cleaned.strip().lower()


def get_section_type(line: str) -> str | None:
    """Return a recognised extraction section type."""

    normalized = normalize_heading(line)

    return _HEADING_TO_SECTION.get(normalized)

def get_heading_details(line: str):
    """
    Detect standalone and inline section headings.

    Examples:
        SKILLS
        Technical Skills:
        Technical Skills: Python, SQL
        Languages: English, German

    Returns:
        (section_type, remaining_content)

    A section_type of None with remaining_content=None
    means the line is not a recognised heading.
    """

    cleaned = BULLET_PATTERN.sub("", line.strip()).strip()

    if not cleaned:
        return None, None

    normalized = normalize_heading(cleaned)

    # Standalone non-entity heading.
    if normalized in NON_ENTITY_SECTION_HEADINGS:
        return "NON_ENTITY", ""

    # Standalone entity heading.
    section_type = _HEADING_TO_SECTION.get(normalized)

    if section_type:
        return section_type, ""

    # Check for inline headings, such as:
    # Languages: English (Native)
    if ":" in cleaned:

        prefix, remaining = cleaned.split(":", 1)

        normalized_prefix = normalize_heading(prefix)

        if normalized_prefix in NON_ENTITY_SECTION_HEADINGS:
            return "NON_ENTITY", ""

        section_type = _HEADING_TO_SECTION.get(normalized_prefix)

        if section_type:
            return section_type, remaining.strip()

    return None, None


def is_noise_text(value: str) -> bool:
    """
    Reject obvious resume formatting noise and template text.
    """

    cleaned = value.strip()

    if not cleaned:
        return True

    # Normalise curly apostrophes.
    cleaned = cleaned.replace("\u2018", "'")
    cleaned = cleaned.replace("\u2019", "'")

    # Decorative separator lines.
    if re.fullmatch(
        r"[_=\-\u2013\u2014\s]{5,}",
        cleaned
    ):
        return True

    # Website and template footer text.
    noise_patterns = [
        r"^www\.enhancv\.com$",
        r"^powered\s+by$",
        r"don't\s+forget\s+to\s+use\s+resume",
        r"worded\s+to\s+scan\s+your\s+resume",
        r"before\s+you\s+send\s+it\s+off",
        r"proven\s+to\s+get\s+you\s+more\s+jobs",
    ]

    return any(
        re.search(
            pattern,
            cleaned,
            flags=re.IGNORECASE
        )
        for pattern in noise_patterns
    )

def extract_section_entities(text: str) -> list[Entity]:
    """
    Extract entities based on recognised resume sections.

    Improvements:
    - Recognises inline section headings.
    - Stops extraction at non-entity sections.
    - Rejects obvious decorative and template noise.
    - Splits individual skills while preserving ETL.
    - Preserves original character offsets.
    """

    entities = []

    current_section = None
    cursor = 0

    for raw_line in text.splitlines(keepends=True):

        line_start = cursor
        cursor += len(raw_line)

        line = raw_line.rstrip("\r\n")

        # Ignore obvious noise before extracting anything.
        if is_noise_text(line):
            continue

        # Detect standalone and inline headings.
        heading_type, heading_content = get_heading_details(line)

        if heading_type == "NON_ENTITY":
            current_section = None
            continue

        if heading_type:
            current_section = heading_type

            # Standalone heading: wait for the next line.
            if not heading_content:
                continue

            # Inline heading: extract the remaining content.
            display_text = heading_content

        else:

            if not current_section:
                continue

            display_text = line.strip()

            # Remove leading bullet characters.
            display_text = BULLET_PATTERN.sub(
                "",
                display_text
            ).strip()

        if not display_text:
            continue

        if is_noise_text(display_text):
            continue

        # Find the exact content position inside the original line.
        display_offset = line.find(display_text)

        if display_offset == -1:
            continue

        # --------------------------------------------------
        # SKILL SECTION
        # --------------------------------------------------

        if current_section == "SKILL":

            content_offset = 0

            # Remove introductory labels such as:
            # Programming Languages: Python, Java
            # Tools: Excel, Power BI
            colon_position = display_text.find(":")

            if colon_position != -1:

                prefix = display_text[:colon_position].strip()

                if len(prefix) <= 40:
                    content_offset = colon_position + 1

            content = display_text[content_offset:]

            # Keep compound ETL skills together.
            # Other commas and semicolons separate skills.
            skill_pattern = re.compile(
                r"[^,;]+(?:,\s*(?=(?:Transform|Load)\b)[^,;]+)*",
                flags=re.IGNORECASE,
            )

            # Only remove proficiency annotations.
            proficiency_pattern = re.compile(
                r"\s*\((?:basic|beginner|intermediate|int\.?|"
                r"proficient|experienced|advanced|expert)\)",
                flags=re.IGNORECASE,
            )

            for match in skill_pattern.finditer(content):

                raw_item = match.group(0)

                skill_text = proficiency_pattern.sub(
                    "",
                    raw_item
                ).strip()

                if not skill_text:
                    continue

                if is_noise_text(skill_text):
                    continue

                if (
                    len(skill_text) < 2
                    and skill_text.upper() not in {"R", "C"}
                ):
                    continue

                local_search_start = (
                    display_offset
                    + content_offset
                    + match.start()
                )

                text_offset = line.find(
                    skill_text,
                    local_search_start
                )

                if text_offset == -1:
                    continue

                start = line_start + text_offset
                end = start + len(skill_text)

                entities.append(
                    _make_entity(
                        skill_text,
                        "SKILL",
                        start,
                        end,
                        confidence=None,
                        source="SECTION_BASED_EXTRACTION",
                    )
                )

        # --------------------------------------------------
        # OTHER ENTITY SECTIONS
        # --------------------------------------------------

        else:

            if len(display_text) < MIN_SECTION_LINE_LENGTH:
                continue

            # Skip course provider and date information.
            if current_section == "COURSE":
                provider_patterns = [
                    r"^certification obtained from\b",
                    r"^(coursera|udemy|edx|linkedin learning)\s*,?\s*\d{4}\.?$",
                ]

                if any(
                    re.search(pattern, display_text, re.IGNORECASE)
                    for pattern in provider_patterns
                ):
                    continue

            text_offset = line.find(display_text)

            if text_offset == -1:
                continue

            start = line_start + text_offset
            end = start + len(display_text)

            entity_label = current_section

            # Some resumes list awards and certifications
            # inside the Education section.
            if current_section == "EDUCATION":
                if re.search(
                    r"\b(certified|certification|certificate|"
                    r"award|fellow|dean'?s list)\b",
                    display_text,
                    re.IGNORECASE,
                ):
                    entity_label = "CERTIFICATION"

            entities.append(
                _make_entity(
                    display_text,
                    entity_label,
                    start,
                    end,
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

    Rules:
    1. Longer entity spans have priority.
    2. For identical spans, more specific labels have priority.
    3. Source priority resolves remaining ties.
    """

    label_priority = {
        "EMAIL": 1,
        "PHONE": 1,
        "EXPERIENCE_DURATION": 2,
        "CERTIFICATION": 3,
        "EDUCATION": 3,
        "SKILL": 3,
        "PROJECT": 4,
        "COURSE": 4,
        "JOB_TITLE": 4,
        "ORGANIZATION": 4,
        "EXPERIENCE": 5,
    }

    source_priority = {
        "REGEX": 1,
        "SPACY_NER": 2,
        "SECTION_BASED_EXTRACTION": 3,
    }

    by_priority = sorted(
        entities,
        key=lambda e: (
            -(e["end"] - e["start"]),
            e["start"],
            label_priority.get(e["label"], 99),
            source_priority.get(e["source"], 99),
        ),
    )

    accepted = []

    for entity in by_priority:
        overlaps = any(
            entity["start"] < kept["end"]
            and entity["end"] > kept["start"]
            for kept in accepted
        )

        if not overlaps:
            accepted.append(entity)

    return sorted(
        accepted,
        key=lambda e: (e["start"], e["end"]),
    )

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

    entities = [
    entity
    for entity in entities
    if not is_noise_text(entity["text"])
]

    entities = sort_entities(entities)

    return {
        "entities": entities,
        "summary": dict(Counter(e["label"] for e in entities)),
        "model": MODEL_NAME,
        "version": NER_VERSION,
    }