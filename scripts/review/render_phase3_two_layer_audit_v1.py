"""Render a robust browser-local human audit workbook for two-layer reviews."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


ROOT = Path("/workspace/zzc/GeneReg-Eval")


def esc(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def species_of(item: dict) -> str:
    return str(item.get("species") or item.get("stratum", {}).get("species"))


def card(index: int, first: dict, second: dict) -> str:
    item, review = first["input"], first["review"]
    verification = second.get("verification") or {}
    validation_route = second.get("verification_validation_route", "UNVALIDATED")
    validation_errors = "; ".join(second.get("verification_validation_errors") or []) or "none"
    payload = {
        "audit_id": f"phase3_two_layer_audit_v1_{index:03d}", "record_key": first["record_key"], "pmid": item["pmid"],
        "species": species_of(item), "trrust_tf": item["tf_mention"], "trrust_target": item["object_mention"], "trrust_mor": item["relation"],
        "layer1_status": review.get("support_status"), "layer1_span": review.get("evidence_span"),
        "layer2_judgment": verification.get("layer1_judgment"), "layer2_expected_status": verification.get("expected_support_status"),
    }
    encoded = esc(json.dumps(payload, ensure_ascii=False))
    tags = ", ".join(verification.get("error_types") or []) or "none"
    if "decision" in verification:
        layer2_html = f'''<details open class="layer two"><summary><b>Layer 2 / 第二层：</b>{esc(verification.get("decision"))} · validator={esc(validation_route)}</summary><p><b>Validator errors：</b>{esc(validation_errors)}</p></details>'''
    else:
        layer2_html = f'''<details open class="layer two"><summary><b>Layer 2 / 第二层：</b>{esc(verification.get("layer1_judgment"))} · expected {esc(verification.get("expected_support_status"))} · accept={esc(verification.get("accept_supported"))} · validator={esc(validation_route)}</summary><p><b>Error types：</b>{esc(tags)}</p><p><b>Validator errors：</b>{esc(validation_errors)}</p><p><b>Note：</b>{esc(verification.get("review_note") or second.get("error") or "")}</p></details>'''
    return f'''<article class="card" data-record='{encoded}'>
<h2>#{index:02d} · PMID {esc(item["pmid"])} <span>{esc(species_of(item))} · {esc(item["relation"])}</span></h2>
<div class="candidate"><b>TRRUST candidate / 待验证关系：</b>{esc(item["tf_mention"])} → {esc(item["object_mention"])}；MoR: {esc(item["relation"])}</div>
<div class="alignment"><b>Entity alignment / 实体对齐：</b>TF <code>{esc(item["tf_mention"])}</code> → <code>{esc(review.get("extracted_tf_mention"))}</code>；Target <code>{esc(item["object_mention"])}</code> → <code>{esc(review.get("extracted_target_mention"))}</code></div>
<details open class="layer one"><summary><b>Layer 1 / 第一层：</b>{esc(review.get("support_status"))}</summary><p><b>Evidence span：</b><mark>{esc(review.get("evidence_span") or "null")}</mark></p><p><b>Note：</b>{esc(review.get("review_note") or "")}</p></details>
{layer2_html}
<h3>Title / 标题</h3><p>{esc(item.get("title"))}</p>
<h3>English abstract / 英文摘要（唯一证据来源）</h3><p class="abstract">{esc(item.get("abstract"))}</p>
<section class="human"><h3>Your final audit / 人工最终审阅</h3><label>Is the specific TRRUST relation independently supported? / 是否独立支持该特定 TRRUST 关系？<select data-field="human_supported"><option value="">Not reviewed / 未审阅</option><option value="YES">YES — ABSTRACT_SUPPORTED</option><option value="NO">NO — not independently supported</option></select></label><label>Evidence span (English original only) / 证据片段（仅英文原文）<textarea data-field="human_evidence_span" placeholder="Copy one continuous supporting original-text span, or leave blank when NO."></textarea></label><label>Audit note / 审阅备注<textarea data-field="human_note" placeholder="Optional: explain entity, species, direction, or evidence issue."></textarea></label></section>
</article>'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--first-pass", required=True)
    parser.add_argument("--second-pass", required=True)
    parser.add_argument("--combined-output", required=True)
    parser.add_argument("--html-output", required=True)
    args = parser.parse_args()
    combined_path, html_path = ROOT / args.combined_output, ROOT / args.html_output
    if combined_path.exists() or html_path.exists():
        raise SystemExit("Refusing to overwrite an existing audit artifact")
    first_rows = [json.loads(line) for line in (ROOT / args.first_pass).open(encoding="utf-8") if line.strip()]
    second_rows = {row["record_key"]: row for row in (json.loads(line) for line in (ROOT / args.second_pass).open(encoding="utf-8") if line.strip())}
    if len(first_rows) != len(second_rows) or any(row["record_key"] not in second_rows for row in first_rows):
        raise ValueError("First- and second-pass records are not a one-to-one match")
    combined_path.parent.mkdir(parents=True, exist_ok=True)
    with combined_path.open("x", encoding="utf-8") as handle:
        for first in first_rows:
            handle.write(json.dumps({"first_pass": first, "second_pass": second_rows[first["record_key"]]}, ensure_ascii=False) + "\n")
    cards = "\n".join(card(index, first, second_rows[first["record_key"]]) for index, first in enumerate(first_rows, 1))
    page = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Phase 3 Two-Layer Audit v1</title><style>
:root{font-family:Arial,"Microsoft YaHei",sans-serif;color:#172b4d;background:#f3f5f7}body{margin:0}header{position:sticky;top:0;z-index:5;background:#102a43;color:#fff;padding:14px 5%;box-shadow:0 1px 5px #567}main{max-width:1200px;margin:auto;padding:18px}.card{background:#fff;margin:16px 0;padding:20px;border-radius:9px;box-shadow:0 1px 5px #cbd5e1}h2{margin:0 0 12px;font-size:18px}h2 span{font-size:13px;color:#52606d;font-weight:normal}h3{font-size:15px;margin:16px 0 7px}p{line-height:1.6}.candidate{background:#fff4cc;padding:11px;border-left:4px solid #d69e2e}.alignment,.layer{margin-top:10px;padding:11px;border-radius:5px;line-height:1.55}.alignment{background:#f1f5f9}.one{background:#eef7ff}.two{background:#f3e8ff}summary{cursor:pointer}.abstract{white-space:pre-wrap;background:#f8fafc;border:1px solid #e2e8f0;padding:14px}mark{background:#c6f6d5;padding:2px}.human{margin-top:16px;padding:14px;background:#f0fdf4;border:1px solid #86efac;border-radius:6px}label{display:block;font-weight:600;margin-top:11px}select,textarea{box-sizing:border-box;width:100%;margin-top:5px;padding:8px;font:inherit;border:1px solid #94a3b8;border-radius:5px;background:#fff}textarea{min-height:75px;resize:vertical}button{margin:4px 8px 0 0;padding:8px 11px;border:0;border-radius:5px;cursor:pointer;font:inherit}.primary{background:#38a169;color:#fff}.secondary{background:#e2e8f0;color:#172b4d}#progress{margin-left:8px}@media(max-width:700px){header{position:static}main{padding:10px}.card{padding:14px}}</style></head><body><header><b>Phase 3 two-layer independent audit / Phase 3 两层独立审阅</b><br><small>30 records from the unreviewed holdout remainder. English title/abstract is the sole evidence source; model outputs are review aids, not evidence.</small><br><button class="primary" id="download">Export audit JSON / 导出审阅 JSON</button><button class="secondary" id="clear">Clear this browser's saved form / 清除本浏览器缓存</button><span id="progress"></span></header><main>""" + cards + """</main><script>
const key='phase3_two_layer_audit_v2_20260829';
const fields=[...document.querySelectorAll('[data-field]')];
const saved=JSON.parse(localStorage.getItem(key)||'{}');
for(const field of fields){const row=JSON.parse(field.closest('.card').dataset.record);field.value=(saved[row.record_key]||{})[field.dataset.field]||'';}
function persist(){const data={};for(const field of fields){const row=JSON.parse(field.closest('.card').dataset.record);(data[row.record_key]??={...row})[field.dataset.field]=field.value||null;}localStorage.setItem(key,JSON.stringify(data));const reviewed=Object.values(data).filter(x=>x.human_supported).length;document.querySelector('#progress').textContent=`Reviewed: ${reviewed} / 30`;}
fields.forEach(x=>{x.addEventListener('input',persist);x.addEventListener('change',persist);});persist();
document.querySelector('#download').onclick=()=>{persist();const data=Object.values(JSON.parse(localStorage.getItem(key)||'{}'));const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});const a=document.createElement('a');const url=URL.createObjectURL(blob);a.href=url;a.download='human_phase3_two_layer_audit_v2_20260829.json';a.style.display='none';document.body.appendChild(a);a.click();setTimeout(()=>{a.remove();URL.revokeObjectURL(url);},1500);};
document.querySelector('#clear').onclick=()=>{if(confirm("Clear only this browser's locally saved form values?")){localStorage.removeItem(key);location.reload();}};
</script></body></html>"""
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(page, encoding="utf-8")
    print(json.dumps({"combined_output": str(combined_path), "html_output": str(html_path), "records": len(first_rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
