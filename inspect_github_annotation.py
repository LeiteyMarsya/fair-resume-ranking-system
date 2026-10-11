
import json
from pathlib import Path

import spacy


BASE_DIR = Path(__file__).resolve().parent
ANNOTATION_DIR = BASE_DIR / "data" / "annotations"

FILES = [
    ANNOTATION_DIR / "bootstrap_candidates.jsonl",
    ANNOTATION_DIR / "reviewed_annotations.jsonl",
]


def read_jsonl(path):
    records = []

    if not path.exists():
        print(f"\nFILE NOT FOUND: {path.name}")
        return records

    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue

            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as error:
                print(
                    f"Invalid JSON in {path.name}, "
                    f"line {line_number}: {error}"
                )

    return records


def inspect_file(path):
    print("\n" + "=" * 70)
    print(f"FILE: {path.name}")
    print("=" * 70)

    records = read_jsonl(path)

    if not records:
        return

    found = False

    for record in records:
        resume_id = record.get("resume_id")
        source_text = record.get("text", "")

        # The original bootstrap file usually uses "entities".
        # The reviewed file uses "review_entities".
        for field in ("entities", "review_entities"):

            entities = record.get(field, [])

            if not isinstance(entities, list):
                continue

            for entity in entities:

                start = entity.get("start")
                end = entity.get("end")
                entity_text = entity.get("text", "")

                is_github = (
                    isinstance(entity_text, str)
                    and "github" in entity_text.lower()
                )

                is_target_span = (
                    resume_id == 1
                    and start == 118
                    and end == 124
                )

                if not (is_github or is_target_span):
                    continue

                found = True

                print(f"\nResume ID: {resume_id}")
                print(f"Entity field: {field}")
                print(f"Entity text: {entity_text!r}")
                print(f"Label: {entity.get('label')}")
                print(f"Start: {start}")
                print(f"End: {end}")
                print(f"Accepted: {entity.get('accepted', 'not set')}")
                print(f"Origin: {entity.get('origin', 'unknown')}")
                print(f"Source: {entity.get('source', 'unknown')}")
                print(f"Review action: {entity.get('review_action', 'not set')}")
                print(f"Review status: {record.get('review_status', 'not set')}")

                if (
                    isinstance(start, int)
                    and isinstance(end, int)
                    and 0 <= start < end <= len(source_text)
                ):
                    actual_text = source_text[start:end]

                    print(f"Actual source span: {actual_text!r}")
                    print(
                        "Nearby text:",
                        repr(
                            source_text[
                                max(0, start - 35):
                                min(len(source_text), end + 35)
                            ]
                        ),
                    )

                    nlp = spacy.blank("en")
                    doc = nlp.make_doc(source_text)

                    span = doc.char_span(
                        start,
                        end,
                        alignment_mode="strict",
                    )

                    print(
                        "Strict token alignment:",
                        "PASS" if span is not None else "FAIL",
                    )

                    if span is not None:
                        print(f"spaCy token span: {span.text!r}")

                else:
                    print("Source offsets are invalid or missing.")

    if not found:
        print("No matching GitHub annotation found in this file.")


if __name__ == "__main__":
    for file_path in FILES:
        inspect_file(file_path)
