import json
from pathlib import Path

path = Path("data/annotations/reviewed_annotations.jsonl")

targets = {
    "CERTIFICATION",
    "COURSE",
    "EDUCATION",
    "PROJECT",
    "JOB_TITLE",
    "EXPERIENCE",
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

            start = ent.get("start")
            end = ent.get("end")
            phrase = ent.get("text", "")

            suspicious = (
                ent.get("label") in {"CERTIFICATION", "COURSE", "JOB_TITLE"}
                or phrase in {
                    "Machine Learning",
                    "Developed and implemented comprehensive analytics strategies",
                    "Enhanced Data Accuracy",
                    "Data Projects Volunteer",
                    "dashboards",
                    "provided recommendations",
                }
            )

            if not suspicious:
                continue

            context = text[max(0, start - 120):min(len(text), end + 120)]

            print(
                f"\nResume {record.get('resume_id')} | "
                f"{ent.get('label')} | {phrase!r}"
            )
            print(context.replace("\n", " "))
