"""Freeze TRRUST source tables and build a unified edge--PMID table.

The TRRUST source files have no header and use four columns:
regulator, object, relation, PMID.  The output expands multi-PMID cells,
deduplicates exact edge--PMID pairs, and keeps source hashes in a manifest.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
from collections import Counter
from datetime import date
from pathlib import Path


RELATIONS = {"Activation", "Repression", "Unknown"}
PMID_SPLIT = re.compile(r"[;,|\s]+")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_source(source: Path, species: str) -> tuple[list[dict[str, str]], dict[str, object]]:
    rows: list[dict[str, str]] = []
    stats: Counter[str] = Counter()
    with source.open("r", encoding="utf-8", newline="") as handle:
        for line_number, fields in enumerate(csv.reader(handle, delimiter="\t"), start=1):
            stats["source_lines"] += 1
            if len(fields) != 4:
                raise ValueError(f"{source}:{line_number}: expected 4 TSV fields, got {len(fields)}")
            regulator, object_mention, relation, pmid_cell = (field.strip() for field in fields)
            if not regulator or not object_mention or relation not in RELATIONS:
                raise ValueError(f"{source}:{line_number}: invalid regulator, object, or relation")
            pmids = [value for value in PMID_SPLIT.split(pmid_cell) if value]
            if not pmids or any(not value.isdigit() for value in pmids):
                raise ValueError(f"{source}:{line_number}: invalid PMID cell {pmid_cell!r}")
            stats["raw_relation_rows"] += 1
            stats["pmid_values_before_deduplication"] += len(pmids)
            for pmid in pmids:
                rows.append(
                    {
                        "species": species,
                        "regulator_mention": regulator,
                        "object_mention": object_mention,
                        "relation": relation,
                        "pmid": pmid,
                    }
                )
    return rows, dict(stats)


def species_statistics(rows: list[dict[str, str]], source_stats: dict[str, object]) -> dict[str, object]:
    edges = {(row["regulator_mention"], row["object_mention"], row["relation"]) for row in rows}
    return {
        **source_stats,
        "unique_edges": len(edges),
        "unique_edge_pmid_pairs": len(rows),
        "unique_regulators": len({row["regulator_mention"] for row in rows}),
        "unique_objects": len({row["object_mention"] for row in rows}),
        "unique_pmids": len({row["pmid"] for row in rows}),
        "relation_counts": dict(sorted(Counter(row["relation"] for row in rows).items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--human-source", type=Path, required=True)
    parser.add_argument("--mouse-source", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--version", default=f"trrust_edge_pmid_v1_{date.today():%Y%m%d}")
    args = parser.parse_args()

    raw_dir = args.project_root / "data" / "raw" / args.version
    intermediate_dir = args.project_root / "data" / "intermediate"
    manifest_dir = args.project_root / "data" / "manifests"
    output_tsv = intermediate_dir / f"{args.version}.tsv"
    stats_path = intermediate_dir / f"{args.version}_stats.json"
    manifest_path = manifest_dir / f"{args.version}.json"
    all_rows: list[dict[str, str]] = []
    sources: list[dict[str, object]] = []
    by_species: dict[str, object] = {}

    for species, source in (("human", args.human_source), ("mouse", args.mouse_source)):
        if not source.is_file():
            raise FileNotFoundError(source)
        frozen_path = raw_dir / source.name
        frozen_path.parent.mkdir(parents=True, exist_ok=True)
        if frozen_path.exists() and sha256(frozen_path) != sha256(source):
            raise FileExistsError(f"refusing to overwrite a different frozen file: {frozen_path}")
        if not frozen_path.exists():
            shutil.copy2(source, frozen_path)
        rows, source_stats = read_source(frozen_path, species)
        all_rows.extend(rows)
        by_species[species] = species_statistics(rows, source_stats)
        sources.append(
            {
                "species": species,
                "origin_path": str(source),
                "frozen_path": str(frozen_path.relative_to(args.project_root)),
                "sha256": sha256(frozen_path),
                "bytes": frozen_path.stat().st_size,
            }
        )

    deduplicated = sorted(
        {tuple(row[column] for column in ("species", "regulator_mention", "object_mention", "relation", "pmid")) for row in all_rows}
    )
    rows = [dict(zip(("species", "regulator_mention", "object_mention", "relation", "pmid"), item)) for item in deduplicated]
    intermediate_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)
    for output in (output_tsv, stats_path, manifest_path):
        if output.exists():
            raise FileExistsError(f"refusing to overwrite versioned artifact: {output}")
    with output_tsv.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("species", "regulator_mention", "object_mention", "relation", "pmid"), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)

    overall = species_statistics(rows, {"raw_relation_rows": sum(int(by_species[item]["raw_relation_rows"]) for item in by_species)})
    statistics = {"version": args.version, "species": by_species, "combined": overall}
    stats_path.write_text(json.dumps(statistics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "artifact_type": "trrust_edge_pmid",
        "version": args.version,
        "source_format": "headerless TSV: regulator, object, relation, PMID",
        "sources": sources,
        "outputs": [
            {"path": str(output_tsv.relative_to(args.project_root)), "sha256": sha256(output_tsv)},
            {"path": str(stats_path.relative_to(args.project_root)), "sha256": sha256(stats_path)},
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(statistics, indent=2, sort_keys=True))
    print(f"manifest={manifest_path}")


if __name__ == "__main__":
    main()
