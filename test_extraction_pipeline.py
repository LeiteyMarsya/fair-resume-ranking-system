
import resume_ner

sample_resume = """
JOHN DOE

EDUCATION
Bachelor of Information Technology

CERTIFICATIONS
AWS Certified
CCNA

SKILLS
Python
SQL
Microsoft Excel

WORK EXPERIENCE
3 years of relevant experience

PROJECTS
ISS Telemetry Monitoring System
Smart Campus Application
"""

print("\n===== RAW SPACY / ENTITYRULER =====")
doc = resume_ner.nlp(sample_resume)

for ent in doc.ents:
    print(
        f"{ent.label_:22} | "
        f"{ent.text:40} | "
        f"Start: {ent.start_char}, End: {ent.end_char}"
    )

print("\n===== RAW REGEX ENTITIES =====")
regex_entities = resume_ner.extract_regex_entities(sample_resume)

for entity in regex_entities:
    print(entity)

print("\n===== RAW SECTION ENTITIES =====")
section_entities = resume_ner.extract_section_entities(sample_resume)

for entity in section_entities:
    print(entity)

print("\n===== FINAL EXTRACTED ENTITIES =====")
result = resume_ner.extract_resume_entities(sample_resume)

for entity in result["entities"]:
    print(entity)

print("\n===== SUMMARY =====")
print(result["summary"])
