"""
Prepare spaCy training data from human-reviewed resume annotations.

Steps:
    1. Load resumes whose review is marked complete.
    2. Check every accepted entity and convert each resume into a
       spaCy Doc with its entities.
    3. Split the resumes into train / dev / test sets. Resumes from the
       same candidate always stay together, so the model is never tested
       on a candidate it trained on.
    4. Save the three sets as .spacy files, plus a JSON report.

Run it with:  python prepare_training_data.py
"""

from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import spacy
from spacy.tokens import DocBin

from annotation_review import ALLOWED_LABELS, REVIEWED_PATH, read_jsonl

# One prepared resume: {"resume_id": ..., "group_id": ..., "doc": spaCy Doc}.
Document = dict[str, Any]

BASE_DIR = Path(__file__).resolve().parent
ANNOTATION_DIR = BASE_DIR / "data" / "annotations"

TRAIN_PATH = ANNOTATION_DIR / "train.spacy"
DEV_PATH = ANNOTATION_DIR / "dev.spacy"
TEST_PATH = ANNOTATION_DIR / "test.spacy"
REPORT_PATH = ANNOTATION_DIR / "training_data_report.json"

SPLIT_PATHS = {"train": TRAIN_PATH, "dev": DEV_PATH, "test": TEST_PATH}

LANGUAGE = "en"        # blank English tokenizer
RANDOM_SEED = 42       # fixed so the split is the same on every run
TEST_FRACTION = 0.15   # share of candidates used for testing
DEV_FRACTION = 0.15    # share of candidates used for validation

# Below this many resumes, results are only a pipeline test.
MIN_RELIABLE_DOCUMENTS = 20


# Loading reviews

def load_completed_reviews() -> list[dict[str, Any]]:
    """
    Load only fully reviewed resumes.

    Pending and in-progress annotations must not become training data.
    """
    if not REVIEWED_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found: {REVIEWED_PATH}\n"
            "Complete Part 4B reviews before training."
        )

    completed = [
        record
        for record in read_jsonl(REVIEWED_PATH)
        if record.get("review_status") == "REVIEWED"
        and record.get("review_complete") is True
    ]

    if not completed:
        raise ValueError(
            "No completed human reviews were found.\n"
            "Open Review Annotations, finish reviewing a resume, "
            "tick the completion checkbox, and save it."
        )

    # The same resume must not appear twice.
    resume_ids = [str(record.get("resume_id")) for record in completed]
    if len(resume_ids) != len(set(resume_ids)):
        raise ValueError(
            "Duplicate resume IDs were found in the reviewed "
            "dataset. Resolve these before preparing training data."
        )

    return completed


# Validating and converting to spaCy

def validate_entity(
    entity: dict[str, Any],
    text: str,
    resume_id: Any,
    valid_labels: set[str],
) -> tuple[int, int, str, str]:
    """
    Check one accepted entity and return (start, end, label, text).

    Raises ValueError with a clear message if anything is wrong.
    """
    if entity.get("reviewed_by_human") is not True:
        raise ValueError(
            f"Resume {resume_id} contains an accepted "
            "entity that is not marked as human-reviewed."
        )

    label = entity.get("label")
    if label not in valid_labels:
        raise ValueError(
            f"Resume {resume_id}: unsupported label "
            f"{label!r} for entity {entity.get('text')!r}."
        )

    start = entity.get("start")
    end = entity.get("end")
    entity_text = entity.get("text")

    if (
        not isinstance(start, int)
        or not isinstance(end, int)
        or not isinstance(entity_text, str)
    ):
        raise ValueError(
            f"Resume {resume_id}: invalid offsets or text "
            f"for entity {entity!r}."
        )

    if not 0 <= start < end <= len(text):
        raise ValueError(
            f"Resume {resume_id}: invalid character offsets "
            f"{start}:{end} for {entity_text!r}."
        )

    actual_text = text[start:end]
    if actual_text != entity_text:
        raise ValueError(
            f"Resume {resume_id}: annotation text does not "
            f"match source offsets.\n"
            f"Label: {label}\n"
            f"Expected text: {entity_text!r}\n"
            f"Source text:   {actual_text!r}\n"
            "Correct the annotation in Review Annotations."
        )

    return start, end, label, entity_text


def check_no_overlaps(
    spans: list[tuple[int, int, str, str]],
    resume_id: Any,
) -> None:
    """
    Make sure no two entities overlap (spaCy cannot train on overlaps).

    Sorts `spans` in place so neighbours can be compared.
    """
    spans.sort(key=lambda span: (span[0], span[1]))

    for previous, current in zip(spans, spans[1:]):
        if current[0] < previous[1]:
            raise ValueError(
                f"Resume {resume_id} has overlapping accepted "
                f"entities: {previous[3]!r} ({previous[2]}) and "
                f"{current[3]!r} ({current[2]}).\n"
                "Resolve the overlap in Review Annotations."
            )


def build_doc(
    nlp,
    text: str,
    spans: list[tuple[int, int, str, str]],
    resume_id: Any,
):
    """Create a spaCy Doc from the text and mark its entities."""
    doc = nlp.make_doc(text)
    entities = []

    for start, end, label, entity_text in spans:
        # "strict" means the entity must start and end on token boundaries.
        span = doc.char_span(start, end, label=label, alignment_mode="strict")

        if span is None:
            raise ValueError(
                f"Resume {resume_id}: entity {entity_text!r} "
                f"at characters {start}:{end} does not align "
                "with spaCy's token boundaries.\n"
                "Review the phrase boundaries in Part 4B."
            )

        entities.append(span)

    doc.ents = entities
    return doc


def prepare_documents(records: list[dict[str, Any]], nlp) -> list[Document]:
    """
    Convert completed reviews into spaCy Docs.

    Each result also stores a group ID (the candidate's blind ID) that
    is used later to keep one candidate's resumes in the same split.
    """
    valid_labels = set(ALLOWED_LABELS)
    prepared = []

    for record in records:
        resume_id = record.get("resume_id")
        text = record.get("text", "")
        review_entities = record.get("review_entities", [])

        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"Resume {resume_id} has no usable text.")

        if not isinstance(review_entities, list):
            raise ValueError(f"Resume {resume_id} has an invalid entity list.")

        # Rejected suggestions are not positive labels, so skip them.
        spans = [
            validate_entity(entity, text, resume_id, valid_labels)
            for entity in review_entities
            if entity.get("accepted", False) is True
        ]

        check_no_overlaps(spans, resume_id)

        prepared.append(
            {
                "resume_id": resume_id,
                "group_id": str(record.get("blind_id") or f"resume-{resume_id}"),
                "doc": build_doc(nlp, text, spans, resume_id),
            }
        )

    return prepared


# Splitting and saving

def split_by_candidate(documents: list[Document]) -> dict[str, list[Document]]:
    """
    Split candidate groups into train, dev and test.

    Whole candidates are assigned to a split, so resumes sharing a
    blind_id never end up in different splits.
    """
    groups = defaultdict(list)
    for item in documents:
        groups[item["group_id"]].append(item)

    group_ids = list(groups)
    total_groups = len(group_ids)

    if total_groups < 3:
        raise ValueError(
            f"Found only {total_groups} unique candidate group(s).\n"
            "At least 3 are required to create train/dev/test splits. "
            "This is only a technical minimum; such a small dataset "
            "cannot provide a reliable model evaluation."
        )

    random.Random(RANDOM_SEED).shuffle(group_ids)

    test_count = max(1, round(total_groups * TEST_FRACTION))
    dev_count = max(1, round(total_groups * DEV_FRACTION))

    # Safety net: always leave at least one group for training.
    while test_count + dev_count >= total_groups:
        if dev_count > 1:
            dev_count -= 1
        elif test_count > 1:
            test_count -= 1
        else:
            raise ValueError("Unable to create non-empty train/dev/test splits.")

    # After shuffling: first groups -> test, next -> dev, the rest -> train.
    split_of_group = {}
    for position, group_id in enumerate(group_ids):
        if position < test_count:
            split_of_group[group_id] = "test"
        elif position < test_count + dev_count:
            split_of_group[group_id] = "dev"
        else:
            split_of_group[group_id] = "train"

    splits: dict[str, list[Document]] = {"train": [], "dev": [], "test": []}
    for group_id, group_documents in groups.items():
        splits[split_of_group[group_id]].extend(group_documents)

    return splits


def write_docbin(documents: list[Document], output_path: Path) -> None:
    """Save the Docs in spaCy's binary .spacy format."""
    doc_bin = DocBin()

    for item in documents:
        doc_bin.add(item["doc"])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc_bin.to_disk(output_path)


# Report

def count_labels(documents: list[Document]) -> dict[str, int]:
    """Count entities per label, sorted by label name."""
    counts = Counter(
        entity.label_ for item in documents for entity in item["doc"].ents
    )
    return dict(sorted(counts.items()))


def unique_groups(documents: list[Document]) -> set[str]:
    """The set of candidate group IDs in a list of documents."""
    return {item["group_id"] for item in documents}


def build_warnings(
    total_documents: int,
    split_reports: dict[str, dict[str, Any]],
) -> list[str]:
    """List problems that make the dataset unreliable for training."""
    warnings = []
    labels_in_training = set(split_reports["train"]["labels"])

    if total_documents < MIN_RELIABLE_DOCUMENTS:
        warnings.append(
            f"Fewer than {MIN_RELIABLE_DOCUMENTS} reviewed resumes are "
            "available. Treat this run as a pipeline test, not as evidence "
            "of reliable generalization."
        )

    if not labels_in_training:
        warnings.append("The training split contains no accepted entity labels.")

    # Labels the model never saw in training can't be evaluated fairly.
    for split_name in ("dev", "test"):
        unseen = set(split_reports[split_name]["labels"]) - labels_in_training
        if unseen:
            warnings.append(
                f"{split_name} contains labels absent from training: "
                f"{sorted(unseen)}. Metrics for those labels "
                "will not be meaningful."
            )

    return warnings


def build_report(
    documents: list[Document],
    splits: dict[str, list[Document]],
) -> dict[str, Any]:
    """Summarize the dataset: counts per split plus any warnings."""
    split_reports = {
        name: {
            "documents": len(split_documents),
            "candidate_groups": len(unique_groups(split_documents)),
            "entities": sum(len(item["doc"].ents) for item in split_documents),
            "labels": count_labels(split_documents),
        }
        for name, split_documents in splits.items()
    }

    return {
        "source": REVIEWED_PATH.name,
        "random_seed": RANDOM_SEED,
        "total_reviewed_documents": len(documents),
        "unique_candidate_groups": len(unique_groups(documents)),
        "splits": split_reports,
        "warnings": build_warnings(len(documents), split_reports),
    }


def print_report(report: dict[str, Any]) -> None:
    """Print the report in a readable format."""
    print("\nDATA PREPARATION COMPLETED")
    print("=" * 55)
    print(f"Reviewed resumes: {report['total_reviewed_documents']}")
    print(f"Candidate groups: {report['unique_candidate_groups']}")

    for split_name, split_report in report["splits"].items():
        print(f"\n{split_name.upper()}")
        print(f"  Documents: {split_report['documents']}")
        print(f"  Candidate groups: {split_report['candidate_groups']}")
        print(f"  Accepted entity spans: {split_report['entities']}")
        print(f"  Labels: {split_report['labels']}")

    if report["warnings"]:
        print("\nWARNINGS")
        for warning in report["warnings"]:
            print(f"- {warning}")

    print("\nGenerated files:")
    for path in (*SPLIT_PATHS.values(), REPORT_PATH):
        print(f"  {path}")


# Main

def main() -> None:
    print("Loading completed human reviews...")
    records = load_completed_reviews()

    nlp = spacy.blank(LANGUAGE)
    documents = prepare_documents(records, nlp)
    print(f"Validated {len(documents)} reviewed resume(s).")

    splits = split_by_candidate(documents)

    for split_name, path in SPLIT_PATHS.items():
        write_docbin(splits[split_name], path)

    report = build_report(documents, splits)

    with REPORT_PATH.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2, ensure_ascii=False)

    print_report(report)


if __name__ == "__main__":
    main()