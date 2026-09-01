"""Deterministic structural and source-anchor validation for abstract reviews.

This validator intentionally does not make semantic or biological judgments.
It preserves model output verbatim and adds only a VALID/REJECT route plus
machine-checkable error messages.
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path("/workspace/zzc/GeneReg-Eval")
STATUSES = {"ABSTRACT_SUPPORTED", "ABSTRACT_PARTIAL", "ABSTRACT_INSUFFICIENT"}
CONDITION_KEYS = ("species", "biological_system", "biological_state", "treatment_or_stimulus", "time", "other_condition")


def source_contains(value: str, title: str, abstract: str) -> bool:
    return value in title or value in abstract


def normalize_anchor(value: str) -> str:
    """Conservative fuzzy surface matching for source-anchored mentions only.

    This deliberately does not expand aliases or infer family/complex identity.
    It only tolerates case, Unicode, whitespace, and hyphen-like typography.
    """
    text = unicodedata.normalize("NFKC", value).casefold()
    text = re.sub(r"[\s\-‐‑‒–—―]+", "", text)
    return text


def span_contains_anchor(span: str, mention: str) -> bool:
    return bool(normalize_anchor(mention)) and normalize_anchor(mention) in normalize_anchor(span)


def validate_record(row: Any, articles: dict[str, dict[str, Any]]) -> list[str]:
    if not isinstance(row, dict):
        return ["R00: record must be an object"]
    review = row.get("review")
    if not isinstance(review, dict):
        return ["R01: review must be an object"]
    errors: list[str] = []
    required = ("support_status", "extracted_tf_mention", "extracted_target_mention", "evidence_span", "condition", "review_flag", "review_note")
    for key in required:
        if key not in review:
            errors.append(f"R02: missing review.{key}")
    if errors:
        return errors
    status = review["support_status"]
    if status not in STATUSES:
        errors.append("R03: invalid support_status")
    for key in ("extracted_tf_mention", "extracted_target_mention", "evidence_span"):
        if review[key] is not None and not isinstance(review[key], str):
            errors.append(f"R04: review.{key} must be string or null")
    if not isinstance(review["review_flag"], bool):
        errors.append("R05: review.review_flag must be boolean")
    if not isinstance(review["review_note"], str):
        errors.append("R06: review.review_note must be a string")
    condition = review["condition"]
    if not isinstance(condition, dict):
        errors.append("R07: review.condition must be an object")
    else:
        if set(condition) != set(CONDITION_KEYS):
            errors.append("R08: review.condition must contain exactly six required keys")
        for key in CONDITION_KEYS:
            value = condition.get(key)
            if value is not None and not isinstance(value, str):
                errors.append(f"R09: condition.{key} must be string or null")
    if errors:
        return errors
    title, abstract = row.get("title"), row.get("abstract")
    if not isinstance(title, str) or not isinstance(abstract, str):
        pmid = row.get("input", {}).get("pmid") if isinstance(row.get("input"), dict) else None
        article = articles.get(str(pmid)) if pmid is not None else None
        if isinstance(article, dict):
            title, abstract = article.get("title"), article.get("abstract")
    if not isinstance(title, str) or not isinstance(abstract, str):
        return ["R10: title and abstract must be strings for source anchoring"]
    for key in ("extracted_tf_mention", "extracted_target_mention"):
        value = review[key]
        if isinstance(value, str) and value and not source_contains(value, title, abstract):
            errors.append(f"R11: review.{key} is not a continuous title/abstract substring")
    for key, value in condition.items():
        if isinstance(value, str) and value and not source_contains(value, title, abstract):
            errors.append(f"R12: condition.{key} is not a continuous title/abstract substring")
    span = review["evidence_span"]
    if status in {"ABSTRACT_PARTIAL", "ABSTRACT_INSUFFICIENT"} and span is not None:
        errors.append("R13: non-supported status requires null evidence_span")
    if status == "ABSTRACT_SUPPORTED":
        if not isinstance(span, str) or not span:
            errors.append("R14: supported status requires a non-empty evidence_span")
        elif not source_contains(span, title, abstract):
            errors.append("R15: evidence_span is not a continuous title/abstract substring")
        for key in ("extracted_tf_mention", "extracted_target_mention"):
            value = review[key]
            if not isinstance(value, str) or not value:
                errors.append(f"R16: supported status requires non-empty {key}")
            elif isinstance(span, str) and span and not span_contains_anchor(span, value):
                errors.append(f"R17: supported evidence_span must contain review.{key} (case/hyphen/whitespace-normalized match)")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--articles", default="data/intermediate/trrust_pubmed_articles_v1_20260826.jsonl")
    args = parser.parse_args()
    input_path, output_path, article_path = ROOT / args.input, ROOT / args.output, ROOT / args.articles
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        raise SystemExit(f"Refusing to overwrite existing output: {output_path}")
    articles: dict[str, dict[str, Any]] = {}
    with article_path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                article = json.loads(line)
                if article.get("pmid") is not None:
                    articles[str(article["pmid"])] = article
    routes: Counter[str] = Counter()
    with input_path.open(encoding="utf-8") as source, output_path.open("x", encoding="utf-8") as sink:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                errors = validate_record(row, articles)
            except json.JSONDecodeError as error:
                row, errors = {"raw_line": line.rstrip("\n")}, [f"R99: invalid input JSON at line {line_number}: {error.msg}"]
            route = "VALID" if not errors else "REJECT"
            routes[route] += 1
            row["validation_route"] = route
            row["validation_errors"] = errors
            sink.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({"input": str(input_path), "output": str(output_path), "routes": routes}, ensure_ascii=False))


if __name__ == "__main__":
    main()
