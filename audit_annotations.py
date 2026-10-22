import json
from collections import Counter
from pathlib import Path

path = Path("data/annotations/reviewed_annotations.jsonl")
label_counts = Counter()
resume_counts = Counter()
examples = {}
total_resumes = 0

with path.open("r", encoding="utf-8") as f:
    for line in f:
        if not line.strip():
            continue

        record = json.loads(line)

        if record.get("review_status") != "REVIEWED":
            continue
        if record.get("review_complete") is not True:
            continue

        total_resumes += 1
        resume_id = record.get("resume_id", "unknown")

        for entity in record.get("review_entities", []):
            if entity.get("accepted") is not True:
                continue

            label = entity.get("label", "UNKNOWN")
            phrase = entity.get("text", "")

            label_counts[label] += 1
            resume_counts[label] += 1

            examples.setdefault(label, [])
            if phrase and len(examples[label]) < 12:
                examples[label].append(
                    f"Resume {resume_id}: {phrase}"
                )

print(f"\nCompleted resumes: {total_resumes}")
print("\nACCEPTED ENTITY COUNTS ACROSS ALL RESUMES")
for label, count in label_counts.most_common():
    print(f"{label:24} {count:4}")

print("\nEXAMPLES BY LABEL")
for label in sorted(examples):
    print(f"\n{label} ({label_counts[label]} total)")
    for example in examples[label]:
        print(f"  - {example}")
