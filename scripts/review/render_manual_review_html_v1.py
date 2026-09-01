"""Render a bilingual, browser-local manual-review HTML page."""
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
    parser.add_argument("--translations", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = ROOT / args.output
    if output.exists():
        raise SystemExit(f"Refusing to overwrite existing output: {output}")
    translations = {row["sample_id"]: row for row in (json.loads(line) for line in (ROOT / args.translations).open(encoding="utf-8") if line.strip())}
    cards = []
    for record in (json.loads(line) for line in (ROOT / args.input).open(encoding="utf-8") if line.strip()):
        translation = translations.get(record["sample_id"], {})
        species, mor = record["stratum"]["species"], record["stratum"]["mor"]
        cards.append(f'''<article class="card" data-species="{esc(species)}" data-mor="{esc(mor)}">
<h2>{esc(record["sample_id"])} · PMID {esc(record["pmid"])} <span>{esc(species)} / {esc(mor)}</span></h2>
<div class="candidate"><b>TRRUST candidate / 候选关系</b>: {esc(record["tf_mention"])} → {esc(record["object_mention"])} ({esc(record["relation"])})</div>
<p><b>Title / 标题</b><br>{esc(record["title"])}<br><span class="zh">{esc(translation.get("title_zh", "机器译文待生成"))}</span></p>
<div class="columns"><section><h3>Abstract (source evidence) / 英文原文（证据依据）</h3><p>{esc(record["abstract"])}</p></section><section><h3>Chinese machine translation / 中文机器译文</h3><p class="zh">{esc(translation.get("abstract_zh", "机器译文待生成"))}</p><p class="notice">译文仅辅助阅读；evidence span 必须逐字摘自英文原文。</p></section></div>
<div class="form"><label>Human decision / 人工结论 <select data-field="support_status"><option value="">未审阅</option><option>ABSTRACT_SUPPORTED</option><option>ABSTRACT_PARTIAL</option><option>ABSTRACT_INSUFFICIENT</option></select></label>
<label>Evidence span (English original) / 证据片段（英文原文）<textarea data-field="evidence_span"></textarea></label>
<label>Condition (English original or null) / 条件（英文原文或空）<textarea data-field="condition"></textarea></label>
<label>Notes / 审阅备注<textarea data-field="notes"></textarea></label></div></article>''')
    page = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>TRRUST Manual Review v1</title><style>
body{{font-family:Arial,"Microsoft YaHei",sans-serif;background:#f4f6f8;margin:0;color:#1d2733}} header{{position:sticky;top:0;background:#102a43;color:#fff;padding:16px 5%;z-index:2}}main{{max-width:1500px;margin:auto;padding:20px}}button,select{{padding:7px;margin:2px}}.card{{background:#fff;margin:16px 0;padding:20px;border-radius:8px;box-shadow:0 1px 4px #ccd}}h2{{font-size:18px;margin-top:0}}h2 span{{font-size:13px;color:#52606d}}.candidate{{background:#fff8db;padding:10px;border-left:4px solid #f0b429}}.columns{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}section{{background:#f8fafc;padding:12px;line-height:1.55}}.zh{{color:#243b53}}.notice{{color:#9c4221;font-size:13px}}label{{display:block;margin-top:10px;font-weight:bold}}textarea{{display:block;box-sizing:border-box;width:100%;min-height:55px;margin-top:4px;font-family:inherit}}@media(max-width:850px){{.columns{{grid-template-columns:1fr}}}}</style>
<header><b>TRRUST Abstract Manual Review / TRRUST 摘要人工审阅</b><br><small>100 unique PMIDs; balanced species × MoR strata. English original is the sole evidence source / 英文原文是唯一证据来源。</small><br><label>Species <select id="species"><option value="">All</option><option>human</option><option>mouse</option></select></label><label>MoR <select id="mor"><option value="">All</option><option>Activation</option><option>Repression</option><option>Unknown</option></select></label><button onclick="exportReviews()">Export reviews / 导出审阅 JSON</button></header><main>{''.join(cards)}</main>
<script>function filter(){{let s=species.value,m=mor.value;document.querySelectorAll('.card').forEach(c=>c.hidden=(s&&c.dataset.species!==s)||(m&&c.dataset.mor!==m));}} species.onchange=mor.onchange=filter;function exportReviews(){{let out=[];document.querySelectorAll('.card').forEach(c=>{{let x={{sample_id:c.querySelector('h2').innerText.split(' · ')[0],pmid:(c.querySelector('h2').innerText.match(/PMID (\\d+)/)||[])[1]}};c.querySelectorAll('[data-field]').forEach(e=>x[e.dataset.field]=e.value||null);out.push(x)}});let a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(out,null,2)],{{type:'application/json'}}));a.download='human_review_export.json';a.click();}}</script></html>'''
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding="utf-8")
    print(json.dumps({"output": str(output), "records": len(cards)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
