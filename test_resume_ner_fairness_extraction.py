
import resume_ner


def get_section_entities(text):
    return resume_ner.extract_section_entities(text)


def test_inline_language_heading_stops_skill_extraction():

    text = """SKILLS
Python, SQL, Tableau
Languages: English (Native), German (Fluent)
"""

    entities = get_section_entities(text)

    skills = [
        entity["text"]
        for entity in entities
        if entity["label"] == "SKILL"
    ]

    assert skills == ["Python", "SQL", "Tableau"]
    print("[PASS] Inline language heading stops skill extraction")


def test_volunteering_heading_stops_experience_extraction():

    text = """WORK EXPERIENCE
Data Analyst Intern
VOLUNTEERING ACTIVITIES AND EXTRACURRICULARS
Data Analysis Volunteer
"""

    entities = get_section_entities(text)

    assert not any(
        entity["text"] == "Data Analysis Volunteer"
        and entity["label"] == "EXPERIENCE"
        for entity in entities
    )

    print("[PASS] Volunteering heading stops experience extraction")


def test_etl_compound_skill_is_preserved():

    text = """SKILLS
Python, SQL, Extract, Transform, Load (ETL), Tableau
"""

    entities = get_section_entities(text)

    skills = [
        entity["text"]
        for entity in entities
        if entity["label"] == "SKILL"
    ]

    assert "Extract, Transform, Load (ETL)" in skills
    assert "Extract" not in skills
    assert "Transform" not in skills
    assert "Load (ETL)" not in skills

    print("[PASS] Compound ETL skill preserved")


def test_proficiency_annotations_are_removed():

    text = """SKILLS
Python (Advanced), Tableau (Experienced)
"""

    entities = get_section_entities(text)

    skills = [
        entity["text"]
        for entity in entities
        if entity["label"] == "SKILL"
    ]

    assert skills == ["Python", "Tableau"]

    print("[PASS] Proficiency annotations removed")


def test_separator_and_template_noise_are_ignored():

    text = """SKILLS
Python
________________________________________________________________
Don't forget to use Resume Worded to scan your resume
www.enhancv.com
Powered by
SQL
"""

    entities = get_section_entities(text)

    skills = [
        entity["text"]
        for entity in entities
        if entity["label"] == "SKILL"
    ]

    assert skills == ["Python", "SQL"]

    print("[PASS] Separator and template noise ignored")


def test_skill_offsets_are_correct():

    text = """SKILLS
Python, SQL, Extract, Transform, Load (ETL)
"""

    entities = get_section_entities(text)

    for entity in entities:

        start = entity["start"]
        end = entity["end"]

        assert text[start:end] == entity["text"], (
            f"Incorrect offset for {entity['text']}"
        )

    print("[PASS] Skill character offsets are correct")


if __name__ == "__main__":

    tests = [
        test_inline_language_heading_stops_skill_extraction,
        test_volunteering_heading_stops_experience_extraction,
        test_etl_compound_skill_is_preserved,
        test_proficiency_annotations_are_removed,
        test_separator_and_template_noise_are_ignored,
        test_skill_offsets_are_correct,
    ]

    for test in tests:
        test()

    print("\nAll fairness extraction tests passed.")
