import json
import shutil
from pathlib import Path

path = Path("data/annotations/reviewed_annotations.jsonl")
backup = Path("data/annotations/reviewed_annotations_before_label_cleanup.jsonl")

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

# Validate every target before changing anything.
found = set()

for record in records:
    rid = str(record.get("resume_id"))

    for ent in record.get("review_entities", []):
        eid = ent.get("review_id")

        if eid in reject.get(rid, set()):
            found.add(("reject", rid, eid))

        if eid in relabel.get(rid, {}):
            found.add(("relabel", rid, eid))

expected = {
    ("reject", rid, eid)
    for rid, ids in reject.items()
    for eid in ids
} | {
    ("relabel", rid, eid)
    for rid, ids in relabel.items()
    for eid in ids
}

if found != expected:
    print("STOP: target verification failed.")
    print("Missing:", sorted(expected - found))
    raise SystemExit(1)

if not backup.exists():
    shutil.copy2(path, backup)
    print("Created backup:", backup)
else:
    print("Using existing backup:", backup)

rejected_count = 0
relabelled_count = 0

for record in records:
    rid = str(record.get("resume_id"))

    for ent in record.get("review_entities", []):
        eid = ent.get("review_id")

        if eid in reject.get(rid, set()):
            ent["accepted"] = False
            rejected_count += 1

        if eid in relabel.get(rid, {}):
            ent["label"] = relabel[rid][eid]
            relabelled_count += 1

temporary = path.with_name(path.name + ".cleanup.tmp")

with temporary.open("w", encoding="utf-8", newline="\n") as f:
    for record in records:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

# Confirm the temporary file is valid JSONL before replacing the original.
with temporary.open(encoding="utf-8") as f:
    checked = [json.loads(line) for line in f if line.strip()]

if len(checked) != len(records):
    temporary.unlink(missing_ok=True)
    raise RuntimeError("Verification failed; original file was not replaced.")

temporary.replace(path)

print("\nCLEANUP COMPLETED")
print("Rejected entities:", rejected_count)
print("Relabelled entities:", relabelled_count)
print("Resume records preserved:", len(records))
print("Backup:", backup)
