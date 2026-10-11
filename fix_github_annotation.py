import json
import shutil
from pathlib import Path

file_path = Path("data/annotations/reviewed_annotations.jsonl")
backup_path = Path(
    "data/annotations/reviewed_annotations.before_github_fix.bak"
)

if not file_path.exists():
    raise FileNotFoundError(f"File not found: {file_path}")

# Keep a backup before making changes.
shutil.copy2(file_path, backup_path)

updated_records = []
changes = 0

with file_path.open("r", encoding="utf-8") as file:
    for line in file:
        if not line.strip():
            continue

        record = json.loads(line)

        # Correct only the specific GitHub URL annotation.
        if str(record.get("resume_id")) == "1":
            for entity in record.get("review_entities", []):
                is_target = (
                    entity.get("text", "").strip().lower() == "github"
                    and entity.get("start") == 118
                    and entity.get("end") == 124
                )

                if is_target:
                    entity["accepted"] = False
                    entity["review_action"] = "REJECTED"
                    changes += 1

        updated_records.append(
            json.dumps(record, ensure_ascii=False)
        )

if changes == 0:
    print("No matching annotation was found. No changes were saved.")
else:
    with file_path.open("w", encoding="utf-8") as file:
        file.write("\n".join(updated_records) + "\n")

    print(f"Successfully rejected {changes} annotation(s).")
    print(f"Backup saved at: {backup_path}")