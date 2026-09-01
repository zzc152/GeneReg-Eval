"""Second-pass audit for Phase 3 abstract relation reviews.

The verifier is a sidecar: it never mutates the first-pass extraction and its
accept_supported flag can be used as an additional precision gate.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from urllib import error, request


ROOT = Path("/workspace/zzc/GeneReg-Eval")

LEGACY_TEMPLATE = """You are the independent second-pass auditor for a biomedical abstract relation review.
Your task is to determine whether the FIRST-PASS REVIEW is correct. Re-read the title and abstract yourself. The first-pass conclusion and span are fallible claims, not evidence.

The source of record is only the supplied Title and Abstract. Gold candidate and mention lists identify the requested edge, but must not be treated as proof.

Decision policy:
1. ABSTRACT_SUPPORTED requires the specific Gold TF→Target edge, compatible entity identity/species, and functional transcriptional evidence. Activation/Repression additionally require that direction. Binding, motif, correlation, PPI, protein trafficking, or abundance change without a transcription/promoter consequence are not sufficient.
2. Preserve arrow direction. A sentence that Target activates TF does not support TF activates Target.
3. A broad gene/protein term (for example, "PEPCK", "MDR1", or "P-glycoprotein") does not establish a specific Gold gene merely because it is present in an alias list. Require a unique source-level identity cue. Cross-species orthologues cannot support the Gold edge.
4. Do not mistake a separate regulator's opposite action for a conflict. Functional promoter/transcription evidence for the named TF remains valid. A named source-defined splice isoform can support its Gold parent when the source explicitly identifies that relationship.
5. An explicit source statement that TF regulates Target transcription, including a statement about prior work in the abstract background, is evidence. Do not require direct DNA binding if functional causal evidence is explicit. Conversely, do not infer transcriptional regulation from a downstream protein/expression change alone.
6. Perturbation evidence can support the observed direction: TF loss followed by Target decrease supports activation, and TF loss followed by Target increase supports repression. General biological roles or indirect mechanisms do not negate that observed relation.

Instructional few-shot examples (synthetic; not records to audit):

Example A — reject direction reversal
Gold: TF_A→GENE_B Activation. Abstract: "Activation of GENE_B was required for upregulation of TF_A." First pass: SUPPORTED.
Output: {{"layer1_judgment":"INCORRECT","expected_support_status":"ABSTRACT_INSUFFICIENT","accept_supported":false,"error_types":["EDGE_DIRECTION_REVERSED"],"review_note":"The source supports GENE_B→TF_A, not the Gold edge."}}

Example B — reject unresolved target identity
Gold: TF_A→GENE_B2 Repression. Abstract: "TF_A inhibited PEPCK promoter activity." First pass maps PEPCK to GENE_B2 and says SUPPORTED.
Output: {{"layer1_judgment":"INCORRECT","expected_support_status":"ABSTRACT_INSUFFICIENT","accept_supported":false,"error_types":["TARGET_IDENTITY_UNRESOLVED"],"review_note":"The bare source term does not identify the specific Gold gene."}}

Example C — reject non-transcriptional change
Gold: TF_A→GENE_B Repression. Abstract: "TF_A overexpression lowered GENE_B protein abundance." First pass: SUPPORTED.
Output: {{"layer1_judgment":"INCORRECT","expected_support_status":"ABSTRACT_PARTIAL","accept_supported":false,"error_types":["NOT_TRANSCRIPTIONAL"],"review_note":"A protein-abundance change alone is not transcriptional repression."}}

Example D — confirm a valid relation despite another regulator
Gold: TF_A→GENE_B Activation. Abstract: "TF_A enhanced GENE_B promoter activity; TF_C inhibited the same promoter." First pass: SUPPORTED with the first clause as span.
Output: {{"layer1_judgment":"CORRECT","expected_support_status":"ABSTRACT_SUPPORTED","accept_supported":true,"error_types":[],"review_note":"TF_A functional promoter activation is explicit; TF_C is a separate regulator."}}

Example E — confirm explicit transcription wording
Gold: TF_A→GENE_B Unknown. Abstract: "Prior studies showed that TF_A regulates GENE_B transcription." First pass: SUPPORTED.
Output: {{"layer1_judgment":"CORRECT","expected_support_status":"ABSTRACT_SUPPORTED","accept_supported":true,"error_types":[],"review_note":"The abstract explicitly states the functional transcriptional relation; direction is not required for Unknown."}}

Return ONLY legal JSON matching exactly:
{{"layer1_judgment":"CORRECT | INCORRECT","expected_support_status":"ABSTRACT_SUPPORTED | ABSTRACT_PARTIAL | ABSTRACT_INSUFFICIENT","accept_supported":true,"error_types":["zero or more of EDGE_DIRECTION_REVERSED, TARGET_IDENTITY_UNRESOLVED, SPECIES_ORTHOLOG_MISMATCH, NOT_TRANSCRIPTIONAL, BINDING_ONLY, PPI_OR_POST_TRANSLATIONAL, OTHER_REGULATOR_CONFLATION, FUNCTIONAL_EVIDENCE_UNDERCALLED, ISOFORM_IDENTITY, OTHER"],"review_note":"one concise sentence"}}

Gold species: {species}
Gold TF: {tf}
Gold Target: {target}
Gold MoR: {mor}
PMID: {pmid}
TF mentions: {tf_mentions}
Target mentions: {target_mentions}

FIRST-PASS REVIEW (untrusted):
{layer1_review}

Title: {title}
Abstract: {abstract}"""

TEMPLATE = """You are the independent second-pass auditor for a biomedical abstract relation review.
Decide whether the FIRST-PASS REVIEW is logically correct, and independently screen for entity-identity risk. Re-read Title and Abstract yourself: the first-pass status, mentions, and span are untrusted claims, not evidence.

Use only the supplied Title/Abstract as evidence. The Gold candidate and mention lists identify the requested edge but do not prove it.

Audit rules:
1. SUPPORTED requires the specific Gold TF→Target edge, compatible entity identity and species, and functional transcriptional evidence; Activation/Repression also require the stated direction.
2. Do not reverse the edge. Do not turn a broad term such as PEPCK, MDR1, or P-glycoprotein into a specific gene without a unique source-level identity cue. Do not use a cross-species orthologue.
3. Binding/motif/correlation/PPI/trafficking or an abundance change alone is insufficient. Explicit transcription/promoter evidence, an explicit source statement about prior work, a named functional mechanism component, or an informative perturbation can support the relation.
4. A different regulator's opposite action is not a conflict. A named source-defined splice isoform can support its Gold parent entity.
5. TF binding a Target protein or changing that protein's transcriptional activity is not regulation of the Target gene. Promoter occupancy linked only to a broad phenotype, without an explicit transcription/expression consequence for that specific Target, remains binding-only.
6. Independently set `entity_identity_risk` true whenever a source mention may not uniquely identify the Gold TF or Target, even if the first-pass conclusion is otherwise plausible. This includes a family/group term, complex or multimer, generic protein name, ambiguous abbreviation, broad historical name, unqualified protein-versus-gene usage, or an unspecified isoform/fusion. Treat slash or paired surface forms such as `A/B`, `A and/or B`, and `A or B` as potentially multiple entities: do not assume that one member is uniquely the Gold entity. Set risk true unless the original wording itself resolves the identity, for example by an explicit definition/apposition or a singular predicate that clearly treats the paired expression as one named entity (such as `A/B is ...`). This is a review-queue flag, not an automatic rejection: keep decision PASS when no definite logical error is established, but explain the ambiguity concisely in `entity_risk_note`.

Synthetic few-shot audits:
Example A: Gold TF_A→GENE_B Activation. Source says "GENE_B activation was required for TF_A upregulation." First pass says SUPPORTED. Output: {{"decision":"REJECT","entity_identity_risk":false,"entity_risk_note":""}}
Example B: Gold TF_A→GENE_B2 Repression. Source says "TF_A inhibited PEPCK promoter activity." First pass maps PEPCK to GENE_B2 and says SUPPORTED. Output: {{"decision":"REJECT","entity_identity_risk":true,"entity_risk_note":"PEPCK does not uniquely identify the Gold target."}}
Example C: Gold TF_A→GENE_B Repression. Source says "TF_A overexpression lowered GENE_B protein." First pass says SUPPORTED. Output: {{"decision":"REJECT","entity_identity_risk":false,"entity_risk_note":""}}
Example D: Gold TF_A→GENE_B Activation. Source says "TF_A enhanced GENE_B promoter activity; TF_C inhibited the same promoter." First pass says SUPPORTED with the TF_A clause. Output: {{"decision":"PASS","entity_identity_risk":false,"entity_risk_note":""}}
Example E: Gold TF_A→GENE_B Unknown. Source says "Prior studies showed TF_A regulates GENE_B transcription." First pass says SUPPORTED. Output: {{"decision":"PASS","entity_identity_risk":false,"entity_risk_note":""}}
Example F: Gold AHR→BRCA1 Unknown. Source says "AhR binds BRCA1 and affects BRCA1 transcription activity." First pass says SUPPORTED. Output: {{"decision":"REJECT","entity_identity_risk":false,"entity_risk_note":""}}
Example G: Gold AHR→IL6 Unknown. Source says "AHR occupancy at the IL6 promoter is required for inflammatory signalling." First pass says SUPPORTED. Output: {{"decision":"REJECT","entity_identity_risk":false,"entity_risk_note":""}}
Example H: Gold NFKB1→GENE_B Activation. Source says "NF-kappaB activates GENE_B transcription." First pass says SUPPORTED. The source does not identify the NFKB1 subunit. Output: {{"decision":"PASS","entity_identity_risk":true,"entity_risk_note":"NF-kappaB is not uniquely anchored to the Gold NFKB1 subunit."}}

Example I: Gold TF_A to GENE_B Activation. Source says "TF_A/TF_C activates GENE_B transcription." First pass says SUPPORTED for TF_A. The source neither defines `TF_A/TF_C` as one entity nor uses source wording that uniquely assigns the action to TF_A. Output: {{"decision":"PASS","entity_identity_risk":true,"entity_risk_note":"The slash expression does not uniquely identify TF_A rather than TF_C or their pair."}}

Return ONLY this exact JSON object, with no other keys or prose. `entity_risk_note` must be empty when entity_identity_risk is false:
{{"decision":"PASS | REJECT","entity_identity_risk":false,"entity_risk_note":""}}

Gold species: {species}
Gold TF: {tf}
Gold Target: {target}
Gold MoR: {mor}
PMID: {pmid}
TF mentions: {tf_mentions}
Target mentions: {target_mentions}

FIRST-PASS REVIEW (untrusted):
{layer1_review}

Title: {title}
Abstract: {abstract}"""


def parse_json(content: str) -> dict:
    text = content.strip()
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


def call_api(url: str, body: dict, headers: dict[str, str]) -> dict:
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    endpoint = url.rstrip("/") + "/v1/chat/completions"
    try:
        with request.urlopen(request.Request(endpoint, data=payload, headers=headers), timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        if exc.code == 400 and "chat_template_kwargs" in message and "support" in message.lower():
            body = dict(body); body.pop("chat_template_kwargs", None)
            payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
            with request.urlopen(request.Request(endpoint, data=payload, headers=headers), timeout=180) as response:
                return json.loads(response.read().decode("utf-8"))
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="First-pass model JSONL")
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", default="qwen35-fp8")
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--api-key", default=os.getenv("VLLM_API_KEY"))
    parser.add_argument("--max-tokens", type=int, default=256)
    args = parser.parse_args()
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise SystemExit(f"Refusing to overwrite existing output: {output}")
    aliases = {}
    for line in (ROOT / "data/intermediate/gene_alias_mapping_v1_20260826.jsonl").open(encoding="utf-8"):
        entity = json.loads(line)
        aliases[(entity["species"], entity.get("approved_symbol", entity.get("mgi_symbol")))] = entity["mention_candidates"]
    # First-pass records intentionally keep only the candidate metadata and
    # review.  Rejoin the immutable PubMed cache here so the verifier always
    # audits the actual title/abstract rather than trusting first-pass fields.
    articles = {
        str(article["pmid"]): article
        for raw in (ROOT / "data/intermediate/trrust_pubmed_articles_v1_20260826.jsonl").open(encoding="utf-8")
        if raw.strip()
        for article in (json.loads(raw),)
    }
    headers = {"Content-Type": "application/json"}
    if args.api_key:
        headers["Authorization"] = "Bearer " + args.api_key
    with output.open("x", encoding="utf-8") as sink:
        for line in (ROOT / args.input).open(encoding="utf-8"):
            if not line.strip():
                continue
            first = json.loads(line)
            item = first["input"]
            species = item.get("species") or item.get("stratum", {}).get("species")
            article = articles.get(str(item["pmid"]))
            if article is None:
                raise KeyError(f"PMID not found in article cache: {item['pmid']}")
            prompt = TEMPLATE.format(
                species=species, tf=item["tf_mention"], target=item["object_mention"], mor=item["relation"], pmid=item["pmid"],
                tf_mentions=json.dumps(aliases.get((species, item["tf_mention"]), [item["tf_mention"]]), ensure_ascii=False),
                target_mentions=json.dumps(aliases.get((species, item["object_mention"]), [item["object_mention"]]), ensure_ascii=False),
                layer1_review=json.dumps(first["review"], ensure_ascii=False),
                title=article.get("title") or "", abstract=article.get("abstract") or "",
            )
            body = {"model": args.model, "messages": [{"role": "user", "content": prompt}], "response_format": {"type": "json_object"}, "temperature": 0.0, "max_tokens": args.max_tokens, "chat_template_kwargs": {"enable_thinking": False}}
            try:
                response = call_api(args.base_url, body, headers)
                raw_output = response["choices"][0]["message"].get("content") or ""
                verification = parse_json(raw_output)
                error_text = None
            except Exception as exc:
                raw_output, verification, error_text = "", None, f"{type(exc).__name__}: {exc}"
            sink.write(json.dumps({"record_key": first["record_key"], "verifier_prompt_version": "phase3_second_pass_verifier_v4_entity_risk_slash_pair", "input": item, "layer1_review": first["review"], "verification": verification, "raw_output": raw_output, "error": error_text}, ensure_ascii=False) + "\n")
            sink.flush()
            time.sleep(0.1)


if __name__ == "__main__":
    main()
