
from pathlib import Path
import spacy

MODEL_PATH = Path("models/resume_ner/model-best")

if not MODEL_PATH.exists():
    raise FileNotFoundError(
        f"Trained model not found: {MODEL_PATH}"
    )

nlp = spacy.load(MODEL_PATH)

sample_text = """
EDUCATION
Bachelor of Information Technology

SKILLS
Python, MySQL, HTML, CSS, JavaScript

PROJECTS
Developed a web application using Python and MySQL.

WORK EXPERIENCE
IT Support Intern for 5 months.
"""

doc = nlp(sample_text)

print("\nNER PREDICTIONS")
print("=" * 40)

if not doc.ents:
    print("No entities detected.")
else:
    for entity in doc.ents:
        print(f"{entity.text} --> {entity.label_}")
