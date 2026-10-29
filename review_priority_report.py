import csv
import json
from collections import Counter
from pathlib import Path

import spacy
import custom_tokenizer


BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "annotations" / "reviewed_annotations.jsonl"
MODEL_PATH = BASE_DIR / "models" / "resume_ner" / "model-best"


def main():
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Annotation file not found: {DATA_PATH}")

    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found: {MODEL_PATH}")

    with DATA_PATH.open("r", encoding="utf-8") as file:
        records = [
            json.loads(line)
            for line in file
            if line.strip()
        ]

    nlp = spacy.load(MODEL_PATH)
    results = []

    for record in records:
        text = record.get("text", "")
        doc = nlp(text)

        predicted = {
            (ent.start_char, ent.end_char, ent.label_, ent.text)
            for ent in doc.ents
        }

        accepted = {
            (
                entity.get("start"),
                entity.get("end"),
                entity.get("label"),
                entity.get("text"),
            )
            for entity in record.get("review_entities", [])
            if entity.get("accepted", False)
        }

        unmatched_predictions = predicted - accepted
        unmatched_accepted = accepted - predicted

        # Count different labels assigned to the same character span.
        predicted_by_span = {}
        accepted_by_span = {}

        for start, end, label, entity_text in predicted:
            predicted_by_span.setdefault((start, end), set()).add(label)

        for start, end, label, entity_text in accepted:
            accepted_by_span.setdefault((start, end), set()).add(label)

        label_disagreements = sum(
            1
            for span in predicted_by_span.keys() & accepted_by_span.keys()
            if predicted_by_span[span] != accepted_by_span[span]
        )

        unmatched_prediction_count = len(unmatched_predictions)
        unmatched_accepted_count = len(unmatched_accepted)

        results.append({
            "resume_id": record.get("resume_id"),
            "blind_id": record.get("blind_id", "UNKNOWN"),
            "status": record.get("review_status", "UNKNOWN"),
            "accepted_count": len(accepted),
            "prediction_count": len(predicted),
            "unmatched_accepted": unmatched_accepted_count,
            "unmatched_predictions": unmatched_prediction_count,
            "label_disagreements": label_disagreements,
            "total_disagreements": (
                unmatched_accepted_count + unmatched_prediction_count
            ),
        })

    # Highest exact-span disagreement count first.
    results.sort(
        key=lambda item: (
            item["total_disagreements"],
            item["unmatched_accepted"],
            item["unmatched_predictions"],
            item["resume_id"] if item["resume_id"] is not None else -1,
        ),
        reverse=True,
    )

    print("\nREAD-ONLY RESUME REVIEW PRIORITY REPORT")
    print("=" * 100)
    print("No annotation or model files were changed.")
    print("Priority is based on exact-span disagreements, not calibrated uncertainty.\n")

    headers = (
        "Rank", "Resume ID", "Blind ID", "Status",
        "Accepted", "Predicted", "Missed", "Extra", "Label diff", "Total"
    )
    print(
        f"{headers[0]:<5} {headers[1]:<10} {headers[2]:<18} "
        f"{headers[3]:<12} {headers[4]:>8} {headers[5]:>9} "
        f"{headers[6]:>7} {headers[7]:>6} {headers[8]:>11} {headers[9]:>6}"
    )
    print("-" * 100)

    for rank, item in enumerate(results, start=1):
        print(
            f"{rank:<5} {str(item['resume_id']):<10} "
            f"{item['blind_id']:<18.18} {item['status']:<12.12} "
            f"{item['accepted_count']:>8} {item['prediction_count']:>9} "
            f"{item['unmatched_accepted']:>7} "
            f"{item['unmatched_predictions']:>6} "
            f"{item['label_disagreements']:>11} "
            f"{item['total_disagreements']:>6}"
        )

    totals = Counter()
    for item in results:
        for key in (
            "accepted_count",
            "prediction_count",
            "unmatched_accepted",
            "unmatched_predictions",
            "label_disagreements",
            "total_disagreements",
        ):
            totals[key] += item[key]

    print("\nSUMMARY")
    print(f"Resumes evaluated: {len(results)}")
    print(f"Accepted annotations: {totals['accepted_count']}")
    print(f"Model predictions: {totals['prediction_count']}")
    print(f"Unmatched accepted annotations: {totals['unmatched_accepted']}")
    print(f"Unmatched predictions: {totals['unmatched_predictions']}")
    print(f"Same-span label disagreements: {totals['label_disagreements']}")

    print(
        "\nInterpretation: use this ranking to guide human inspection. "
        "Exact-span differences can include boundary differences and "
        "do not automatically mean a prediction is wrong."
    )
    return results

def export_csv(results):
    output_path = BASE_DIR / "data" / "annotations" / "review_priority_report.csv"

    fieldnames = [
        "resume_id",
        "blind_id",
        "status",
        "accepted_count",
        "prediction_count",
        "unmatched_accepted",
        "unmatched_predictions",
        "label_disagreements",
        "total_disagreements",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\nCSV report saved to: {output_path}")


if __name__ == "__main__":
	
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--csv",
        action="store_true",
        help="Export the review priority report to a separate CSV file.",
    )
    args = parser.parse_args()

    results = main()
	

    if args.csv:
        export_csv(results)