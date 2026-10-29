import spacy
from spacy.tokenizer import Tokenizer
from spacy.util import compile_infix_regex


@spacy.registry.tokenizers("resume_fairness_tokenizer.v1")
def create_resume_tokenizer():
    def create_tokenizer(nlp):
        infixes = list(nlp.Defaults.infixes)
        infixes.extend([
            r"(?<=[^\s(])(?=\()",
            r"(?<=\()(?=[A-Za-z0-9])",
            r"(?<=\))(?=[A-Za-z0-9])",
        ])

        return Tokenizer(
            nlp.vocab,
            rules=nlp.Defaults.tokenizer_exceptions,
            prefix_search=compile_infix_regex(nlp.Defaults.prefixes).search,
            suffix_search=compile_infix_regex(nlp.Defaults.suffixes).search,
            infix_finditer=compile_infix_regex(infixes).finditer,
            token_match=nlp.Defaults.token_match,
            url_match=nlp.Defaults.url_match,
        )

    return create_tokenizer
