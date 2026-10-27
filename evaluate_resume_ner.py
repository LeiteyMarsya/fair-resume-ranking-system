from pathlib import Path
import json
import spacy
from spacy.scorer import Scorer
from spacy.training import Example
from spacy.util import compile_infix_regex
from spacy.tokens import DocBin

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "models" / "resume_ner" / "model-best"
TEST_PATH = BASE_DIR / "data" / "annotations" / "test.spacy"
OUTPUT_PATH = BASE_DIR / "data" / "annotations" / "test_metrics_tokenizer_fixed.json"

def main():
    nlp = spacy.load(MODEL_PATH)

    infixes = list(nlp.Defaults.infixes)
    infixes.extend([
        r"(?<=[^\s(])(?=\()",
        r"(?<=\()(?=[A-Za-z0-9])",
        r"(?<=\))(?=[A-Za-z0-9])",
    ])
    nlp.tokenizer.infix_finditer = compile_infix_regex(infixes).finditer

    doc_bin = DocBin().from_disk(TEST_PATH)
    gold_docs = list(doc_bin.get_docs(nlp.vocab))
    examples = []

    for gold in gold_docs:
        predicted = nlp(gold.text)
        examples.append(Example(predicted, gold))

    scores = Scorer().score(examples)

    result = {
        key: value
        for key, value in scores.items()
        if key.startswith("ents_") or key.startswith("ents_per_type")
    }
    result["evaluation_documents"] = len(gold_docs)
    result["model_path"] = str(MODEL_PATH)
    result["tokenizer"] = "resume tokenizer with parenthesis splitting"

    OUTPUT_PATH.write_text(
        json.dumps(result, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(result, indent=2))
    print(f"\nMetrics saved to: {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
