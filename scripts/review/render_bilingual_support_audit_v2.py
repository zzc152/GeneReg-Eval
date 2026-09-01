"""Render a deliberately minimal bilingual human audit page for TRRUST abstracts."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path("/workspace/zzc/GeneReg-Eval")


def source_mentions(candidates: list[str], title: str, abstract: str) -> list[str]:
    """Return only candidate aliases actually present in this article, as written."""
    source = f"{title}\n{abstract}"
    found: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, str) or not candidate.strip():
            continue
        # Word-like strings need boundaries; long names with spaces/punctuation do not.
        if re.fullmatch(r"[A-Za-z0-9_]+", candidate):
            pattern = rf"(?<![A-Za-z0-9_]){re.escape(candidate)}(?![A-Za-z0-9_])"
        else:
            pattern = re.escape(candidate)
        for match in re.finditer(pattern, source, flags=re.IGNORECASE):
            original = match.group(0)
            key = original.casefold()
            if key not in seen:
                found.append(original)
                seen.add(key)
    return found


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--translations", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--aliases", default="data/intermediate/gene_alias_mapping_v1_20260826.jsonl")
    parser.add_argument("--initial-reviews", help="Optional exported human-review JSON to prefill by sample_id")
    args = parser.parse_args()
    output = ROOT / args.output
    if output.exists():
        raise SystemExit(f"Refusing to overwrite existing output: {output}")
    with (ROOT / args.translations).open(encoding="utf-8") as handle:
        translations = {x["sample_id"]: x for x in (json.loads(line) for line in handle if line.strip())}
    initial_reviews: dict[str, dict[str, str]] = {}
    if args.initial_reviews:
        for row in json.loads((ROOT / args.initial_reviews).read_text(encoding="utf-8")):
            sample_id = row.get("sample_id")
            if isinstance(sample_id, str) and (row.get("abstract_supported") or row.get("evidence_span")):
                initial_reviews[sample_id] = {
                    "abstract_supported": row.get("abstract_supported") or "",
                    "evidence_span": row.get("evidence_span") or "",
                }
    with (ROOT / args.aliases).open(encoding="utf-8") as handle:
        aliases = {
            (x["species"], x.get("approved_symbol", x.get("mgi_symbol"))): x.get("mention_candidates", [])
            for x in (json.loads(line) for line in handle if line.strip())
        }
    records = []
    with (ROOT / args.input).open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            translation = translations.get(row["sample_id"], {})
            tf_aliases = aliases.get((row["stratum"]["species"], row["tf_mention"]), [row["tf_mention"]])
            target_aliases = aliases.get((row["stratum"]["species"], row["object_mention"]), [row["object_mention"]])
            # Strict both-mentioned samples carry the exact candidate that selected them.
            tf_candidates = [row["tf_matched_candidate"]] if row.get("tf_matched_candidate") else tf_aliases
            target_candidates = [row["target_matched_candidate"]] if row.get("target_matched_candidate") else target_aliases
            records.append({
                "sample_id": row["sample_id"], "pmid": row["pmid"], "species": row["stratum"]["species"],
                "mor": row["relation"], "tf": row["tf_mention"], "target": row["object_mention"],
                "tf_source_mentions": source_mentions(tf_candidates, row["title"], row["abstract"]),
                "target_source_mentions": source_mentions(target_candidates, row["title"], row["abstract"]),
                "title": row["title"], "abstract": row["abstract"], "title_zh": translation.get("title_zh", ""),
                "abstract_zh": translation.get("abstract_zh", ""), "translation_status": translation.get("translation_status", "MISSING"),
            })
    output.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(records, ensure_ascii=False).replace("</", "<\\/")
    output.write_text(PAGE.replace("__DATA__", data).replace("__INITIAL_REVIEWS__", json.dumps(initial_reviews, ensure_ascii=False)), encoding="utf-8")
    print(json.dumps({"output": str(output), "records": len(records), "prefilled_reviews": len(initial_reviews), "translated": sum(bool(x["abstract_zh"]) for x in records), "tf_source_matches": sum(bool(x["tf_source_mentions"]) for x in records), "target_source_matches": sum(bool(x["target_source_mentions"]) for x in records)}, ensure_ascii=False))


PAGE = r'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TRRUST 双语摘要支持性审阅</title><style>
:root{--ink:#172b4d;--bg:#f1f5f9;--line:#cbd5e1}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.65 Arial,"Microsoft YaHei",sans-serif}header{position:sticky;top:0;z-index:2;background:#082f49;color:#fff;padding:14px 4%}h1{font-size:20px;margin:0 0 4px}main{max-width:1500px;margin:auto;padding:18px}.box,.card{background:white;border:1px solid var(--line);border-radius:10px;padding:16px;margin-bottom:14px}.tools{display:flex;gap:8px;flex-wrap:wrap;align-items:center}select,button,textarea{font:inherit}select,button{padding:7px 10px;border:1px solid #94a3b8;border-radius:6px;background:#fff}.primary{background:#0369a1;color:#fff}.card[hidden]{display:none}.meta{display:flex;gap:6px;flex-wrap:wrap}.tag{padding:2px 8px;background:#e0f2fe;border-radius:999px;font-size:13px}.candidate{margin:10px 0;padding:11px;background:#fef3c7;border-left:4px solid #d97706}.mapping{margin:10px 0;padding:10px;background:#eff6ff;border-left:4px solid #2563eb}.mapping summary{cursor:pointer;font-weight:bold}.mapping code{font:13px/1.5 Consolas,monospace;word-break:break-word}.columns{display:grid;grid-template-columns:1fr 1fr;gap:14px}.source{white-space:pre-wrap;background:#f8fafc;padding:12px;border:1px solid #e2e8f0;border-radius:6px}.zh{color:#243b53}.hint{color:#9a3412;font-size:13px}.form{border-top:2px solid #0ea5e9;margin-top:15px;padding-top:12px}.form label{font-weight:bold;display:block;margin:10px 0 3px}.form textarea{display:block;width:100%;min-height:66px;border:1px solid #94a3b8;border-radius:5px;padding:8px}.count{font-weight:bold;color:#047857}@media(max-width:850px){.columns{grid-template-columns:1fr}}</style><body><header><h1>TRRUST relation × PubMed abstract：双语人工支持性审阅</h1><small>英文 Title / Abstract 是唯一证据来源；中文为机器辅助译文。对于每条候选，只判断它是否能由该摘要独立支持，并在支持时复制最小连续英文 evidence span。</small></header><main><section class="box"><b>规则：</b>选择“是”仅当摘要本身能支持 TF、Target 和给定的 Activation / Repression 方向；binding、ChIP、关联或共表达本身不足。若选择“否”，evidence span 留空。不要依赖 TRRUST 标签或外部知识。下方“实体映射”仅列出已收集的 symbol / alias，用于识别同一实体的不同写法，不是额外证据。</section><section class="box tools"><label>物种 <select id="species"><option value="">全部</option><option>human</option><option>mouse</option></select></label><label>MoR <select id="mor"><option value="">全部</option><option>Activation</option><option>Repression</option><option>Unknown</option></select></label><label>人工状态 <select id="state"><option value="">全部</option><option value="new">未审</option><option value="done">已审</option></select></label><button id="next" class="primary">下一条未审</button><button id="export">下载人工审阅 JSON</button><span id="count" class="count"></span></section><section id="cards"></section></main><script>
const DATA=__DATA__,KEY='trrust-bilingual-support-audit-v4:'+location.pathname;let saved={};try{saved=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){};const $=x=>document.querySelector(x),esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));const mentions=x=>Array.isArray(x)&&x.length?x.join(' · '):'未在 title/abstract 中匹配到已知别名';function val(id){return saved[id]||{abstract_supported:'',evidence_span:''}}function persist(id,k,v){let x=val(id);x[k]=v;saved[id]=x;localStorage.setItem(KEY,JSON.stringify(saved))}function render(){let a=$('#species').value,b=$('#mor').value,c=$('#state').value,done=DATA.filter(r=>val(r.sample_id).abstract_supported).length;$('#count').textContent=`已审 ${done} / ${DATA.length}`;$('#cards').innerHTML=DATA.map((r,i)=>{let x=val(r.sample_id),isDone=!!x.abstract_supported;if((a&&r.species!==a)||(b&&r.mor!==b)||(c==='new'&&isDone)||(c==='done'&&!isDone))return '';return `<article class="card" id="r${i}"><div class="meta"><span class="tag">#${i+1}</span><span class="tag">${esc(r.sample_id)}</span><span class="tag">PMID ${esc(r.pmid)}</span><span class="tag">${esc(r.species)}</span><span class="tag">${esc(r.mor)}</span><span class="tag">${isDone?'已审':'未审'}</span></div><div class="candidate"><b>TRRUST candidate / 待验证关系：</b>${esc(r.tf)} → ${esc(r.target)}；MoR: ${esc(r.mor)}</div><div class="mapping"><b>自动实体对齐 / Entity alignment</b><br><b>TF</b>：TRRUST <code>${esc(r.tf)}</code> → 原文命中 <code>${esc(mentions(r.tf_source_mentions))}</code><br><b>Target</b>：TRRUST <code>${esc(r.target)}</code> → 原文命中 <code>${esc(mentions(r.target_source_mentions))}</code></div><div class="columns"><section><h3>English original（唯一证据来源）</h3><div class="source"><b>Title</b>\n${esc(r.title)}\n\n<b>Abstract</b>\n${esc(r.abstract)}</div></section><section><h3>中文机器译文（仅辅助理解）</h3><div class="source zh"><b>标题</b>\n${esc(r.title_zh)||'译文缺失'}\n\n<b>摘要</b>\n${esc(r.abstract_zh)||'译文缺失'}</div><p class="hint">Evidence span 必须逐字复制自左侧英文原文。</p></section></div><div class="form"><label>该 abstract 是否独立支持此 TRRUST relation？</label><select data-id="${esc(r.sample_id)}" data-key="abstract_supported"><option value="">— 未判定 —</option><option value="YES" ${x.abstract_supported==='YES'?'selected':''}>YES：ABSTRACT_SUPPORTED</option><option value="NO" ${x.abstract_supported==='NO'?'selected':''}>NO：不支持</option></select><label>最小 evidence span（英文原文；仅 YES 时填写）</label><textarea data-id="${esc(r.sample_id)}" data-key="evidence_span" placeholder="复制最小、连续的英文原文片段">${esc(x.evidence_span)}</textarea></div></article>`}).join('')||'<p>没有符合筛选条件的记录。</p>';document.querySelectorAll('[data-id]').forEach(e=>e.oninput=e.onchange=()=>{persist(e.dataset.id,e.dataset.key,e.value);render()})}function out(){return DATA.map(r=>({sample_id:r.sample_id,pmid:r.pmid,species:r.species,tf:r.tf,target:r.target,mor:r.mor,...val(r.sample_id)}))}$('#export').onclick=()=>{let a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(out(),null,2)],{type:'application/json'}));a.download='human_bilingual_support_audit_v4.json';a.click();URL.revokeObjectURL(a.href)};$('#next').onclick=()=>{let i=DATA.findIndex(r=>!val(r.sample_id).abstract_supported);if(i>=0)document.querySelector('#r'+i)?.scrollIntoView({behavior:'smooth',block:'start'})};['species','mor','state'].forEach(x=>$('#'+x).onchange=render);render();</script></body></html>'''


if __name__ == "__main__":
    main()
