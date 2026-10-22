import json
from pathlib import Path
import spacy

path = Path("data/annotations/reviewed_annotations.jsonl")
backup = Path("data/annotations/reviewed_annotations_before_comma_normalization.jsonl")

if not path.exists():
    raise FileNotFoundError(f"Could not find {path}")

if backup.exists():
    raise FileExistsError(
        f"Backup already exists: {backup}\n"
        "No files were changed. Choose a different backup filename if needed."
    )

original = path.read_text(encoding="utf-8")
backup.write_text(original, encoding="utf-8")

rows = [
    json.loads(line)
    for line in original.splitlines()
    if line.strip()
]

changed = []

for row in rows:
    text = row.get("text", "")
    if ",," in text:
        count = text.count(",,")
        row["text"] = text.replace(",,", ", ")
        changed.append((row.get("resume_id"), count))

updated = "\n".join(
    json.dumps(row, ensure_ascii=False)
    for row in rows
) + "\n"

path.write_text(updated, encoding="utf-8")

print("Formatting repair completed.")
print(f"Backup saved to: {backup}")
print(f"Records repaired: {len(changed)}")

for resume_id, count in changed:
    print(f"  Resume {resume_id}: normalized {count} repeated-comma separators")

# Check whether the Data Analysis boundaries now align in Resume 19.
row19 = next(
    (row for row in rows if str(row.get("resume_id")) == "19"),
    None
)

if row19:
    doc = spacy.blank("en")(row19["text"])
    print("\nResume 19 tokenization after repair:")
    for token in doc:
        if token.idx < 480 and token.idx + len(token.text) > 435:
            print(repr(token.text), token.idx, token.idx + len(token.text))
