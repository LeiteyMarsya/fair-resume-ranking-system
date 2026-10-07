"""
job_analyzer.py
===============

Rule-based extraction of requirements from a job description.

The analyzer looks for four kinds of requirements:
    SKILL, EDUCATION, CERTIFICATION, EXPERIENCE

and for each one guesses whether it is REQUIRED, PREFERRED or UNSPECIFIED
by looking at the words around it.

IMPORTANT: everything here is a *prediction*. A recruiter must review and
confirm the results before they are used to score any candidate.

Main entry point:
    analyze_job_description(text) -> {"requirements": [...], "summary": {...}}
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Iterable

# One extracted requirement. Keys match what database.create_job_requirement
# expects (EXPERIENCE items also carry an extra "years" value).
Requirement = dict[str, Any]


# ============================================================
# CONSTANTS
# ============================================================

# Requirement types
REQUIRED = "REQUIRED"
PREFERRED = "PREFERRED"
UNSPECIFIED = "UNSPECIFIED"

# Requirement categories
SKILL = "SKILL"
EDUCATION = "EDUCATION"
CERTIFICATION = "CERTIFICATION"
EXPERIENCE = "EXPERIENCE"

# How many characters on each side of a match we read to decide
# whether it is required or preferred.
CONTEXT_WINDOW = 150


# ============================================================
# KNOWLEDGE BASE
# ============================================================
# This is only a first prototype baseline. Planned evolution:
#   manual list -> ESCO -> skill normalization -> semantic matching

COMMON_SKILLS = (
    # Programming languages
    "python", "java", "javascript", "typescript", "c++", "c#", "php", "ruby", "r",
    # Databases
    "sql", "mysql", "postgresql", "mongodb",
    # Web
    "html", "css", "react", "angular", "vue", "node.js", "node",
    "fastapi", "flask", "django",
    # Tools and cloud
    "git", "github", "docker", "kubernetes",
    "aws", "azure", "google cloud", "gcp",
    # Data and analytics
    "power bi", "tableau", "excel", "data analysis", "data analytics",
    "data visualization", "machine learning", "deep learning",
    "artificial intelligence", "natural language processing",
    "computer vision", "statistics",
    # Security and infrastructure
    "cybersecurity", "networking", "network security", "penetration testing",
    "linux", "windows", "microsoft 365", "active directory",
    # IT and engineering practice
    "technical support", "it support", "troubleshooting",
    "system administration", "cloud computing", "software development",
    "software testing", "quality assurance",
    # General
    "project management", "communication", "problem solving",
)

EDUCATION_PATTERNS = (
    r"bachelor'?s degree",
    r"bachelor degree",
    r"master'?s degree",
    r"master degree",
    r"phd",
    r"doctorate",
    r"diploma",
    r"degree in [a-zA-Z0-9 &/\-]+",
    r"diploma in [a-zA-Z0-9 &/\-]+",
)

CERTIFICATION_KEYWORDS = (
    "certification", "certified", "certificate", "comptia", "cisco certified",
    "ccna", "aws certified", "microsoft certified", "azure certification",
    "pmp", "isc2",
)

# Each pattern captures the number of years in group 1.
EXPERIENCE_PATTERNS = (
    r"(\d+(?:\.\d+)?)\+?\s+years?\s+(?:of\s+)?experience",   # "2 years experience"
    r"minimum\s+of\s+(\d+(?:\.\d+)?)\+?\s+years?",           # "minimum of 2 years"
    r"at\s+least\s+(\d+(?:\.\d+)?)\+?\s+years?",             # "at least 2 years"
    r"(\d+(?:\.\d+)?)\+?\s+years?\s+of\s+relevant\s+experience",
)

# Words that suggest a requirement is mandatory / optional.
REQUIRED_KEYWORDS = (
    "required", "must", "mandatory", "minimum", "essential",
    "need to", "needs to", "should have",
)

PREFERRED_KEYWORDS = (
    "preferred", "preferable", "nice to have", "advantage", "plus",
    "bonus", "desirable", "would be an advantage",
)

# NOTE: not used yet. Planned: detect which section of the job description
# a requirement sits in (more reliable than the nearby-words approach).
REQUIRED_SECTION_HEADINGS = (
    "requirements", "required qualifications", "minimum qualifications",
    "essential qualifications", "must have", "key requirements",
)

PREFERRED_SECTION_HEADINGS = (
    "preferred qualifications", "preferred skills", "nice to have",
    "additional qualifications", "desired qualifications",
)

# How confident we are in a detection, by category and requirement type.
# Explicit wording ("must have Python") is trusted more than a bare mention.
CONFIDENCE: dict[str, dict[str, float]] = {
    SKILL:         {REQUIRED: 0.90, PREFERRED: 0.85, UNSPECIFIED: 0.65},
    EDUCATION:     {REQUIRED: 0.90, PREFERRED: 0.75, UNSPECIFIED: 0.75},
    CERTIFICATION: {REQUIRED: 0.85, PREFERRED: 0.65, UNSPECIFIED: 0.65},
    EXPERIENCE:    {REQUIRED: 0.85, PREFERRED: 0.70, UNSPECIFIED: 0.70},
}


# ============================================================
# PRE-COMPILED REGEXES
# ============================================================
# Compiling once at import time is faster than rebuilding a pattern
# for every keyword on every job description.

def _keyword_pattern(keyword: str) -> re.Pattern[str]:
    """
    Match a keyword as a whole word/phrase, ignoring case.

    We use (?<!\\w) and (?!\\w) instead of \\b because \\b breaks on keywords
    that end in symbols, such as "c++" or "c#".
    """
    return re.compile(
        r"(?<!\w)" + re.escape(keyword) + r"(?!\w)",
        flags=re.IGNORECASE,
    )


def _any_word_pattern(words: Iterable[str]) -> re.Pattern[str]:
    """Match any one of several words/phrases as whole words."""
    alternatives = "|".join(re.escape(word) for word in words)
    return re.compile(rf"\b(?:{alternatives})\b", flags=re.IGNORECASE)


_SKILL_PATTERNS = [(skill, _keyword_pattern(skill)) for skill in COMMON_SKILLS]
_CERTIFICATION_PATTERNS = [
    (keyword, _keyword_pattern(keyword)) for keyword in CERTIFICATION_KEYWORDS
]
_EDUCATION_REGEXES = [
    re.compile(pattern, flags=re.IGNORECASE) for pattern in EDUCATION_PATTERNS
]
_EXPERIENCE_REGEXES = [
    re.compile(pattern, flags=re.IGNORECASE) for pattern in EXPERIENCE_PATTERNS
]
_REQUIRED_REGEX = _any_word_pattern(REQUIRED_KEYWORDS)
_PREFERRED_REGEX = _any_word_pattern(PREFERRED_KEYWORDS)


# ============================================================
# TEXT HELPERS
# ============================================================

def clean_text(text: str) -> str:
    """
    Basic normalization that keeps all meaningful content:
    unify line endings, collapse repeated spaces, limit blank lines.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)      # collapse spaces, keep newlines
    text = re.sub(r"\n{3,}", "\n\n", text)   # max one blank line in a row
    return text.strip()


def get_context(
    text: str,
    start: int,
    end: int,
    window: int = CONTEXT_WINDOW,
) -> str:
    """Return the text surrounding a match (`window` characters each side)."""
    return text[max(0, start - window): min(len(text), end + window)]


def determine_requirement_type(context: str) -> str:
    """
    Guess whether the surrounding text marks something as REQUIRED,
    PREFERRED or UNSPECIFIED.

    REQUIRED wins if both kinds of wording appear nearby.
    """
    if _REQUIRED_REGEX.search(context):
        return REQUIRED

    if _PREFERRED_REGEX.search(context):
        return PREFERRED

    return UNSPECIFIED


# ============================================================
# BUILDING A REQUIREMENT
# ============================================================

def _build_requirement(
    text: str,
    match: re.Match[str],
    requirement_text: str,
    category: str,
    source: str,
    **extra: Any,
) -> Requirement:
    """
    Turn one regex match into a requirement dictionary.

    Shared by every extractor so the output format stays identical.
    `extra` lets a category add its own fields (e.g. years for EXPERIENCE).
    """
    context = get_context(text, match.start(), match.end())
    requirement_type = determine_requirement_type(context)

    return {
        "requirement_text": requirement_text,
        "category": category,
        "requirement_type": requirement_type,
        "importance_weight": 1.0,
        "mandatory": requirement_type == REQUIRED,
        "confidence": CONFIDENCE[category][requirement_type],
        "source": source,
        **extra,
    }


def _extract_keywords(
    text: str,
    patterns: list[tuple[str, re.Pattern[str]]],
    category: str,
    source: str,
) -> list[Requirement]:
    """Find each known keyword (first occurrence only) and build requirements."""
    results = []

    for keyword, pattern in patterns:
        match = pattern.search(text)
        if match:
            results.append(
                _build_requirement(text, match, keyword, category, source)
            )

    return results


# ============================================================
# EXTRACTORS (one per category)
# ============================================================

def extract_skills(text: str) -> list[Requirement]:
    """Find skills from COMMON_SKILLS mentioned in the text."""
    return _extract_keywords(text, _SKILL_PATTERNS, SKILL, "RULE_BASED_SKILL_MATCH")


def extract_certifications(text: str) -> list[Requirement]:
    """Find certification keywords mentioned in the text."""
    return _extract_keywords(
        text, _CERTIFICATION_PATTERNS, CERTIFICATION, "RULE_BASED_CERTIFICATION"
    )


def extract_education(text: str) -> list[Requirement]:
    """Find education requirements such as "bachelor's degree in IT"."""
    return [
        _build_requirement(
            text, match, match.group(0).strip(), EDUCATION, "RULE_BASED_EDUCATION"
        )
        for regex in _EDUCATION_REGEXES
        for match in regex.finditer(text)
    ]


def extract_experience(text: str) -> list[Requirement]:
    """
    Find years-of-experience requirements such as "at least 2 years".

    Each result also has a "years" field holding the number as a float.
    The recruiter still has to verify whether it is truly mandatory.
    """
    return [
        _build_requirement(
            text,
            match,
            match.group(0).strip(),
            EXPERIENCE,
            "RULE_BASED_EXPERIENCE",
            years=float(match.group(1)),
        )
        for regex in _EXPERIENCE_REGEXES
        for match in regex.finditer(text)
    ]


# ============================================================
# POST-PROCESSING
# ============================================================

def remove_duplicates(requirements: list[Requirement]) -> list[Requirement]:
    """
    Merge requirements with the same category and text (case-insensitive),
    keeping whichever detection has the higher confidence.
    """
    unique: dict[tuple[str, str], Requirement] = {}

    for requirement in requirements:
        key = (requirement["category"], requirement["requirement_text"].lower())
        existing = unique.get(key)

        if existing is None or requirement["confidence"] > existing["confidence"]:
            unique[key] = requirement

    return list(unique.values())


def _summarize(requirements: list[Requirement]) -> dict[str, int]:
    """Count requirements by category and by required/preferred type."""
    by_category = Counter(r["category"] for r in requirements)
    by_type = Counter(r["requirement_type"] for r in requirements)

    return {
        "total_requirements": len(requirements),
        "skills": by_category[SKILL],
        "education": by_category[EDUCATION],
        "experience": by_category[EXPERIENCE],
        "certifications": by_category[CERTIFICATION],
        "required": by_type[REQUIRED],
        "preferred": by_type[PREFERRED],
    }


# ============================================================
# MAIN ENTRY POINT
# ============================================================

def analyze_job_description(text: str) -> dict[str, Any]:
    """
    Analyze a complete job description.

    Returns:
        {
            "requirements": [ {requirement_text, category, ...}, ... ],
            "summary":      {total_requirements, skills, education, ...},
        }
    """
    cleaned_text = clean_text(text)

    requirements = [
        *extract_skills(cleaned_text),
        *extract_education(cleaned_text),
        *extract_certifications(cleaned_text),
        *extract_experience(cleaned_text),
    ]

    requirements = remove_duplicates(requirements)

    return {
        "requirements": requirements,
        "summary": _summarize(requirements),
    }