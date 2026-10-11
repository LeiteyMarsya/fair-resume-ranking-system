
from pathlib import Path

import spacy


BASE_DIR = Path(__file__).resolve().parent

MODEL_PATH = BASE_DIR / "models" / "resume_ner" / "model-best"


def main() -> None:

    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            "Trained model not found. "
            "Run the spaCy training command first."
        )

    nlp = spacy.load(MODEL_PATH)

    sample_text = """
    Education
    Bachelor of Information Technology

    Projects
    Developed an inventory monitoring system using Python and MySQL.

    Courses
    Database Management

    Experience
    IT Support Internship
    """

    doc = nlp(sample_text)

    print("\nPREDICTED ENTITIES")
    print("=" * 50)

    if not doc.ents:
        print("No entities were predicted.")
        print(
            "This may occur if the training dataset is too small "
            "or the model has not learned the labels yet."
        )

    for entity in doc.ents:
        print(
            f"{entity.text:<45} {entity.label_}"
        )


if __name__ == "__main__":
    main()