import json
from pathlib import Path

path = Path("data/annotations/reviewed_annotations.jsonl")

reject = {
    "11": {"manual_96170f612f50"},
    "8": {"manual_ebd8cfc1d04d", "manual_ac1df9ed4c9a"},
}

relabel = {
    "4": {"manual_2a1efae7f8a0": "JOB_TITLE"},
}

records = [
    json.loads(line)
    for line in path.read_text(encoding="utf-8").splitlines()
    if line.strip()
]

# Verify every target before making changes.
found_reject = set()
found_relabel = set()

for record in records:
    rid = str(record.get("resume_id"))

    for ent in record.get("review_entities", []):
        eid = ent.get("review_id")

        if eid in reject.get(rid, set()):
            found_reject.add((rid, eid))

        if eid in relabel.get(rid, {}):
            found_relabel.add((rid, eid))

expected_reject = {
    (rid, eid)
    for rid, ids in reject.items()
    for eid in ids
}
expected_relabel = {
    (rid, eid)
    for rid, ids in relabel.items()
    for eid in ids
}

if found_reject != expected_reject or found_relabel != expected_relabel:
    print("STOP: target verification failed. No changes saved.")
    print("Missing rejection targets:", sorted(expected_reject - found_reject))
    print("Missing relabel targets:", sorted(expected_relabel - found_relabel))
    raise SystemExit(1)

# Preserve the current file before changing it.
backup = path.with_name("reviewed_annotations_before_final_cleanup.jsonl")

if not backup.exists():
    backup.write_text(
        path.read_text(encoding="utf-8"),
        encoding="utf-8"
    )
    print("Backup created:", backup)
else:
    print("Backup already exists:", backup)

for record in records:
    rid = str(record.get("resume_id"))

    for ent in record.get("review_entities", []):
        eid = ent.get("review_id")

        if eid in reject.get(rid, set()):
            ent["accepted"] = False

        if eid in relabel.get(rid, {}):
            ent["label"] = relabel[rid][eid]

temp = path.with_name(path.name + ".tmp")

with temp.open("w", encoding="utf-8", newline="\n") as f:
    for record in records:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

# Verify the output before replacing the original.
with temp.open(encoding="utf-8") as f:
    verified = [json.loads(line) for line in f if line.strip()]

if len(verified) != len(records):
    temp.unlink(missing_ok=True)
    raise SystemExit("Verification failed; original file preserved.")

temp.replace(path)

print("\nCleanup completed.")
print("Rejected:", len(expected_reject))
print("Relabelled:", len(expected_relabel))
print("Resume records preserved:", len(records))
