"""Freeze an independent Human L0/L1 benchmark and render its human audit page.

The benchmark is sampled by *unique PMID*, never by merely unique TRRUST
edge.  It excludes PMIDs present in every existing project review, model,
translation, or teacher artifact.  The resulting manifest is therefore
independent of prior development workflows and retains all provenance needed
to add a nested L2 reasoning review later.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import random
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(os.environ.get("GENEREG_EVAL_ROOT", Path(__file__).resolve().parents[2]))
VERSION = "human_heldout_l0_l1_benchmark_v1_20260901"
SOURCE_CANDIDATES = "data/intermediate/trrust_entity_both_mentioned_v1_20260826.jsonl"
SOURCE_ARTICLES = "data/intermediate/trrust_pubmed_articles_v1_20260826.jsonl"
SOURCE_ALIASES = "data/intermediate/gene_alias_mapping_v1_20260826.jsonl"
WORKFLOW_TOKENS = (
    "review", "audit", "benchmark", "phase3", "qwen", "teacher", "manual",
    "disagreement", "extraction", "translation", "deepseek",
)
NON_BENCHMARK_PREPROCESSING = {
    "data/intermediate/trrust_entity_mention_audit_v1_20260826.jsonl",
    "data/intermediate/trrust_entity_mention_audit_v1_20260826_stats.json",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def pmid_from_key(record_key: str) -> str | None:
    fields = record_key.split("|")
    return fields[-1] if fields and fields[-1].isdigit() else None


def collect_pmids(value: Any, output: set[str]) -> None:
    """Collect record-bearing PMIDs recursively from a workflow artifact."""
    if isinstance(value, dict):
        record_key = value.get("record_key")
        if isinstance(record_key, str):
            pmid = pmid_from_key(record_key)
            if pmid:
                output.add(pmid)
        pmid = value.get("pmid")
        if isinstance(pmid, (str, int)) and str(pmid).isdigit():
            output.add(str(pmid))
        for nested in value.values():
            collect_pmids(nested, output)
    elif isinstance(value, list):
        for nested in value:
            collect_pmids(nested, output)


def workflow_exclusions() -> tuple[set[str], list[dict[str, Any]]]:
    """Return prior-workflow PMIDs and a frozen inventory of the scanned files."""
    excluded: set[str] = set()
    inventory: list[dict[str, Any]] = []
    for base in (ROOT / "data", ROOT / "reports"):
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.suffix not in {".json", ".jsonl"}:
                continue
            relative = str(path.relative_to(ROOT))
            if relative in NON_BENCHMARK_PREPROCESSING or relative in {
                SOURCE_CANDIDATES, SOURCE_ARTICLES, SOURCE_ALIASES,
            }:
                continue
            path_parts = Path(relative).parts
            if "inputs" in path_parts or path.name in {"input.jsonl", "input_manifest.jsonl", "planned_record_pmids.jsonl"}:
                # A scheduled input does not imply that a model or a reviewer
                # saw the record. Actual outputs remain exclusion sources.
                continue
            lowered = relative.lower()
            if not any(token in lowered for token in WORKFLOW_TOKENS):
                continue
            before = len(excluded)
            try:
                if path.suffix == ".jsonl":
                    for row in read_jsonl(path):
                        collect_pmids(row, excluded)
                else:
                    collect_pmids(json.loads(path.read_text(encoding="utf-8")), excluded)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            inventory.append({
                "path": relative,
                "sha256": sha256(path),
                "new_excluded_pmids": len(excluded) - before,
            })
    return excluded, inventory


def compact_mentions(mapping: dict[str, Any] | None, fallback: str) -> list[str]:
    values = list((mapping or {}).get("mention_candidates") or [fallback])
    return values[:16]


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def render_card(index: int, row: dict[str, Any]) -> str:
    source, article = row["source_record"], row["article"]
    aliases = row["entity_mapping"]
    data = {
        "sample_id": row["sample_id"],
        "record_key": row["record_key"],
        "pmid": row["pmid"],
        "species": "human",
        "candidate": {key: source[key] for key in ("tf_mention", "object_mention", "relation")},
        "provenance": row["provenance"],
    }
    encoded = esc(json.dumps(data, ensure_ascii=False))
    tf_aliases = ", ".join(aliases["tf"]["mention_candidates"])
    target_aliases = ", ".join(aliases["target"]["mention_candidates"])
    return f'''<article class="card" data-record="{encoded}">
<h2>#{index:03d} · PMID {esc(row["pmid"])} <span>{esc(source["relation"])}</span></h2>
<section class="candidate"><b>TRRUST candidate / 待判定关系</b><br>{esc(source["tf_mention"])} → {esc(source["object_mention"])} · MoR: {esc(source["relation"])}</section>
<details class="mapping"><summary>Entity mapping aid / 实体映射辅助（不含模型结论）</summary><p><b>TF</b> {esc(source["tf_mention"])}: {esc(tf_aliases)}</p><p><b>Target</b> {esc(source["object_mention"])}: {esc(target_aliases)}</p></details>
<h3>Title / 标题</h3><p>{esc(article["title"])}</p>
<h3>English original abstract / 英文原始摘要（唯一证据来源）</h3><p class="abstract">{esc(article["abstract"])}</p>
<section class="l0"><h3>L0 · Support adjudication / 摘要独立支持判定</h3>
<label>Support status / 支持程度<select data-field="l0_support_status"><option value="">未审阅</option><option>ABSTRACT_SUPPORTED</option><option>ABSTRACT_PARTIAL</option><option>ABSTRACT_INSUFFICIENT</option><option>REVIEW_UNCERTAIN</option></select></label>
<label>L0 note / L0 备注（可选）<textarea data-field="l0_note" placeholder="例如：binding only、实体边界不清、方向不明。"></textarea></label></section>
<section class="l1"><h3>L1 · Evidence-grounded relation extraction / 证据约束关系抽取</h3><p class="hint">仅当 L0 = <code>ABSTRACT_SUPPORTED</code> 时填写。所有文本必须复制自英文 title/abstract；不要使用外部知识。</p>
<label>Evidence span / 证据片段<textarea data-field="l1_evidence_span" placeholder="复制一个连续、足以支持该关系的英文原文片段。"></textarea></label>
<div class="grid"><label>TF mention in source / 原文 TF 表述<input data-field="l1_regulator_mention" placeholder="原文中的实体名称"></label><label>Target mention in source / 原文 Target 表述<input data-field="l1_object_mention" placeholder="原文中的实体名称"></label></div>
<label>Relation supported by abstract / 摘要支持的关系<select data-field="l1_relation"><option value="">未填写</option><option>Activation</option><option>Repression</option><option>Unknown</option></select></label>
<label>Relation-level condition / 关系成立条件（可选）<textarea data-field="l1_condition_note" placeholder="只写‘关系只在哪些条件下成立’的原文信息；不要把用于证明因果的 knockdown/overexpression 自动当作 condition。"></textarea></label>
<label>L1 note / L1 备注（可选）<textarea data-field="l1_note" placeholder="可记录 promoter、isoform、species 或对象边界等信息。"></textarea></label></section>
<details class="provenance"><summary>Frozen provenance / 冻结来源（供后续 L2 复用）</summary><pre>{esc(json.dumps(row["provenance"], ensure_ascii=False, indent=2))}</pre></details>
</article>'''


def render_html(rows: list[dict[str, Any]], metadata: dict[str, Any]) -> str:
    cards = "\n".join(render_card(index, row) for index, row in enumerate(rows, 1))
    metadata_json = json.dumps(metadata, ensure_ascii=False)
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Human Held-out L0/L1 Benchmark v1</title>
<style>
:root{{font-family:Arial,"Microsoft YaHei",sans-serif;color:#172b4d;background:#f1f5f9}}body{{margin:0}}header{{position:sticky;top:0;z-index:10;padding:14px 5%;background:#102a43;color:white;box-shadow:0 2px 7px #64748b}}header small{{display:block;margin-top:4px;color:#dbeafe}}main{{max-width:1120px;margin:auto;padding:12px 18px 32px}}.card{{background:#fff;border-radius:10px;padding:22px;margin:16px 0;box-shadow:0 1px 5px #cbd5e1}}h2{{margin:0 0 12px;font-size:19px}}h2 span{{font-size:13px;font-weight:normal;color:#64748b}}h3{{font-size:15px;margin:18px 0 8px}}p{{line-height:1.6}}.candidate{{background:#fff7d6;border-left:4px solid #d69e2e;padding:11px;line-height:1.5}}.mapping,.provenance{{margin-top:11px;padding:10px;background:#eff6ff;border-radius:6px}}summary{{cursor:pointer;font-weight:600}}.abstract{{white-space:pre-wrap;background:#f8fafc;border:1px solid #dbe3ee;padding:13px;border-radius:5px}}.l0,.l1{{margin-top:16px;padding:15px;border-radius:7px}}.l0{{background:#eff6ff;border:1px solid #93c5fd}}.l1{{background:#f0fdf4;border:1px solid #86efac}}label{{display:block;font-weight:600;margin-top:10px}}select,input,textarea{{box-sizing:border-box;width:100%;margin-top:5px;padding:8px;font:inherit;border:1px solid #94a3b8;border-radius:5px;background:white}}textarea{{min-height:75px;resize:vertical}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}.hint{{font-size:13px;color:#475569;margin:0}}button{{font:inherit;padding:8px 12px;border:0;border-radius:5px;margin:8px 8px 0 0;cursor:pointer}}.primary{{background:#22c55e;color:white}}.secondary{{background:#dbeafe;color:#172b4d}}.danger{{background:#fee2e2;color:#991b1b}}#progress{{margin-left:8px;font-weight:bold}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}}@media(max-width:700px){{header{{position:static}}main{{padding:10px}}.card{{padding:14px}}.grid{{grid-template-columns:1fr}}}}
</style></head><body><header><b>Independent Human held-out benchmark · L0/L1</b><small>{len(rows)} unique PMID samples; no model output is displayed. English title/abstract is the only evidence source. Browser autosave survives Ctrl+R.</small><button type="button" class="primary" id="download">Export review JSON / 导出审阅 JSON</button><label class="secondary" style="display:inline-block;padding:8px 12px;border-radius:5px;cursor:pointer">Import saved JSON / 导入审阅 JSON<input id="import" type="file" accept="application/json" hidden></label><button type="button" class="danger" id="clear">Clear local draft / 清除本机草稿</button><span id="progress"></span></header><main>{cards}</main>
<script>
const storageKey='{VERSION}'; const benchmarkMetadata={metadata_json}; const fields=[...document.querySelectorAll('[data-field]')];
function recordOf(field){{return JSON.parse(field.closest('.card').dataset.record)}}
function saved(){{try{{return JSON.parse(localStorage.getItem(storageKey)||'{{}}')}}catch{{return {{}}}}}}
function persist(){{const draft=saved();for(const field of fields){{const meta=recordOf(field);draft[meta.sample_id]??={{...meta}};draft[meta.sample_id][field.dataset.field]=field.value||null;}}localStorage.setItem(storageKey,JSON.stringify(draft));const rows=Object.values(draft);const l0=rows.filter(x=>x.l0_support_status).length;const l1=rows.filter(x=>x.l0_support_status==='ABSTRACT_SUPPORTED'&&x.l1_evidence_span).length;document.querySelector('#progress').textContent=`L0: ${{l0}} / {len(rows)} · L1 complete: ${{l1}}`;}}
function restore(){{const draft=saved();for(const field of fields){{const row=draft[recordOf(field).sample_id]||{{}};field.value=row[field.dataset.field]||'';}}persist();}}
fields.forEach(field=>{{field.addEventListener('input',persist);field.addEventListener('change',persist);}});window.addEventListener('beforeunload',persist);restore();
document.querySelector('#download').addEventListener('click',()=>{{persist();const payload={{benchmark_metadata:benchmarkMetadata,reviewed_at_local:new Date().toISOString(),records:Object.values(saved())}};const blob=new Blob([JSON.stringify(payload,null,2)],{{type:'application/json;charset=utf-8'}});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='{VERSION}_review.json';document.body.appendChild(a);a.click();setTimeout(()=>{{URL.revokeObjectURL(a.href);a.remove()}},1000);}});
document.querySelector('#import').addEventListener('change',event=>{{const file=event.target.files[0];if(!file)return;const reader=new FileReader();reader.onload=()=>{{try{{const value=JSON.parse(reader.result);const rows=Array.isArray(value)?value:value.records;if(!Array.isArray(rows))throw new Error('records array missing');const draft=saved();for(const row of rows)if(row.sample_id)draft[row.sample_id]={{...(draft[row.sample_id]||{{}}),...row}};localStorage.setItem(storageKey,JSON.stringify(draft));restore();alert('Imported '+rows.length+' records.')}}catch(error){{alert('Import failed: '+error.message)}}}};reader.readAsText(file,'utf-8');event.target.value='';}});
document.querySelector('#clear').addEventListener('click',()=>{{if(confirm('Only this page\'s browser-local draft will be removed. Export first if needed.')){{localStorage.removeItem(storageKey);for(const field of fields)field.value='';persist();}}}});
</script></body></html>'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-output", required=True)
    parser.add_argument("--stats-output", required=True)
    parser.add_argument("--html-output", required=True)
    parser.add_argument("--seed", type=int, default=20260901)
    parser.add_argument("--version", default=VERSION)
    parser.add_argument("--relations", nargs="+", choices=("Activation", "Repression", "Unknown"), default=("Activation", "Repression", "Unknown"))
    parser.add_argument("--per-relation", type=int, default=133)
    args = parser.parse_args()
    manifest_path, stats_path, html_path = (ROOT / args.manifest_output, ROOT / args.stats_output, ROOT / args.html_output)
    if any(path.exists() for path in (manifest_path, stats_path, html_path)):
        raise SystemExit("Refusing to overwrite an existing benchmark artifact")

    excluded_pmids, inventory = workflow_exclusions()
    articles = {str(row["pmid"]): row for row in read_jsonl(ROOT / SOURCE_ARTICLES)}
    aliases = {(row["species"], row.get("approved_symbol") or row.get("mgi_symbol")): row for row in read_jsonl(ROOT / SOURCE_ALIASES)}
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for source in read_jsonl(ROOT / SOURCE_CANDIDATES):
        if source.get("species") != "human" or source.get("abstract_status") != "ABSTRACT_AVAILABLE":
            continue
        pmid = str(source["pmid"])
        if pmid in excluded_pmids or pmid not in articles:
            continue
        grouped[source["relation"]][pmid].append(source)

    if args.per_relation < 1:
        raise ValueError("--per-relation must be positive")
    quotas = {relation: args.per_relation for relation in args.relations}
    rng = random.Random(args.seed)
    selected: list[dict[str, Any]] = []
    selected_pmids: set[str] = set()
    for relation, quota in quotas.items():
        pmids = list(grouped[relation])
        rng.shuffle(pmids)
        chosen = [pmid for pmid in pmids if pmid not in selected_pmids][:quota]
        if len(chosen) != quota:
            availability = {name: len(values) for name, values in grouped.items()}
            raise ValueError(
                f"Insufficient independent PMIDs for {relation}: {len(chosen)} < {quota}; "
                f"available_by_relation={availability}; excluded_pmids={len(excluded_pmids)}; articles={len(articles)}; "
                f"largest_exclusion_files={sorted(inventory, key=lambda entry: entry['new_excluded_pmids'], reverse=True)[:30]}"
            )
        for pmid in chosen:
            source = rng.choice(grouped[relation][pmid])
            selected_pmids.add(pmid)
            tf, target = source["tf_mention"], source["object_mention"]
            selected.append({
                "sample_id": f"{args.version}_{len(selected) + 1:03d}",
                "record_key": "|".join(["human", tf, target, source["relation"], pmid]),
                "pmid": pmid,
                "stratum": {"species": "human", "trrust_mor": source["relation"]},
                "source_record": source,
                "article": articles[pmid],
                "entity_mapping": {
                    "tf": {"approved_symbol": tf, "mention_candidates": compact_mentions(aliases.get(("human", tf)), tf)},
                    "target": {"approved_symbol": target, "mention_candidates": compact_mentions(aliases.get(("human", target)), target)},
                },
                "provenance": {
                    "benchmark_version": args.version,
                    "selection_seed": args.seed,
                    "source_candidate_file": SOURCE_CANDIDATES,
                    "source_article_file": SOURCE_ARTICLES,
                    "source_alias_file": SOURCE_ALIASES,
                    "source_pmid": pmid,
                    "workflow_exclusion": "PMID absent from frozen inventory of all pre-existing review/model/teacher workflow artifacts.",
                },
            })
    rng.shuffle(selected)
    for index, row in enumerate(selected, 1):
        row["sample_id"] = f"{args.version}_{index:03d}"

    metadata = {
        "benchmark_version": args.version,
        "purpose": "Independent Human held-out benchmark with nested L0 support adjudication and L1 evidence-grounded relation extraction; L2 provenance retained but L2 is not annotated in this workbook.",
        "sample_size": len(selected),
        "unique_pmids": len({row["pmid"] for row in selected}),
        "seed": args.seed,
        "strata": {relation: sum(row["stratum"]["trrust_mor"] == relation for row in selected) for relation in quotas},
        "source_files": {
            SOURCE_CANDIDATES: sha256(ROOT / SOURCE_CANDIDATES),
            SOURCE_ARTICLES: sha256(ROOT / SOURCE_ARTICLES),
            SOURCE_ALIASES: sha256(ROOT / SOURCE_ALIASES),
        },
        "workflow_exclusion_pmids": len(excluded_pmids),
        "reservation_policy": "All selected PMIDs are permanently reserved for this benchmark and must be excluded from later sampling, model inference, translation, training, and benchmark construction workflows.",
        "workflow_inventory": inventory,
        "l0_schema": ["ABSTRACT_SUPPORTED", "ABSTRACT_PARTIAL", "ABSTRACT_INSUFFICIENT", "REVIEW_UNCERTAIN"],
        "l1_policy": "Annotate L1 only for L0 ABSTRACT_SUPPORTED. Copy source-form entity mentions and continuous English evidence span.",
    }
    for path in (manifest_path, stats_path, html_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("x", encoding="utf-8") as handle:
        for row in selected:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    stats_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    html_path.write_text(render_html(selected, metadata), encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path), "stats": str(stats_path), "html": str(html_path), "records": len(selected)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
