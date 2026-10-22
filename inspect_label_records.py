import json
from pathlib import Path

path = Path("data/annotations/reviewed_annotations.jsonl")

with path.open(encoding="utf-8") as f:
    for line in f:
        if not line.strip():
            continue
        record = json.loads(line)

        if str(record.get("resume_id")) in {"1", "5", "10", "12", "13", "14", "18", "20"}:
            print("\nResume:", record.get("resume_id"))
            print("Review status:", record.get("review_status"))
            print("Review complete:", record.get("review_complete"))

            for ent in record.get("review_entities", []):
                if ent.get("accepted") is True and ent.get("label") in {
                    "COURSE", "CERTIFICATION", "EXPERIENCE",
                    "JOB_TITLE", "PROJECT"
                }:
                    print({
                        "text": ent.get("text"),
                        "label": ent.get("label"),
                        "start": ent.get("start"),
                        "end": ent.get("end"),
                        "accepted": ent.get("accepted"),
                        "review_id": ent.get("review_id")
                    })
