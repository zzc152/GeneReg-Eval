"""Create a reproducible stratified audit sample restricted to both-mentioned rows."""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path("/workspace/zzc/GeneReg-Eval")
SPECIES = ("human", "mouse")
MORS = ("Activation", "Repression", "Unknown")


def quotas(total: int) -> dict[tuple[str, str], int]:
    strata = [(species, mor) for species in SPECIES for mor in MORS]
    base, remainder = divmod(total, len(strata))
    return {stratum: base + (index < remainder) for index, stratum in enumerate(strata)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--stats-output", required=True)
    parser.add_argument("--sample-size", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260827)
    parser.add_argument("--input", default="data/intermediate/trrust_entity_both_mentioned_v1_20260826.jsonl")
    parser.add_argument("--articles", default="data/intermediate/trrust_pubmed_articles_v1_20260826.jsonl")
    args = parser.parse_args()
    output, stats_output = ROOT / args.output, ROOT / args.stats_output
    if output.exists() or stats_output.exists():
        raise SystemExit("Refusing to overwrite existing output")
    with (ROOT / args.articles).open(encoding="utf-8") as handle:
        articles = {str(x["pmid"]): x for x in (json.loads(line) for line in handle if line.strip())}
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    with (ROOT / args.input).open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            key = (row.get("species"), row.get("relation"))
            if key in {(s, m) for s in SPECIES for m in MORS} and row.get("both_mentions_found") and str(row.get("pmid")) in articles:
                groups[key].append(row)
    wanted, rng, used_pmids, selected = quotas(args.sample_size), random.Random(args.seed), set(), []
    population = {key: {"both_mentioned_edge_pmids": len(rows), "unique_pmids": len({x["pmid"] for x in rows})} for key, rows in groups.items()}
    for key, amount in wanted.items():
        rows = list(groups[key]); rng.shuffle(rows); taken = 0
        for row in rows:
            if row["pmid"] in used_pmids:
                continue
            article = articles[row["pmid"]]
            selected.append({
                "sample_id": f"both_mentioned_support_audit_v1_{len(selected)+1:03d}", "stratum": {"species": key[0], "mor": key[1]},
                "pmid": row["pmid"], "tf_mention": row["tf_mention"], "object_mention": row["object_mention"], "relation": row["relation"],
                "tf_matched_candidate": row["tf_matched_candidate"], "target_matched_candidate": row["target_matched_candidate"],
                "title": article["title"], "abstract": article["abstract"], "journal": article.get("journal"), "publication_year": article.get("publication_year"),
            })
            used_pmids.add(row["pmid"]); taken += 1
            if taken == amount:
                break
        if taken != amount:
            raise SystemExit(f"{key}: sampled {taken}/{amount}")
    counts = Counter((x["stratum"]["species"], x["stratum"]["mor"]) for x in selected)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        for row in selected:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    stats = {"sample_version": "both_mentioned_support_audit_v1_20260827", "seed": args.seed, "sample_size": len(selected), "unique_pmids": len(used_pmids), "strata": [{"species": k[0], "mor": k[1], "sampled": counts[k], **population[k]} for k in wanted]}
    stats_output.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
