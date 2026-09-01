"""Render a browser-local audit workbook for Phase 3 first/second-pass rows."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


ROOT = Path("/workspace/zzc/GeneReg-Eval")


def load_jsonl(paths: list[str]) -> list[dict]:
    rows: list[dict] = []
    for path in paths:
        with (ROOT / path).open(encoding="utf-8") as handle:
            rows.extend(json.loads(line) for line in handle if line.strip())
    return rows


def esc(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def card(index: int, first: dict, second: dict, article: dict, translation: dict) -> str:
    item, review = first["input"], first["review"]
    verification = second.get("verification") or {}
    record_key = first["record_key"]
    payload = {
        "record_key": record_key,
        "pmid": str(item["pmid"]),
        "species": item.get("species"),
        "tf": item["tf_mention"],
        "target": item["object_mention"],
        "mor": item["relation"],
        "layer1_status": review.get("support_status"),
        "layer2_decision": verification.get("decision"),
    }
    title, abstract = article.get("title", ""), article.get("abstract", "")
    title_zh, abstract_zh = translation.get("title_zh", ""), translation.get("abstract_zh", "")
    translation_html = (
        f"<b>标题</b>\n{esc(title_zh)}\n\n<b>摘要</b>\n{esc(abstract_zh)}"
        if abstract_zh else "<i>该 PMID 没有可复用的既有中文译文；未重新翻译。</i>"
    )
    return f'''<article class="card" data-record='{esc(json.dumps(payload, ensure_ascii=False))}'>
<div class="meta"><span>#{index}</span><span>PMID {esc(item["pmid"])}</span><span>{esc(item.get("species"))}</span><span>{esc(item["relation"])}</span></div>
<div class="candidate"><b>TRRUST candidate / 待验证关系：</b>{esc(item["tf_mention"])} → {esc(item["object_mention"])}；MoR: {esc(item["relation"])}</div>
<div class="alignment"><b>Entity alignment / 实体对齐：</b><br>TF：TRRUST <code>{esc(item["tf_mention"])}</code> → 原文 <code>{esc(review.get("extracted_tf_mention"))}</code><br>Target：TRRUST <code>{esc(item["object_mention"])}</code> → 原文 <code>{esc(review.get("extracted_target_mention"))}</code></div>
<div class="model"><b>Layer 1 / 第一层：</b>{esc(review.get("support_status"))}<br><b>Evidence span：</b><mark>{esc(review.get("evidence_span") or "null")}</mark><br><b>Layer 2 / 第二层：</b>{esc(verification.get("decision"))}；validator={esc(second.get("verification_validation_route"))}<br><b>Entity identity risk / 实体识别风险：</b>{esc(verification.get("entity_identity_risk"))}；{esc(verification.get("entity_risk_note") or "—")}</div>
<div class="columns"><section><h3>English original（唯一证据来源）</h3><div class="source"><b>Title</b>\n{esc(title)}\n\n<b>Abstract</b>\n{esc(abstract)}</div></section><section><h3>中文机器译文（仅辅助理解）</h3><div class="source zh">{translation_html}</div><p class="hint">Evidence span 必须逐字复制自英文原文。</p></section></div>
<section class="form"><label>该 abstract 是否独立支持此 TRRUST relation？</label><select data-field="abstract_supported"><option value="">— 未判定 —</option><option value="YES">YES：ABSTRACT_SUPPORTED</option><option value="NO">NO：不独立支持</option></select><label>evidence span（英文原文；仅 YES 时填写）</label><textarea data-field="evidence_span" placeholder="复制一段连续的英文原文"></textarea></section>
</article>'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--first-pass", nargs="+", required=True)
    parser.add_argument("--second-pass", nargs="+", required=True)
    parser.add_argument("--articles", default="data/intermediate/trrust_pubmed_articles_v1_20260826.jsonl")
    parser.add_argument("--translations", nargs="*", default=[])
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = ROOT / args.output
    if output.exists():
        raise SystemExit(f"Refusing to overwrite existing output: {output}")
    first = load_jsonl(args.first_pass)
    second = {row["record_key"]: row for row in load_jsonl(args.second_pass)}
    if len(first) != len(second) or any(row["record_key"] not in second for row in first):
        raise ValueError("First/second pass rows are not a one-to-one match")
    articles = {str(row["pmid"]): row for row in load_jsonl([args.articles])}
    translations: dict[str, dict] = {}
    for row in load_jsonl(args.translations):
        if row.get("translation_status") == "OK":
            translations[str(row["pmid"])] = row
    cards = "\n".join(card(i, row, second[row["record_key"]], articles.get(str(row["input"]["pmid"]), {}), translations.get(str(row["input"]["pmid"]), {})) for i, row in enumerate(first, 1))
    storage_key = "phase3-audit:" + output.stem
    download_name = output.stem + "_human_review.json"
    page = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Phase 3 second-pass audit (100)</title><style>
body{margin:0;background:#f4f7fb;color:#172b4d;font:15px Arial,"Microsoft YaHei",sans-serif}header{position:sticky;top:0;z-index:4;padding:14px 5%;background:#102a43;color:#fff}main{max-width:1400px;margin:auto;padding:18px}.card{background:#fff;margin:16px 0;padding:18px;border-radius:8px;box-shadow:0 1px 5px #cbd5e1}.meta span{display:inline-block;background:#e6eef8;border-radius:12px;padding:3px 9px;margin:0 5px 8px 0;font-size:12px}.candidate{background:#fff4cc;padding:10px;border-left:4px solid #d69e2e}.alignment,.model{margin-top:10px;padding:10px;background:#eef6ff;border-radius:5px;line-height:1.6}.model{background:#f3e8ff}code{background:#fff;padding:1px 4px}h3{font-size:15px}.columns{display:grid;grid-template-columns:1fr 1fr;gap:14px}.source{white-space:pre-wrap;line-height:1.6;background:#f8fafc;border:1px solid #d9e2ec;padding:12px}.zh{color:#334e68}.hint{font-size:12px;color:#52606d}.form{margin-top:14px;padding:14px;background:#f0fdf4;border:1px solid #86efac;border-radius:6px}label{display:block;margin-top:8px;font-weight:bold}select,textarea{width:100%;box-sizing:border-box;margin-top:5px;padding:8px;font:inherit;border:1px solid #94a3b8;border-radius:5px}textarea{min-height:80px;resize:vertical}button{padding:8px 12px;margin:6px 8px 0 0;border:0;border-radius:5px;cursor:pointer}.primary{background:#38a169;color:#fff}.secondary{background:#e2e8f0}@media(max-width:850px){header{position:static}.columns{grid-template-columns:1fr}}</style></head><body><header><b>Phase 3 第二层审阅：100 条</b><br><small>英文 Title/Abstract 是唯一证据来源；模型输出仅供辅助。填写仅两项：是否支持、英文 evidence span。</small><br><button class="primary" id="export">导出审阅 JSON</button><button class="secondary" id="clear">清除本页浏览器缓存</button><span id="count"></span></header><main>__CARDS__</main><script>
const KEY='__STORAGE_KEY__';const fields=[...document.querySelectorAll('[data-field]')];let saved={};try{saved=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){};function row(f){return JSON.parse(f.closest('.card').dataset.record)}function updateCount(){const n=Object.values(saved).filter(x=>x.abstract_supported).length;document.querySelector('#count').textContent=` 已审 ${n} / __COUNT__`;}function restore(){for(const f of fields){const r=row(f);f.value=(saved[r.record_key]||{})[f.dataset.field]||''}updateCount()}function persist(){for(const f of fields){const r=row(f);saved[r.record_key]={...r,...(saved[r.record_key]||{}),[f.dataset.field]:f.value||null}}localStorage.setItem(KEY,JSON.stringify(saved));updateCount()}fields.forEach(f=>{f.addEventListener('input',persist);f.addEventListener('change',persist)});document.querySelector('#export').onclick=()=>{persist();const a=document.createElement('a'),u=URL.createObjectURL(new Blob([JSON.stringify(Object.values(saved),null,2)],{type:'application/json'}));a.href=u;a.download='__DOWNLOAD_NAME__';a.click();setTimeout(()=>URL.revokeObjectURL(u),1500)};document.querySelector('#clear').onclick=()=>{if(confirm('清除本页浏览器中保存的填写内容？')){localStorage.removeItem(KEY);saved={};restore()}};restore();
</script></body></html>""".replace("__CARDS__", cards).replace("__COUNT__", str(len(first))).replace("__STORAGE_KEY__", storage_key).replace("__DOWNLOAD_NAME__", download_name)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding="utf-8")
    print(json.dumps({"output": str(output), "records": len(first), "translations_reused": sum(bool(translations.get(str(row["input"]["pmid"]))) for row in first)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
