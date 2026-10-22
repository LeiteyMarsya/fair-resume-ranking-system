import json
from pathlib import Path

path = Path("data/annotations/reviewed_annotations.jsonl")

targets = {
    "11": {"Developed and implemented comprehensive analytics strategies"},
    "8": {"dashboards", "provided recommendations"},
    "4": {"Data Projects Volunteer"},
}

with path.open(encoding="utf-8") as f:
    for line in f:
        if not line.strip():
            continue

        record = json.loads(line)
        rid = str(record.get("resume_id"))

        if rid not in targets:
            continue

        for ent in record.get("review_entities", []):
            if ent.get("text") in targets[rid]:
                print(
                    f"Resume {rid} | "
                    f"Text: {ent.get('text')!r} | "
                    f"Label: {ent.get('label')} | "
                    f"Review ID: {ent.get('review_id')} | "
                    f"Accepted: {ent.get('accepted')}"
                )
