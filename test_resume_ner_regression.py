
import resume_ner


def get_entity(entities, text):
    return [
        entity for entity in entities
        if entity["text"] == text
    ]


def test_skill_section_after_certification():
    text = """CERTIFICATIONS
AWS Certified
CCNA

SKILLS
Python
SQL
Microsoft Excel
"""

    result = resume_ner.extract_resume_entities(text)
    entities = result["entities"]

    for skill in ["Python", "SQL", "Microsoft Excel"]:
        matches = get_entity(entities, skill)

        assert len(matches) == 1, (
            f"Expected exactly one entity for {skill}"
        )
        assert matches[0]["label"] == "SKILL", (
            f"{skill} was incorrectly classified"
        )


def test_experience_duration_priority():
    text = """WORK EXPERIENCE
3 years of relevant experience
"""

    result = resume_ner.extract_resume_entities(text)
    matches = get_entity(
        result["entities"],
        "3 years of relevant experience"
    )

    assert len(matches) == 1
    assert matches[0]["label"] == "EXPERIENCE_DURATION"


def test_exact_character_offsets():
    text = """SKILLS
    - Microsoft Excel
"""

    result = resume_ner.extract_resume_entities(text)

    matches = get_entity(
        result["entities"],
        "Microsoft Excel"
    )

    assert len(matches) == 1

    entity = matches[0]

    assert text[entity["start"]:entity["end"]] == entity["text"]


def test_education_and_project_extraction():
    text = """EDUCATION
Bachelor of Information Technology

PROJECTS
ISS Telemetry Monitoring System
"""

    result = resume_ner.extract_resume_entities(text)
    entities = result["entities"]

    education = get_entity(
        entities,
        "Bachelor of Information Technology"
    )

    project = get_entity(
        entities,
        "ISS Telemetry Monitoring System"
    )

    assert any(e["label"] == "EDUCATION" for e in education)
    assert any(e["label"] == "PROJECT" for e in project)


def run_tests():
    tests = [
        test_skill_section_after_certification,
        test_experience_duration_priority,
        test_exact_character_offsets,
        test_education_and_project_extraction,
    ]

    passed = 0

    for test in tests:
        test()
        passed += 1
        print(f"[PASS] {test.__name__}")

    print(f"\n{passed}/{len(tests)} regression tests passed.")


if __name__ == "__main__":
    run_tests()
