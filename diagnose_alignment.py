import json
import spacy
from pathlib import Path

path = Path("data/annotations/reviewed_annotations.jsonl")
nlp = spacy.blank("en")
errors = 0
checked = 0

with path.open(encoding="utf-8") as f:
    for line_no, line in enumerate(f, 1):
        if not line.strip():
            continue
        rec = json.loads(line)
        text = rec.get("text", "")
        doc = nlp.make_doc(text)
        rid = rec.get("resume_id", f"line {line_no}")

        for ent in rec.get("review_entities", []):
            if ent.get("accepted") is not True:
                continue

            checked += 1
            start, end = ent.get("start"), ent.get("end")
            phrase = ent.get("text", "")

            if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end > len(text) or start >= end:
                errors += 1
                print(f"\nINVALID OFFSETS | Resume {rid} | {phrase!r} | {start}:{end}")
                continue

            actual = text[start:end]
            span = doc.char_span(start, end, alignment_mode="strict")

            if actual != phrase or span is None:
                errors += 1
                print(f"\nResume {rid} | Entity: {phrase!r} | Label: {ent.get('label')}")
                print(f"Offsets: {start}:{end} | Actual text: {actual!r}")
                print(f"Text matches: {actual == phrase} | Token aligned: {span is not None}")
                print(f"Context: {text[max(0, start-45):min(len(text), end+45)]!r}")
                for tok in doc:
                    if tok.idx < end + 10 and tok.idx + len(tok.text) > start - 10:
                        print(f"  Token {tok.text!r}: {tok.idx}:{tok.idx + len(tok.text)}")

print(f"\nChecked {checked} accepted annotations; found {errors} errors.")
