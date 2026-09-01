"""Create a reproducible species × MoR stratified manual-review sample."""
from __future__ import annotations

import argparse
import csv
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
    parser.add_argument("--edge-input", default="data/intermediate/trrust_edge_pmid_v1_20260826.tsv")
    parser.add_argument("--article-input", default="data/intermediate/trrust_pubmed_articles_v1_20260826.jsonl")
    parser.add_argument("--sample-size", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260826)
    args = parser.parse_args()
    output, stats_output = ROOT / args.output, ROOT / args.stats_output
    if output.exists() or stats_output.exists():
        raise SystemExit("Refusing to overwrite an existing sample or stats file")

    articles: dict[str, dict] = {}
    with (ROOT / args.article_input).open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                article = json.loads(line)
                if article.get("abstract_status") == "ABSTRACT_AVAILABLE" and str(article.get("abstract") or "").strip():
                    articles[str(article["pmid"])] = article

    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    with (ROOT / args.edge_input).open(encoding="utf-8", newline="") as handle:
        for edge in csv.DictReader(handle, delimiter="\t"):
            pmid = str(edge["pmid"])
            stratum = (edge["species"], edge["relation"])
            if stratum in {(species, mor) for species in SPECIES for mor in MORS} and pmid in articles:
                groups[stratum].append(edge)

    requested = quotas(args.sample_size)
    rng, used_pmids, selected = random.Random(args.seed), set(), []
    population = {}
    for stratum, rows in groups.items():
        population[stratum] = {
            "edge_pmid_records": len(rows),
            "unique_pmids": len({row["pmid"] for row in rows}),
        }
    for stratum in requested:
        rows = list(groups[stratum])
        rng.shuffle(rows)
        picked = 0
        for edge in rows:
            if edge["pmid"] in used_pmids:
                continue
            article = articles[edge["pmid"]]
            selected.append({
                "sample_id": f"manual_review_v1_{len(selected) + 1:03d}",
                "stratum": {"species": stratum[0], "mor": stratum[1]},
                "pmid": edge["pmid"], "tf_mention": edge["tf_mention"],
                "object_mention": edge["object_mention"], "relation": edge["relation"],
                "title": article["title"], "abstract": article["abstract"],
                "journal": article.get("journal"), "publication_year": article.get("publication_year"),
            })
            used_pmids.add(edge["pmid"])
            picked += 1
            if picked == requested[stratum]:
                break
        if picked != requested[stratum]:
            raise SystemExit(f"Stratum {stratum} supplied {picked}/{requested[stratum]} unique PMID records")

    by_stratum = Counter((row["stratum"]["species"], row["stratum"]["mor"]) for row in selected)
    for row in selected:
        key = (row["stratum"]["species"], row["stratum"]["mor"])
        row["sampling_weight_edge_pmid"] = population[key]["edge_pmid_records"] / by_stratum[key]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        for row in selected:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    stats_output.parent.mkdir(parents=True, exist_ok=True)
    stats = {
        "sample_version": "manual_review_stratified_v1_20260826",
        "seed": args.seed, "sample_size": len(selected), "unique_pmids": len(used_pmids),
        "strata": [{"species": key[0], "mor": key[1], "sampled": by_stratum[key], **population[key]} for key in requested],
    }
    stats_output.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
