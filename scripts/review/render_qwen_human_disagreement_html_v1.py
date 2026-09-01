"""Render a browser-local adjudication page for Qwen vs human benchmark disagreements."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path("/workspace/zzc/GeneReg-Eval")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--benchmark", required=True)
    parser.add_argument("--translations", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = ROOT / args.output
    if output.exists():
        raise SystemExit(f"Refusing to overwrite existing output: {output}")
    with (ROOT / args.benchmark).open(encoding="utf-8") as handle:
        human = {x["benchmark_id"]: x for x in (json.loads(line) for line in handle if line.strip())}
    with (ROOT / args.translations).open(encoding="utf-8") as handle:
        translations = {x["sample_id"]: x for x in (json.loads(line) for line in handle if line.strip())}
    selected = []
    with (ROOT / args.model).open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            sample_id = row["input"]["sample_id"]
            reference, review = human[sample_id], row["review"]
            model_yes = review.get("support_status") == "ABSTRACT_SUPPORTED" and row.get("validation_route") == "VALID"
            mismatch = bool(reference["human_abstract_supported"]) != model_yes
            rejected = row.get("validation_route") == "REJECT"
            if not (mismatch or rejected):
                continue
            translated = translations.get(sample_id, {})
            selected.append({
                "sample_id": sample_id, "pmid": reference["pmid"], "species": reference["species"], "mor": reference["trrust_mor"], "tf": reference["trrust_tf"], "target": reference["trrust_target"],
                "tf_source": reference.get("abstract_tf_mention"), "target_source": reference.get("abstract_target_mention"),
                "title": reference["title"], "abstract": reference["abstract"], "title_zh": translated.get("title_zh", ""), "abstract_zh": translated.get("abstract_zh", ""),
                "human_yes": reference["human_abstract_supported"], "human_span": reference.get("human_evidence_span"), "human_note": reference.get("human_review_note"),
                "model_status": review.get("support_status"), "model_span": review.get("evidence_span"), "model_note": review.get("review_note"), "model_tf": review.get("extracted_tf_mention"), "model_target": review.get("extracted_target_mention"),
                "validation_route": row.get("validation_route"), "validation_errors": row.get("validation_errors", []), "mismatch": mismatch, "rejected": rejected,
            })
    payload = json.dumps(selected, ensure_ascii=False).replace("</", "<\\/")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(PAGE.replace("__DATA__", payload), encoding="utf-8")
    print(json.dumps({"output": str(output), "records": len(selected), "mismatches": sum(x["mismatch"] for x in selected), "rejected": sum(x["rejected"] for x in selected)}, ensure_ascii=False))


PAGE = r'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Qwen × Human 分歧审阅</title><style>
:root{--ink:#172b4d;--bg:#f1f5f9;--line:#cbd5e1}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 Arial,"Microsoft YaHei",sans-serif}header{position:sticky;top:0;z-index:2;background:#082f49;color:#fff;padding:14px 4%}h1{font-size:20px;margin:0 0 4px}main{max-width:1500px;margin:auto;padding:18px}.box,.card{background:#fff;border:1px solid var(--line);border-radius:10px;padding:15px;margin-bottom:14px}.tools{display:flex;gap:8px;flex-wrap:wrap;align-items:center}select,button,textarea{font:inherit}select,button{padding:7px 10px;border:1px solid #94a3b8;border-radius:6px;background:#fff}.primary{background:#0369a1;color:white}.card[hidden]{display:none}.meta{display:flex;flex-wrap:wrap;gap:6px}.tag{background:#e0f2fe;border-radius:999px;padding:2px 8px;font-size:13px}.bad{background:#fee2e2;color:#991b1b}.candidate{background:#fef3c7;border-left:4px solid #d97706;padding:10px;margin:10px 0}.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.panel{padding:11px;border-radius:6px}.human{background:#ecfdf5}.model{background:#eff6ff}.source{white-space:pre-wrap;background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:12px}.zh{color:#243b53}.audit{border-top:2px solid #0ea5e9;margin-top:14px;padding-top:10px}.audit label{display:block;font-weight:bold;margin-top:8px}.audit select,.audit textarea{width:100%}.audit textarea{min-height:64px;padding:7px;border:1px solid #94a3b8;border-radius:5px}.saved{font-size:13px;color:#047857}@media(max-width:850px){.grid{grid-template-columns:1fr}}</style><body><header><h1>Qwen × Human 分歧审阅</h1><small>仅显示人机二分类不一致或 deterministic validator 拒绝的记录。英文 Title/Abstract 是唯一证据来源；中文译文仅辅助阅读。</small></header><main><section class="box"><b>判定说明：</b>人工 `YES` 与 Qwen `ABSTRACT_SUPPORTED + VALID` 视为正类。`PARTIAL` 与 `INSUFFICIENT` 均为负类。请判断人/模型哪方更符合“摘要是否独立支持 TRRUST relation”，并记录理由。</section><section class="box tools"><label>类型 <select id="f"><option value="">全部</option><option value="mismatch">仅人机分歧</option><option value="rejected">含 validator 拒绝</option></select></label><label>审阅状态 <select id="s"><option value="">全部</option><option value="new">未审</option><option value="done">已审</option></select></label><button id="next" class="primary">下一条未审</button><button id="export">下载 adjudication JSON</button><span id="count"></span></section><section id="cards"></section></main><script>
const DATA=__DATA__,KEY='qwen-human-disagreement-adjudication-v1:'+location.pathname;let saved={};try{saved=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){};const $=x=>document.querySelector(x),esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));function val(id){return saved[id]||{adjudication:'',note:''}}function store(id,k,v){let x=val(id);x[k]=v;saved[id]=x;localStorage.setItem(KEY,JSON.stringify(saved))}function render(){let f=$('#f').value,s=$('#s').value,done=DATA.filter(r=>val(r.sample_id).adjudication).length;$('#count').textContent=`已审 ${done} / ${DATA.length}`;$('#cards').innerHTML=DATA.map((r,i)=>{let a=val(r.sample_id),isDone=!!a.adjudication;if((f==='mismatch'&&!r.mismatch)||(f==='rejected'&&!r.rejected)||(s==='new'&&isDone)||(s==='done'&&!isDone))return '';return `<article class="card" id="r${i}"><div class="meta"><span class="tag">#${i+1}</span><span class="tag">PMID ${esc(r.pmid)}</span><span class="tag">${esc(r.species)} / ${esc(r.mor)}</span>${r.mismatch?'<span class="tag bad">人机分歧</span>':''}${r.rejected?'<span class="tag bad">validator REJECT</span>':''}</div><div class="candidate"><b>TRRUST candidate：</b>${esc(r.tf)} → ${esc(r.target)}；MoR: ${esc(r.mor)}<br><b>实体原文对齐：</b>${esc(r.tf)} → ${esc(r.tf_source)}；${esc(r.target)} → ${esc(r.target_source)}</div><div class="grid"><section class="panel human"><b>人工审阅</b><br>结论：${r.human_yes?'YES / SUPPORTED':'NO'}<br>Span：<mark>${esc(r.human_span)||'null'}</mark><br>备注：${esc(r.human_note)||'—'}</section><section class="panel model"><b>Qwen 输出</b><br>结论：${esc(r.model_status)}<br>实体：${esc(r.model_tf)} → ${esc(r.model_target)}<br>Span：<mark>${esc(r.model_span)||'null'}</mark><br>备注：${esc(r.model_note)||'—'}<br>Validator：${esc(r.validation_route)}；${(r.validation_errors||[]).map(esc).join('; ')||'—'}</section></div><div class="grid"><section><h3>English original</h3><div class="source"><b>Title</b>\n${esc(r.title)}\n\n<b>Abstract</b>\n${esc(r.abstract)}</div></section><section><h3>中文机器译文（辅助）</h3><div class="source zh"><b>标题</b>\n${esc(r.title_zh)||'译文缺失'}\n\n<b>摘要</b>\n${esc(r.abstract_zh)||'译文缺失'}</div></section></div><div class="audit"><label>裁决</label><select data-id="${esc(r.sample_id)}" data-k="adjudication"><option value="">— 未审 —</option>${['HUMAN_CORRECT','MODEL_CORRECT','BOTH_DEFENSIBLE','UNCERTAIN'].map(x=>`<option ${a.adjudication===x?'selected':''}>${x}</option>`).join('')}</select><label>裁决备注</label><textarea data-id="${esc(r.sample_id)}" data-k="note" placeholder="只写基于摘要原文的理由。">${esc(a.note)}</textarea><span class="saved">输入自动保存；textarea 不会重绘页面。</span></div></article>`}).join('')||'<p>没有符合筛选条件的记录。</p>';document.querySelectorAll('[data-id]').forEach(e=>{if(e.tagName==='TEXTAREA')e.oninput=()=>store(e.dataset.id,e.dataset.k,e.value);else e.onchange=()=>{store(e.dataset.id,e.dataset.k,e.value);render()}})}function out(){return DATA.map(r=>({sample_id:r.sample_id,pmid:r.pmid,tf:r.tf,target:r.target,mor:r.mor,...val(r.sample_id)}))}$('#export').onclick=()=>{let a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(out(),null,2)],{type:'application/json'}));a.download='qwen_human_disagreement_adjudication_v1.json';a.click();URL.revokeObjectURL(a.href)};$('#next').onclick=()=>{let i=DATA.findIndex(r=>!val(r.sample_id).adjudication);if(i>=0)document.querySelector('#r'+i)?.scrollIntoView({behavior:'smooth',block:'start'})};['f','s'].forEach(x=>$('#'+x).onchange=render);render();</script></body></html>'''


if __name__ == "__main__":
    main()
