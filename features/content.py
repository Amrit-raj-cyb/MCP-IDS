"""Content features: what the *tool metadata* says, after neutralization.

Source: every tool advertised in ``tools/list`` responses, i.e. its
``description`` and every ``description`` inside its input schema (parameter
descriptions). That's exactly the text a model reads when it decides how to
use tools.

All text has already been through ``neutralize()`` (features/session.py),
so the lab marker and canary token are gone. The lexicons below are *general*
signals of text that directs the reader (imperatives, addressing the model,
secrecy, markup), not copies of our payload sentences. They were still
written by people who knew the payloads, which is a bias the holdout
experiment and docs/ml.md discuss.
"""

from __future__ import annotations

import re

from common.simulation import schema_texts
from features.base import FeatureSpec, stats
from features.session import Session

SRC = "tools/list responses: tool descriptions + input-schema descriptions"

DIRECTIVE_WORDS = ("must", "always", "never", "do not", "don't", "before", "first", "ignore", "instead",
                   "required", "requirement", "important", "ensure", "make sure", "should", "please")
MODEL_ADDRESS = ("assistant", " ai ", "you ", "your ", "the user", "instructions", "conversation",
                 "any request", "each request", "reply", "answer")
SECRECY = ("do not mention", "don't mention", "do not tell", "don't tell", "without telling",
           "hide", "secret", "silently")
_WORD = re.compile(r"[A-Za-z']+")
_TAG = re.compile(r"</?[A-Za-z][A-Za-z0-9_-]*>")
_SENT = re.compile(r"[.!?](\s|$)")

FEATURES = [
    FeatureSpec("n_tools_advertised", "content", "int", "Tools listed by all servers", SRC),
    FeatureSpec("desc_len_mean", "content", "float", "Mean tool-description length (chars)", SRC),
    FeatureSpec("desc_len_std", "content", "float", "Std. dev. of description length", SRC),
    FeatureSpec("desc_len_max", "content", "float", "Longest tool description", SRC),
    FeatureSpec("desc_words_max", "content", "float", "Most words in one description", SRC),
    FeatureSpec("desc_words_total", "content", "float", "Words across all descriptions", SRC),
    FeatureSpec("desc_sentences_max", "content", "float", "Most sentences in one description", SRC),
    FeatureSpec("param_desc_len_mean", "content", "float", "Mean parameter-description length", SRC),
    FeatureSpec("param_desc_len_max", "content", "float", "Longest parameter description", SRC),
    FeatureSpec("metadata_text_len_max", "content", "float", "Longest single metadata text", SRC),
    FeatureSpec("directive_word_count", "content", "int",
                "Directive/imperative words (must, always, before, ignore, ...) in all metadata", SRC),
    FeatureSpec("model_address_count", "content", "int",
                "Phrases addressing the model/agent (assistant, you, your, reply, ...)", SRC),
    FeatureSpec("secrecy_phrase_count", "content", "int", "Secrecy phrases (do not mention, hide, ...)", SRC),
    FeatureSpec("second_person_count", "content", "int", "Occurrences of 'you'/'your'", SRC),
    FeatureSpec("uppercase_word_count", "content", "int", "ALL-CAPS words of 3+ letters", SRC),
    FeatureSpec("markup_tag_count", "content", "int", "XML/HTML-like tags such as <important>", SRC),
    FeatureSpec("tool_name_mentions", "content", "int",
                "Mentions of advertised tool names inside metadata text", SRC),
    FeatureSpec("cross_server_tool_reference_count", "content", "int",
                "Tool descriptions that refer to a tool advertised by another server", SRC),
    FeatureSpec("max_directive_density", "content", "float",
                "Highest directive words per 100 words in any single text", SRC),
    FeatureSpec("max_desc_param_ratio", "content", "float",
                "Highest description length / (1 + number of parameters) over tools", SRC),
]


def _count(text: str, phrases: tuple[str, ...]) -> int:
    t = f" {text.lower()} "
    return sum(t.count(p) for p in phrases)


def extract(s: Session) -> dict[str, float]:
    tools = [t for e in s.events if e.method == "tools/list" and e.kind == "response"
             for t in ((e.body.get("result") or {}).get("tools") or [])]
    descs = [t.get("description") or "" for t in tools]
    params = [d for t in tools for d in schema_texts(t.get("inputSchema"))]
    texts = descs + params
    names = [t.get("name", "") for t in tools if t.get("name")]
    listings = [(e.server_id, t) for e in s.events if e.method == "tools/list" and e.kind == "response"
                for t in ((e.body.get("result") or {}).get("tools") or []) if t.get("name")]
    owners: dict[str, set[str]] = {}
    for server, tool in listings:
        owners.setdefault(str(tool["name"]), set()).add(server)
    cross_references = 0
    for server, tool in listings:
        description = str(tool.get("description") or "").lower()
        for other_name, other_servers in owners.items():
            if not any(owner != server for owner in other_servers):
                continue
            namespaced = [f"{owner}__{other_name}".lower() for owner in other_servers if owner != server]
            explicit_reference = any(token in description for token in namespaced)
            unambiguous_name = (other_name != str(tool["name"]) and len(other_servers) == 1
                                and bool(re.search(rf"\b{re.escape(other_name.lower())}\b", description)))
            if explicit_reference or unambiguous_name:
                cross_references += 1
    blob = "\n".join(texts)
    words = [_WORD.findall(d) for d in descs]

    densities = []
    for t in texts:
        n = len(_WORD.findall(t))
        if n:
            densities.append(100.0 * _count(t, DIRECTIVE_WORDS) / n)

    ratios = []
    for t in tools:
        n_params = len(((t.get("inputSchema") or {}).get("properties") or {}))
        ratios.append(len(t.get("description") or "") / (1 + n_params))

    d_mean, d_std, _, d_max = stats([len(d) for d in descs])
    p_mean, _, _, p_max = stats([len(p) for p in params])
    return {
        "n_tools_advertised": len(tools),
        "desc_len_mean": d_mean, "desc_len_std": d_std, "desc_len_max": d_max,
        "desc_words_max": float(max((len(w) for w in words), default=0)),
        "desc_words_total": float(sum(len(w) for w in words)),
        "desc_sentences_max": float(max((len(_SENT.findall(d)) for d in descs), default=0)),
        "param_desc_len_mean": p_mean, "param_desc_len_max": p_max,
        "metadata_text_len_max": float(max((len(t) for t in texts), default=0)),
        "directive_word_count": _count(blob, DIRECTIVE_WORDS),
        "model_address_count": _count(blob, MODEL_ADDRESS),
        "secrecy_phrase_count": _count(blob, SECRECY),
        "second_person_count": len(re.findall(r"\byou(r)?\b", blob, re.IGNORECASE)),
        "uppercase_word_count": len(re.findall(r"\b[A-Z]{3,}\b", blob)),
        "markup_tag_count": len(_TAG.findall(blob)),
        "tool_name_mentions": sum(blob.count(n) for n in names),
        "cross_server_tool_reference_count": cross_references,
        "max_directive_density": max(densities, default=0.0),
        "max_desc_param_ratio": max(ratios, default=0.0),
    }
