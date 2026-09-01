"""Build a deduplicated PMID/title/abstract input for local translation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path("/workspace/zzc/GeneReg-Eval")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--first-pass", nargs="+", required=True)
    parser.add_argument("--articles", default="data/intermediate/trrust_pubmed_articles_v1_20260826.jsonl")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = ROOT / args.output
    if output.exists():
        raise SystemExit(f"Refusing to overwrite existing output: {output}")
    articles = {
        str(row["pmid"]): row
        for line in (ROOT / args.articles).open(encoding="utf-8")
        if line.strip()
        for row in (json.loads(line),)
    }
    pmids: list[str] = []
    seen: set[str] = set()
    for path in args.first_pass:
        for line in (ROOT / path).open(encoding="utf-8"):
            if line.strip():
                pmid = str(json.loads(line)["input"]["pmid"])
                if pmid not in seen:
                    seen.add(pmid)
                    pmids.append(pmid)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        for pmid in pmids:
            article = articles.get(pmid)
            if not article or not article.get("abstract"):
                raise ValueError(f"Missing article text for PMID {pmid}")
            handle.write(json.dumps({"sample_id": f"phase3_second_pass_100_{pmid}", "pmid": pmid, "title": article.get("title") or "", "abstract": article["abstract"]}, ensure_ascii=False) + "\n")
    print(json.dumps({"output": str(output), "unique_pmids": len(pmids)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
