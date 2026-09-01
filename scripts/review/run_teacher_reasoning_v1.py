"""Generate bounded teacher reasoning records from two-layer-admitted samples."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request


ROOT = Path("/workspace/zzc/GeneReg-Eval")
CATALOG_VERSION = "gene_reg_inference_rule_catalog_v1"
RULES = """GRR-001 explicit named TF-to-Target transcriptional relation assertion; GRR-002 TF loss + Target decrease => Activation; GRR-003 TF loss + Target increase => Repression; GRR-004 TF gain + Target increase => Activation; GRR-005 TF gain + Target decrease => Repression; GRR-006 functional Target promoter/reporter result; GRR-007 Target binding/occupancy plus linked functional consequence; GRR-008 functional mutation of TF-linked Target binding site; GRR-009 source-defined TF complex component plus functional Target transcription output; GRR-010 explicit functional TF-to-Target relation with direction unspecified => Unknown. Binding/occupancy, correlation, association, PPI, or target protein function alone are not rules."""
RULE_IDS = [
    "GRR-001_EXPLICIT_TRANSCRIPTIONAL_RELATION_ASSERTION", "GRR-002_TF_LOSS_TARGET_DECREASE_IMPLIES_ACTIVATION",
    "GRR-003_TF_LOSS_TARGET_INCREASE_IMPLIES_REPRESSION", "GRR-004_TF_GAIN_TARGET_INCREASE_IMPLIES_ACTIVATION",
    "GRR-005_TF_GAIN_TARGET_DECREASE_IMPLIES_REPRESSION", "GRR-006_PROMOTER_OR_REPORTER_FUNCTION",
    "GRR-007_BINDING_PLUS_FUNCTIONAL_CONSEQUENCE", "GRR-008_FUNCTIONAL_BINDING_SITE_MUTATION",
    "GRR-009_NAMED_COMPLEX_COMPONENT_WITH_FUNCTIONAL_OUTPUT", "GRR-010_FUNCTIONAL_RELATION_DIRECTION_UNSPECIFIED"
]


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3].rstrip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def call_api(base_url: str, body: dict) -> dict:
    endpoint = base_url.rstrip("/") + "/v1/chat/completions"
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    try:
        with request.urlopen(request.Request(endpoint, data=payload, headers=headers), timeout=240) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        if exc.code == 400 and "chat_template_kwargs" in message and "support" in message.lower():
            body = dict(body)
            body.pop("chat_template_kwargs", None)
            payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
            with request.urlopen(request.Request(endpoint, data=payload, headers=headers), timeout=240) as response:
                return json.loads(response.read().decode("utf-8"))
        raise


def prompt(item: dict, title: str, abstract: str, upstream_span: str) -> str:
    return f"""You are a biomedical evidence teacher. Produce bounded, auditable reasoning for an already admitted abstract-supported relation. Do not write chain-of-thought and do not use outside knowledge.

The prior relation and prior support span are references, not proof. Teacher evidence must be verbatim title/abstract text selected for the observation-to-rule chain; it may differ from the prior support span. Do not invent an experiment when the abstract only makes an explicit authorial claim.

If the source supports the upstream relation, set teacher_assessment to AGREES_UPSTREAM and repeat exactly that relation in final_relation. If it may be wrong, set UPSTREAM_ERROR_SUSPECTED, provide evidence IDs and a concise review reason, set final_relation to null, and never propose a replacement relation.

Rule meanings: {RULES}
Your `rule_id` MUST equal exactly one complete string in this JSON list: {json.dumps(RULE_IDS)}. Abbreviations such as `GRR-001` are invalid.
Primary-rule priority, highest to lowest: GRR-008; GRR-002/GRR-003/GRR-004/GRR-005; GRR-006; GRR-007; GRR-009; GRR-001; GRR-010. If concrete functional evidence supports a more-specific rule, it must be the `primary_rule_application_id`; GRR-001 is a fallback for an explicit authorial/summary assertion only when no more-specific experimental rule is supported. GRR-010 is a fallback only for an Unknown-direction relation.

Output only JSON with exactly these keys:
{{
  "evidence":[{{"evidence_id":"ev1","verbatim_span":"...","role":"functional|mechanistic|context"}}],
  "observations":[{{"observation_id":"obs1","evidence_ids":["ev1"],"observation_type":"EXPLICIT_TRANSCRIPTION_STATEMENT|AUTHORIAL_RELATION_ASSERTION|TF_PERTURBATION_TARGET_CHANGE|PROMOTER_OR_REPORTER_ACTIVITY|BINDING_OR_OCCUPANCY|BINDING_SITE_FUNCTION|TARGET_TRANSCRIPT_OR_EXPRESSION_CHANGE|COMPLEX_COMPONENT_FUNCTION|OTHER_FUNCTIONAL_OBSERVATION","statement":"...","assertion_provenance":null}}],
  "rule_applications":[{{"application_id":"rule1","rule_id":"GRR-...","observation_ids":["obs1"],"conclusion":{{"relation":"Activation|Repression|Unknown","scope_note":"optional literal scope or omit"}}}}],
  "teacher_assessment":{{"status":"AGREES_UPSTREAM|UPSTREAM_ERROR_SUSPECTED","review_reason":null,"challenge_evidence_ids":[]}},
  "final_relation":{{"support_status":"ABSTRACT_SUPPORTED","regulator_mention":"...","relation":"Activation|Repression|Unknown","object_mention":"...","object_kind":"gene|regulatory_element|protein|other","evidence_ids":["ev1"],"rule_application_ids":["rule1"],"primary_rule_application_id":"rule1","relation_condition":{{"species":[],"biological_system":[],"biological_state":[],"treatment_or_stimulus":[],"time":[],"other_condition":[]}}}}
}}

For AUTHORIAL_RELATION_ASSERTION only, assertion_provenance must be CURRENT_STUDY_RESULT, PRIOR_WORK_ASSERTION, or BACKGROUND_ASSERTION. Otherwise it must be null.

Condition answers only: “Under which explicitly stated conditions does this relation hold?” Include a condition entry only when it directly constrains where, when, or under what setting this TF-to-Target relation holds. It is independent of the inference rule. Do not put TF/Target knockdown, overexpression, mutation, or another causal manipulation into condition merely because it was used to establish the relation. Each relation_condition field is an array of zero or more {{"text":"verbatim source substring","evidence_ids":["ev1"]}} entries. All six arrays may be empty.

Upstream relation: {json.dumps(item, ensure_ascii=False)}
Prior support span (reference only): {upstream_span}
Title: {title}
Abstract: {abstract}"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--first", required=True)
    parser.add_argument("--second", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8003")
    parser.add_argument("--model", default="qwen35-fp8")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20260831)
    parser.add_argument("--max-tokens", type=int, default=1024)
    args = parser.parse_args()
    output_dir = ROOT / args.output_dir
    if output_dir.exists():
        raise SystemExit(f"Refusing to overwrite existing output directory: {output_dir}")
    output_dir.mkdir(parents=True)
    first = [json.loads(line) for line in (ROOT / args.first).open(encoding="utf-8") if line.strip()]
    second = {row["record_key"]: row for line in (ROOT / args.second).open(encoding="utf-8") if line.strip() for row in (json.loads(line),)}
    admitted = [row for row in first if row.get("validation_route") == "VALID" and row.get("review", {}).get("support_status") == "ABSTRACT_SUPPORTED" and second.get(row["record_key"], {}).get("verification_validation_route") == "VALID" and second[row["record_key"]].get("verification", {}).get("decision") == "PASS"]
    if len(admitted) < args.limit:
        raise ValueError(f"only {len(admitted)} admitted records available")
    chosen = random.Random(args.seed).sample(sorted(admitted, key=lambda x: x["record_key"]), args.limit)
    articles = {str(row["pmid"]): row for line in (ROOT / "data/intermediate/trrust_pubmed_articles_v1_20260826.jsonl").open(encoding="utf-8") if line.strip() for row in (json.loads(line),)}
    (output_dir / "input_manifest.jsonl").write_text("".join(json.dumps({"record_key": row["record_key"], "pmid": row["input"]["pmid"]}, ensure_ascii=False) + "\n" for row in chosen), encoding="utf-8")
    records_path, calls_path = output_dir / "teacher_reasoning.jsonl", output_dir / "teacher_calls.jsonl"
    with records_path.open("x", encoding="utf-8") as sink, calls_path.open("x", encoding="utf-8") as calls:
        for row in chosen:
            item, review = row["input"], row["review"]
            article = articles[str(item["pmid"])]
            title, abstract = article.get("title") or "", article.get("abstract") or ""
            upstream = {"regulator_mention": review["extracted_tf_mention"], "relation": item["relation"], "object_mention": review["extracted_target_mention"], "object_kind": "gene"}
            try:
                response = call_api(args.base_url, {"model": args.model, "messages": [{"role": "system", "content": "Return JSON only."}, {"role": "user", "content": prompt(upstream, title, abstract, review["evidence_span"])}], "response_format": {"type": "json_object"}, "temperature": 0.0, "max_tokens": args.max_tokens, "chat_template_kwargs": {"enable_thinking": False}})
                raw = response["choices"][0]["message"].get("content") or ""
                generated, error_text = parse_json(raw), None
            except Exception as exc:
                raw, generated, error_text = "", None, f"{type(exc).__name__}: {exc}"
            calls.write(json.dumps({"record_key": row["record_key"], "raw_output": raw, "error": error_text}, ensure_ascii=False) + "\n")
            calls.flush()
            if generated is None:
                continue
            record = {"schema_version": "gene_reg_teacher_reasoning_v1", "reasoning_id": "grtr-v1:" + row["record_key"], "source": {"source_record_key": row["record_key"], "pmid": str(item["pmid"]), "species": item["species"], "title_sha256": digest(title), "abstract_sha256": digest(abstract), "upstream_admission": {"first_pass_status": review["support_status"], "first_validator_route": row["validation_route"], "second_pass_decision": second[row["record_key"]]["verification"]["decision"], "second_validator_route": second[row["record_key"]]["verification_validation_route"]}, "upstream_relation": upstream, "upstream_support_span": review["evidence_span"]}, "inference_rule_catalog_version": CATALOG_VERSION, **generated, "teacher_metadata": {"model_id": args.model, "prompt_version": "teacher_reasoning_v1_smoke", "generated_at_utc": datetime.now(timezone.utc).isoformat()}}
            sink.write(json.dumps(record, ensure_ascii=False) + "\n")
            sink.flush()
            time.sleep(0.1)


if __name__ == "__main__":
    main()
