
import resume_ner


def test_skill_heading_variants():
    headings = [
        "SKILLS",
        "Technical Skills",
        "Key Skills",
        "Core Skills",
        "Core Competencies",
        "Areas of Expertise",
        "TECHNICAL SKILLS:",
    ]

    for heading in headings:
        result = resume_ner.get_section_type(heading)

        assert result == "SKILL", (
            f"Heading not recognised: {heading}. Got: {result}"
        )

        print(f"[PASS] {heading} -> {result}")


def test_section_switching():
    text = """CERTIFICATIONS
AWS Certified
TECHNICAL SKILLS
Microsoft Excel
Python
PROJECTS
ISS Telemetry Monitoring System
"""

    result = resume_ner.extract_resume_entities(text)
    entities = result["entities"]

    expected = {
        "AWS Certified": "CERTIFICATION",
        "Microsoft Excel": "SKILL",
        "ISS Telemetry Monitoring System": "PROJECT",
    }

    for entity_text, expected_label in expected.items():
        matches = [
            e for e in entities
            if e["text"] == entity_text
        ]

        assert len(matches) == 1, (
            f"Expected one entity for {entity_text}, got {len(matches)}"
        )

        assert matches[0]["label"] == expected_label, (
            f"{entity_text}: expected {expected_label}, "
            f"got {matches[0]['label']}"
        )

        print(f"[PASS] {entity_text} -> {expected_label}")


if __name__ == "__main__":
    test_skill_heading_variants()
    test_section_switching()

    print("\nAll section variant tests passed.")
