"""Create a browser-local human audit workbook from Phase 3 holdout results."""
from __future__ import annotations

import argparse
import html
import json
import random
from collections import defaultdict
from pathlib import Path


ROOT = Path("/workspace/zzc/GeneReg-Eval")


def esc(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def species_of(item: dict) -> str:
    return str(item.get("species") or item.get("stratum", {}).get("species"))


def choose_rows(rows: list[dict], seed: int) -> list[dict]:
    """Select 50 rows: 8/8/9 from A/R/U for each species."""
    quotas = {
        ("human", "Activation"): 8,
        ("human", "Repression"): 8,
        ("human", "Unknown"): 9,
        ("mouse", "Activation"): 8,
        ("mouse", "Repression"): 8,
        ("mouse", "Unknown"): 9,
    }
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        item = row["input"]
        grouped[(species_of(item), item["relation"])].append(row)
    rng = random.Random(seed)
    selected: list[dict] = []
    for key, quota in quotas.items():
        candidates = grouped[key]
        if len(candidates) < quota:
            raise ValueError(f"Insufficient records for {key}: {len(candidates)} < {quota}")
        selected.extend(rng.sample(candidates, quota))
    rng.shuffle(selected)
    return selected


def card(index: int, row: dict) -> str:
    item, review = row["input"], row["review"]
    species = species_of(item)
    condition = review.get("condition") or {}
    condition_text = "<br>".join(
        f"{esc(k)}: {esc(v)}" for k, v in condition.items() if v
    ) or "null"
    model_status = review.get("support_status", "")
    model_supported = "YES" if model_status == "ABSTRACT_SUPPORTED" else "NO"
    payload = {
        "audit_id": f"phase3_holdout_audit_v1_{index:03d}",
        "record_key": row["record_key"],
        "pmid": item["pmid"],
        "species": species,
        "trrust_tf": item["tf_mention"],
        "trrust_target": item["object_mention"],
        "trrust_mor": item["relation"],
        "model_support_status": model_status,
        "model_evidence_span": review.get("evidence_span"),
    }
    encoded = esc(json.dumps(payload, ensure_ascii=False))
    return f'''<article class="card" data-record='{encoded}'>
<h2>#{index:02d} · PMID {esc(item["pmid"])} <span>{esc(species)} · {esc(item["relation"])} · model {esc(model_status)}</span></h2>
<div class="candidate"><b>TRRUST candidate / 待验证关系：</b>{esc(item["tf_mention"])} → {esc(item["object_mention"])}；MoR: {esc(item["relation"])}</div>
<div class="alignment"><b>Model entity alignment / 模型实体对齐：</b>TF <code>{esc(item["tf_mention"])}</code> → <code>{esc(review.get("extracted_tf_mention"))}</code>；Target <code>{esc(item["object_mention"])}</code> → <code>{esc(review.get("extracted_target_mention"))}</code></div>
<details open class="model"><summary><b>Model output / 模型结论：</b><span class="badge {esc(model_status)}">{esc(model_status)} · supported={model_supported}</span></summary>
<p><b>Evidence span / 模型证据片段：</b><mark>{esc(review.get("evidence_span") or "null")}</mark></p>
<p><b>Condition / 条件：</b><br>{condition_text}</p>
<p><b>Model note / 模型备注：</b>{esc(review.get("review_note") or "")}</p></details>
<h3>Title / 标题</h3><p>{esc(item.get("title"))}</p>
<h3>English abstract / 英文摘要（唯一证据来源）</h3><p class="abstract">{esc(item.get("abstract"))}</p>
<section class="human"><h3>Your audit / 人工审阅</h3>
<label>Is this specific TRRUST relation independently supported? / 是否独立支持该特定 TRRUST 关系？
<select data-field="human_supported"><option value="">Not reviewed / 未审阅</option><option value="YES">YES — ABSTRACT_SUPPORTED</option><option value="NO">NO — not independently supported</option></select></label>
<label>Evidence span (English original only) / 证据片段（仅英文原文）
<textarea data-field="human_evidence_span" placeholder="Copy one continuous supporting original-text span, or leave blank when NO."></textarea></label>
<label>Audit note / 审阅备注
<textarea data-field="human_note" placeholder="Optional: entity/species, direction, or evidence issue."></textarea></label>
</section></article>'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--selected-output", required=True)
    parser.add_argument("--html-output", required=True)
    parser.add_argument("--seed", type=int, default=20260829)
    args = parser.parse_args()
    selected_path, html_path = ROOT / args.selected_output, ROOT / args.html_output
    if selected_path.exists() or html_path.exists():
        raise SystemExit("Refusing to overwrite an existing audit artifact.")
    rows = [json.loads(line) for line in (ROOT / args.input).open(encoding="utf-8") if line.strip()]
    selected = choose_rows(rows, args.seed)
    selected_path.parent.mkdir(parents=True, exist_ok=True)
    with selected_path.open("x", encoding="utf-8") as handle:
        for row in selected:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    cards = "\n".join(card(i, row) for i, row in enumerate(selected, 1))
    page = f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Phase 3 Holdout Audit v1</title>
<style>
:root{{color-scheme:light;font-family:Arial,"Microsoft YaHei",sans-serif;color:#172b4d;background:#f3f5f7}}body{{margin:0}}header{{position:sticky;top:0;z-index:5;background:#102a43;color:#fff;padding:14px 5%;box-shadow:0 1px 5px #567}}main{{max-width:1200px;margin:auto;padding:18px}}.card{{background:#fff;margin:16px 0;padding:20px;border-radius:9px;box-shadow:0 1px 5px #cbd5e1}}h2{{margin:0 0 12px;font-size:18px}}h2 span{{font-size:13px;color:#52606d;font-weight:normal}}h3{{font-size:15px;margin:16px 0 7px}}p{{line-height:1.6}}.candidate{{background:#fff4cc;padding:11px;border-left:4px solid #d69e2e}}.alignment,.model{{margin-top:10px;background:#eef7ff;padding:11px;border-radius:5px;line-height:1.55}}summary{{cursor:pointer}}.badge{{padding:3px 6px;border-radius:4px;background:#dbeafe}}.ABSTRACT_SUPPORTED{{background:#bbf7d0}}.ABSTRACT_PARTIAL{{background:#fde68a}}.ABSTRACT_INSUFFICIENT{{background:#fecaca}}.abstract{{white-space:pre-wrap;background:#f8fafc;border:1px solid #e2e8f0;padding:14px}}mark{{background:#c6f6d5;padding:2px}}.human{{margin-top:16px;padding:14px;background:#f0fdf4;border:1px solid #86efac;border-radius:6px}}label{{display:block;font-weight:600;margin-top:11px}}select,textarea{{box-sizing:border-box;width:100%;margin-top:5px;padding:8px;font:inherit;border:1px solid #94a3b8;border-radius:5px;background:#fff}}textarea{{min-height:75px;resize:vertical}}button{{margin:4px 8px 0 0;padding:8px 11px;border:0;border-radius:5px;cursor:pointer;font:inherit}}.primary{{background:#38a169;color:#fff}}.secondary{{background:#e2e8f0;color:#172b4d}}#progress{{margin-left:8px}}@media(max-width:700px){{header{{position:static}}main{{padding:10px}}.card{{padding:14px}}}}
</style></head><body><header><b>Phase 3 independent holdout audit / Phase 3 独立留出集审阅</b><br><small>50 deterministic stratified records; English title/abstract is the sole evidence source. Model output is displayed for quality audit.</small><br><button class="primary" id="download">Export audit JSON / 导出审阅 JSON</button><button class="secondary" id="clear">Clear this browser's saved form / 清除本浏览器缓存</button><span id="progress"></span></header><main>{cards}</main>
<script>
const key='phase3_holdout_audit_v1_20260829';
const fields=[...document.querySelectorAll('[data-field]')];
const saved=JSON.parse(localStorage.getItem(key)||'{{}}');
for(const field of fields){{const id=field.closest('.card').dataset.record;const row=JSON.parse(id);field.value=(saved[row.record_key]||{{}})[field.dataset.field]||'';}}
function persist(){{const data={{}};for(const field of fields){{const row=JSON.parse(field.closest('.card').dataset.record);(data[row.record_key]??={{...row}})[field.dataset.field]=field.value||null;}}localStorage.setItem(key,JSON.stringify(data));const reviewed=Object.values(data).filter(x=>x.human_supported).length;document.querySelector('#progress').textContent=`Reviewed: ${{reviewed}} / 50`;}}
fields.forEach(x=>{{x.addEventListener('input',persist);x.addEventListener('change',persist);}});persist();
document.querySelector('#download').onclick=()=>{{persist();const data=Object.values(JSON.parse(localStorage.getItem(key)||'{{}}'));const blob=new Blob([JSON.stringify(data,null,2)],{{type:'application/json'}});const a=document.createElement('a');const url=URL.createObjectURL(blob);a.href=url;a.download='human_phase3_holdout_audit_v1_20260829.json';a.style.display='none';document.body.appendChild(a);a.click();setTimeout(()=>{{a.remove();URL.revokeObjectURL(url);}},1500);}};
document.querySelector('#clear').onclick=()=>{{if(confirm("Clear only this browser's locally saved form values?")){{localStorage.removeItem(key);location.reload();}}}};
</script></body></html>'''
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(page, encoding="utf-8")
    print(json.dumps({"selected_output": str(selected_path), "html_output": str(html_path), "records": len(selected)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
