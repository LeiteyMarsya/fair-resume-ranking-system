import json
from pathlib import Path

path = Path("data/annotations/reviewed_annotations.jsonl")
targets = {
    "CERTIFICATION",
    "COURSE",
    "EXPERIENCE",
    "JOB_TITLE",
    "PROJECT",
}

with path.open(encoding="utf-8") as f:
    for line in f:
        if not line.strip():
            continue
        record = json.loads(line)

        if record.get("review_status") != "REVIEWED":
            continue
        if record.get("review_complete") is not True:
            continue

        text = record.get("text", "")
        for ent in record.get("review_entities", []):
            if ent.get("accepted") is not True:
                continue
            if ent.get("label") not in targets:
                continue

            start, end = ent.get("start"), ent.get("end")
            context = text[max(0, start-100):min(len(text), end+100)]
            print(
                f"\nResume {record.get('resume_id')} | "
                f"{ent.get('label')} | {ent.get('text')!r}"
            )
            print(context.replace("\n", " "))
