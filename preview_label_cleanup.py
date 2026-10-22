import json
from pathlib import Path

path = Path("data/annotations/reviewed_annotations.jsonl")

# Exact entity IDs to reject, keyed by resume ID.
reject = {
    "1": {
        "bootstrap_26",
        "manual_6c74808dff5e",
        "manual_4f246cc735c7",
    },
    "5": {"manual_089519ed03ae"},
    "10": {"manual_eafe346002e9"},
    "13": {
        "manual_2f8ecbb1e652",
        "manual_373879d8fc0b",
    },
    "14": {
        "manual_994246c2df2a",
        "manual_85a6a262b3c8",
    },
    "18": {
        "manual_fe122041d478",
        "manual_39ce80d2fffe",
    },
    "20": {"bootstrap_11"},
}

# Relabel only spans that appear in skills lists.
relabel = {
    "12": {"bootstrap_8": "SKILL"},
    "13": {
        "bootstrap_6": "SKILL",
        "bootstrap_8": "SKILL",
        "bootstrap_9": "SKILL",
    },
    "14": {"bootstrap_2": "SKILL"},
}

records = [
    json.loads(line)
    for line in path.read_text(encoding="utf-8").splitlines()
    if line.strip()
]

found = set()
problems = []

for record in records:
    rid = str(record.get("resume_id"))

    if record.get("review_status") != "REVIEWED" or record.get("review_complete") is not True:
        continue

    for ent in record.get("review_entities", []):
        eid = ent.get("review_id")

        if eid in reject.get(rid, set()):
            found.add(("reject", rid, eid))
            print(
                f"REJECT | Resume {rid} | {ent.get('label')} | "
                f"{ent.get('text')!r} | {eid}"
            )

        if eid in relabel.get(rid, {}):
            found.add(("relabel", rid, eid))
            print(
                f"RELABEL | Resume {rid} | {ent.get('label')} -> "
                f"{relabel[rid][eid]} | {ent.get('text')!r} | {eid}"
            )

expected = {
    ("reject", rid, eid)
    for rid, ids in reject.items()
    for eid in ids
} | {
    ("relabel", rid, eid)
    for rid, ids in relabel.items()
    for eid in ids
}

missing = expected - found

print("\n--- DRY RUN SUMMARY ---")
print("Proposed rejections:", sum(len(v) for v in reject.values()))
print("Proposed relabels:", sum(len(v) for v in relabel.values()))
print("Missing expected entities:", len(missing))

if missing:
    print("STOP: Some expected IDs were not found:")
    for item in sorted(missing):
        print(item)
else:
    print("All target IDs were found. No files were changed.")
