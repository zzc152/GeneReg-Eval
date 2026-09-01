"""Patch a rendered audit page to retain annotations and avoid textarea rerenders."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path("/workspace/zzc/GeneReg-Eval")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-html", required=True)
    parser.add_argument("--reviews", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = ROOT / args.output
    if output.exists():
        raise SystemExit(f"Refusing to overwrite existing output: {output}")
    annotations = json.loads((ROOT / args.reviews).read_text(encoding="utf-8"))
    initial = {
        x["sample_id"]: {"abstract_supported": x.get("abstract_supported") or "", "evidence_span": x.get("evidence_span") or ""}
        for x in annotations
        if x.get("sample_id") and (x.get("abstract_supported") or x.get("evidence_span"))
    }
    page = (ROOT / args.base_html).read_text(encoding="utf-8")
    replacements = [
        (",KEY='trrust-bilingual-support-audit-v4:'+location.pathname;", ",INITIAL_REVIEWS=" + json.dumps(initial, ensure_ascii=False) + ",KEY='trrust-bilingual-support-audit-v5:'+location.pathname;"),
        ("catch(e){};const $=", "catch(e){};if(!Object.keys(saved).length&&Object.keys(INITIAL_REVIEWS).length){saved=INITIAL_REVIEWS;localStorage.setItem(KEY,JSON.stringify(saved))};const $="),
        ("document.querySelectorAll('[data-id]').forEach(e=>e.oninput=e.onchange=()=>{persist(e.dataset.id,e.dataset.key,e.value);render()})", "document.querySelectorAll('[data-id]').forEach(e=>{if(e.tagName==='TEXTAREA'){e.oninput=()=>persist(e.dataset.id,e.dataset.key,e.value)}else{e.onchange=()=>{persist(e.dataset.id,e.dataset.key,e.value);render()}}})"),
        ("human_bilingual_support_audit_v4.json", "human_bilingual_support_audit_v5.json"),
    ]
    for old, new in replacements:
        if old not in page:
            raise SystemExit(f"Expected page fragment not found: {old[:60]}")
        page = page.replace(old, new, 1)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding="utf-8")
    print(json.dumps({"output": str(output), "prefilled_reviews": len(initial)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
