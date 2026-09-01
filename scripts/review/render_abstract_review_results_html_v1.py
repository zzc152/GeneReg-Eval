"""Render model abstract-review results for browser-based human inspection."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

ROOT = Path("/workspace/zzc/GeneReg-Eval")


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--articles", default="data/intermediate/trrust_pubmed_articles_v1_20260826.jsonl")
    args = parser.parse_args()
    output = ROOT / args.output
    if output.exists():
        raise SystemExit(f"Refusing to overwrite existing output: {output}")
    articles = {str(x["pmid"]): x for x in (json.loads(line) for line in (ROOT / args.articles).open(encoding="utf-8") if line.strip())}
    cards = []
    for row in (json.loads(line) for line in (ROOT / args.input).open(encoding="utf-8") if line.strip()):
        item, review = row["input"], row["review"]
        article = articles[item["pmid"]]
        status, route = review.get("support_status"), row.get("validation_route")
        errors = "<br>".join(esc(error) for error in row.get("validation_errors", [])) or "None / 无"
        condition = "<br>".join(f"{esc(key)}: {esc(value)}" for key, value in review.get("condition", {}).items() if value) or "null"
        cards.append(f'''<article class="card" data-status="{esc(status)}" data-route="{esc(route)}">
<h2>PMID {esc(item["pmid"])} <span>{esc(item["species"])} · {esc(item["relation"])} · {esc(route)}</span></h2>
<div class="candidate"><b>TRRUST candidate / 候选关系：</b>{esc(item["tf_mention"])} → {esc(item["object_mention"])} ({esc(item["relation"])})</div>
<div class="model"><b>Qwen result / Qwen 结论：</b>{esc(status)}<br><b>TF / Target：</b>{esc(review.get("extracted_tf_mention"))} → {esc(review.get("extracted_target_mention"))}<br><b>Evidence span / 证据片段：</b><mark>{esc(review.get("evidence_span"))}</mark><br><b>Condition / 条件：</b>{condition}<br><b>Model note / 模型备注：</b>{esc(review.get("review_note"))}<br><b>Validator / 验证结果：</b>{esc(route)}<br><b>Errors / 错误：</b>{errors}</div>
<h3>Title / 标题</h3><p>{esc(article.get("title"))}</p><h3>Abstract (source of record) / 英文摘要原文（唯一证据来源）</h3><p class="abstract">{esc(article.get("abstract"))}</p>
<p class="notice">请只依据英文 title/abstract 审阅；模型结论与 TRRUST 候选均不是原文证据。</p></article>''')
    page = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>Qwen Abstract Review Inspection</title><style>
body{{font-family:Arial,"Microsoft YaHei",sans-serif;margin:0;background:#f5f7fa;color:#172b4d}}header{{position:sticky;top:0;z-index:2;background:#102a43;color:white;padding:14px 5%}}main{{max-width:1300px;margin:auto;padding:18px}}select{{padding:6px}}.card{{background:#fff;margin:16px 0;padding:20px;border-radius:8px;box-shadow:0 1px 4px #ccd}}h2{{margin:0 0 12px;font-size:18px}}h2 span{{font-size:13px;color:#52606d}}.candidate{{background:#fff4cc;padding:10px;border-left:4px solid #f0b429}}.model{{margin-top:12px;background:#eef7ff;padding:12px;line-height:1.6}}mark{{background:#c6f6d5}}.abstract{{white-space:pre-wrap;line-height:1.65;background:#f8fafc;padding:14px}}.notice{{color:#9c4221;font-size:13px}}</style>
<header><b>Qwen Abstract Review Inspection / Qwen 摘要审阅结果核查</b><br><small>英文原文是唯一证据来源；页面仅展示模型判断与 deterministic validator 结果。</small><br>Support status <select id="status"><option value="">All</option><option>ABSTRACT_SUPPORTED</option><option>ABSTRACT_PARTIAL</option><option>ABSTRACT_INSUFFICIENT</option></select> Validation <select id="route"><option value="">All</option><option>VALID</option><option>REJECT</option></select></header><main>{''.join(cards)}</main><script>function f(){{document.querySelectorAll('.card').forEach(x=>x.hidden=(status.value&&x.dataset.status!==status.value)||(route.value&&x.dataset.route!==route.value))}}status.onchange=route.onchange=f;</script></html>'''
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding="utf-8")
    print(json.dumps({"output": str(output), "records": len(cards)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
