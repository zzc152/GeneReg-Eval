import argparse,csv,json,os,time
from pathlib import Path
from urllib import request
ROOT=Path("/workspace/zzc/GeneReg-Eval")
TEMPLATE="""You are a biomedical literature evidence reviewer. Judge only whether the PubMed abstract independently supports the given curated TF to Target transcriptional relation. Output only valid JSON with support_status (ABSTRACT_SUPPORTED, ABSTRACT_PARTIAL, ABSTRACT_INSUFFICIENT), extracted_tf_mention (a continuous verbatim title/abstract substring or null), extracted_target_mention (a continuous verbatim title/abstract substring or null), evidence_span (one concise, continuous verbatim supporting span or null), condition (an object with species, biological_system, biological_state, treatment_or_stimulus, time, other_condition; every value must be a verbatim substring or null), review_flag, review_note (a string).

Hard output constraints:
1. `evidence_span` must be null when support_status is ABSTRACT_PARTIAL or ABSTRACT_INSUFFICIENT. Only ABSTRACT_SUPPORTED may contain an evidence_span. Choose any one continuous original-text span sufficient to support the conclusion; it need not be the uniquely shortest span, and another valid supporting span may exist. A SUPPORTED span MUST explicitly contain the original-text TF mention and the original-text Target mention used for this decision. Set `extracted_tf_mention` and `extracted_target_mention` to those mentions within the span. Do not rely only on pronouns such as "it", "this factor", or "these genes". If the functional sentence uses an anaphor, extend the span backward only as far as the nearest immediately preceding source sentence needed to include both entity anchors; the final span must still be one continuous verbatim source substring. If no such anchored continuous span exists, do not mark ABSTRACT_SUPPORTED.
2. Binding, ChIP/occupancy, EMSA, correlation, association, pathway co-occurrence, or protein interaction alone are ABSTRACT_PARTIAL, never ABSTRACT_SUPPORTED. This applies even when the curated MoR is Unknown. ABSTRACT_SUPPORTED requires a direct functional regulatory statement; for Activation or Repression it must also establish that direction.
3. Every non-null value in condition must be copied as one continuous, exact substring from Title or Abstract. Do not paraphrase, normalize, infer, or use outside knowledge. If no directly stated relation-level condition satisfies this rule, keep all six condition fields null. The condition object must always contain all six fields.
4. `review_flag` must be the JSON boolean `true` or `false`, never a string. Keep `review_note` to one concise sentence (at most 240 characters).

Phase 3 adjudication rules (apply these before deciding):
5. TRRUST MoR `Unknown` means the curated direction is unspecified; it does NOT conflict with abstract Activation or Repression. For Unknown, mark ABSTRACT_SUPPORTED when the abstract establishes functional TF-to-Target transcriptional regulation, and do not require the abstract to state a direction.
6. Do not treat binding alone as regulation. But do mark ABSTRACT_SUPPORTED when binding is paired with a functional promoter/expression consequence, a TF-specific binding-site mutation changes promoter activity, or a perturbation establishes a Target transcription/expression effect. Do not require a fully direct molecular mechanism beyond such functional evidence. Do not require TF-specific knockdown, knockout, or overexpression: the absence of a TF-specific perturbation alone is never a reason to downgrade an otherwise explicit functional transcription/promoter relation.
7. Explicit cooperative regulation can support the named TF when the abstract identifies it as a component of the regulatory complex and links the complex to Target transcription. Do not require a single-factor perturbation in that case.
8. Protein-protein interaction, post-translational regulation, predicted motif, correlation, or chromatin association without Target transcription/expression consequence is not TF-to-Target transcriptional regulation.
9. Interpret perturbation direction causally (for example TF knockdown causing Target decrease supports TF activation). An upstream stimulus that activates the TF does not invalidate an explicitly stated TF-to-Target relation.
10. Require compatible species and entity identity. Gold species is supplied below. Do not substitute an orthologue, a gene family, or a complex for the supplied entity unless it is explicitly included in the supplied mention mapping. A generic protein or family term shared across species (for example, a generic MDR1/P-glycoprotein mention) does not by itself establish a species-specific Gold entity: when the Gold entity is species-specific, require an explicit title/abstract cue that the mention is from the Gold species. If that cue is absent, do not mark ABSTRACT_SUPPORTED; set review_flag true and briefly state the species/entity ambiguity. If a known TRRUST Activation/Repression is explicitly opposed by aligned, same-species evidence, do not mark SUPPORTED; set review_flag true and state the direction conflict in review_note.
11. Preserve edge direction. Evidence that Target regulates TF does not support TF regulates Target. Identify the grammatical or causal regulator and regulated entity in the cited span; do not reverse an edge merely because both entities occur in the same sentence.
12. Do not resolve a broad historical or protein name to a specific Gold gene unless the title/abstract or reliable mention list makes the identity unique. For example, a bare "PEPCK" mention is not automatically the specific gene PCK2. If the target identity remains unresolved, do not mark ABSTRACT_SUPPORTED; set review_flag true.
13. Distinguish transcriptional regulation from a downstream abundance change. "TF overexpression was accompanied by lower Target protein/expression" alone is insufficient when the abstract does not attribute a transcriptional or promoter consequence to TF. Conversely, an explicit statement that TF regulates or inhibits Target transcription/promoter activity is functional evidence even if it is phrased as a prior finding in the abstract background. A TF explicitly named as a mechanistic mediator or component of that stated Target transcriptional activation/repression is also functional evidence. Do not discard either solely because the mechanism is indirect or not newly measured in the current study.
14. Do not treat a different regulator's opposite action as a conflict. If the abstract says TF activates Target and a separate named regulator represses Target, the TF→Target activation relation can still be ABSTRACT_SUPPORTED. Likewise, a knockout/perturbation-associated Target change supports the observed direction even when the TF has a general biological role that appears opposite; record indirectness in condition or review_note only when it prevents entity/direction resolution.
15. A named splice isoform can support its Gold parent entity when the title/abstract explicitly identifies it as an isoform or splice product of that entity and the span establishes the relation. Output the original isoform string; do not silently normalize it. A differently named homologue, paralogue, or fusion remains non-equivalent unless listed in the supplied mapping.
16. Distinguish a Target gene from its protein's downstream function. Evidence that TF binds the Target protein or alters the Target protein's ability to regulate transcription does not establish TF regulation of Target gene transcription/expression. For example, "AhR binds BRCA1 and affects BRCA1 transcription activity" is not evidence for AHR → BRCA1 gene regulation.
17. Target-promoter occupancy is still binding-only unless the abstract explicitly links TF perturbation/activity to that Target's own transcription or expression. A statement that occupancy at the IL6 promoter is required for a broader inflammatory phenotype is not by itself evidence for AHR → IL6 regulation.

Provided TF/Target mention lists are the only allowed mapping evidence, except for a named splice isoform explicitly identified in the source as a product of the Gold entity under rule 15. Use them to align an original-text mention to the Gold entity, but always output the original-text mention, never a substituted TRRUST name. Do not use any other entity equivalence outside the provided lists. A fusion protein, complex, family name, homologue, or other form not explicitly allowed above is not equivalent to the Gold entity; flag review and do not use ABSTRACT_SUPPORTED. Do not use knowledge outside title/abstract.\nGold species: {species}\nGold TF: {tf}\nGold Target: {target}\nGold MoR: {mor}\nPMID: {pmid}\nTF mentions: {tf_mentions}\nTarget mentions: {target_mentions}\nTitle: {title}\nAbstract: {abstract}"""
def parse_model_json(content):
 text=content.strip()
 if text.startswith("```"):
  text=text.split("\n",1)[1] if "\n" in text else text
  if text.rstrip().endswith("```"): text=text.rstrip()[:-3].rstrip()
 try:return json.loads(text)
 except json.JSONDecodeError:
  start,end=text.find("{"),text.rfind("}")
  if start>=0 and end>start:return json.loads(text[start:end+1])
  raise
def main():
 p=argparse.ArgumentParser();p.add_argument("--input",default="data/intermediate/trrust_entity_both_mentioned_v1_20260826.jsonl");p.add_argument("--output",required=True);p.add_argument("--model",default="qwen35-fp8");p.add_argument("--base-url",default="http://127.0.0.1:8001");p.add_argument("--api-key",default=os.getenv("VLLM_API_KEY"));p.add_argument("--max-tokens",type=int,default=1536);p.add_argument("--limit",type=int);a=p.parse_args()
 out=ROOT/a.output;out.parent.mkdir(parents=True,exist_ok=True);done=set()
 if out.exists():
  done={json.loads(x)["record_key"] for x in out.open()}
 articles={json.loads(x)["pmid"]:json.loads(x) for x in (ROOT/"data/intermediate/trrust_pubmed_articles_v1_20260826.jsonl").open()}
 aliases={}
 for x in (ROOT/"data/intermediate/gene_alias_mapping_v1_20260826.jsonl").open():
  q=json.loads(x);aliases[(q["species"],q.get("approved_symbol",q.get("mgi_symbol")))]=q["mention_candidates"]
 n=0
 with out.open("a") as f:
  for line in (ROOT/a.input).open():
   x=json.loads(line);species=x.get("species") or x.get("stratum",{}).get("species");
   if not isinstance(species,str):raise ValueError("input record lacks species or stratum.species")
   key="|".join([species,x["tf_mention"],x["object_mention"],x["relation"],x["pmid"]])
   if key in done:continue
   z=articles[x["pmid"]];prompt=TEMPLATE.format(species=species,tf=x["tf_mention"],target=x["object_mention"],mor=x["relation"],pmid=x["pmid"],tf_mentions=json.dumps(aliases.get((species,x["tf_mention"]),[x["tf_mention"]]),ensure_ascii=False),target_mentions=json.dumps(aliases.get((species,x["object_mention"]),[x["object_mention"]]),ensure_ascii=False),title=z["title"],abstract=z["abstract"])
   body=json.dumps({"model":a.model,"messages":[{"role":"user","content":prompt}],"response_format":{"type":"json_object"},"temperature":0.0,"max_tokens":a.max_tokens,"chat_template_kwargs":{"enable_thinking":False}},ensure_ascii=False).encode()
   headers={"Content-Type":"application/json"}
   if a.api_key: headers["Authorization"]="Bearer "+a.api_key
   try:
    r=request.urlopen(request.Request(a.base_url.rstrip("/")+"/v1/chat/completions",data=body,headers=headers),timeout=180)
    ans=parse_model_json(json.loads(r.read())["choices"][0]["message"]["content"])
   except Exception as error:
    print(f"ERROR record_key={key} {type(error).__name__}: {error}",flush=True);continue
   f.write(json.dumps({"record_key":key,"prompt_version":"phase3_adjudication_v4_no_tf_specific_perturbation_requirement","input":x,"review":ans},ensure_ascii=False)+"\n");f.flush();n+=1;time.sleep(.1)
   if a.limit and n>=a.limit:break
if __name__=="__main__":main()
