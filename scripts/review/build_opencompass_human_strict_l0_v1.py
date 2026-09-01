"""Materialize frozen strict L0 benchmark records as OpenCompass MCQ datasets.

The source labels remain in the strict benchmark JSONL.  The generated
questions deliberately omit both the TRRUST MoR and the human label: Qwen sees
only the title, abstract, and a regulator--target query.  Each task has two
deterministically counterbalanced answer positions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(os.environ.get("GENEREG_EVAL_ROOT", Path(__file__).resolve().parents[2]))
VERSION = "opencompass_human_strict_l0_v1_20260901"


def sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def question(article: dict[str, Any], candidate: dict[str, Any], task: str) -> str:
    if task == "KNOWN_DIRECTION":
        instruction = (
            "Based only on the title and abstract, which direction is directly "
            "supported for the specified regulator-target pair?"
        )
    elif task == "UNKNOWN_RELATION_PRESENCE":
        instruction = (
            "Based only on the title and abstract, is a transcriptional regulatory "
            "relationship directly supported for the specified regulator-target pair?"
        )
    else:
        raise ValueError(f"unknown task: {task}")
    return "\n".join((
        "You are evaluating one biomedical abstract. Use the abstract as the only evidence.",
        "Do not use external knowledge or infer a relation not stated in the text.",
        f"Title: {article['title']}",
        f"Abstract: {article['abstract']}",
        f"Candidate regulator: {candidate['tf_mention']}",
        f"Candidate target: {candidate['object_mention']}",
        instruction,
        "Choose exactly one option letter.",
    ))


def materialize(records: list[dict[str, Any]], sources: dict[str, dict[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Counter]]:
    datasets: dict[str, list[dict[str, Any]]] = {"direction": [], "presence": []}
    option_positions: dict[str, Counter] = {"direction": Counter(), "presence": Counter()}
    for row in records:
        sample_id = row["sample_id"]
        source = sources.get(sample_id)
        if source is None:
            raise ValueError(f"strict record missing frozen source: {sample_id}")
        article = source["article"]
        if not article.get("title") or not article.get("abstract"):
            raise ValueError(f"source lacks title/abstract: {sample_id}")
        task = row["l0"]["task"]
        label = row["l0"]["gold_label"]
        if task == "KNOWN_DIRECTION":
            bucket, labels = "direction", ["Activation", "Repression"]
        elif task == "UNKNOWN_RELATION_PRESENCE":
            bucket, labels = "presence", ["REGULATION_PRESENT", "NO_REGULATION"]
        else:
            raise ValueError(f"unexpected strict task: {task}")
        # Stable per-item shuffle avoids a fixed A/B label position while making
        # the dataset byte-identical when rebuilt from the same frozen sources.
        random.Random(f"{VERSION}:{sample_id}").shuffle(labels)
        answer = "A" if labels[0] == label else "B"
        option_positions[bucket][f"{answer}:{label}"] += 1
        datasets[bucket].append({
            "question": question(article, row["candidate"], task),
            "A": labels[0],
            "B": labels[1],
            "answer": answer,
            "benchmark_id": row["benchmark_id"],
            "sample_id": sample_id,
            "pmid": row["pmid"],
            "task": task,
            "gold_label": label,
            "source_record_key": row["record_key"],
        })
    return datasets, option_positions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", required=True)
    parser.add_argument("--frozen-source", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    strict_path = ROOT / args.strict
    source_path = ROOT / args.frozen_source
    output_dir = ROOT / args.output_dir
    if output_dir.exists():
        raise SystemExit(f"refusing to overwrite existing output directory: {output_dir}")
    strict = read_jsonl(strict_path)
    sources = {row["sample_id"]: row for row in read_jsonl(source_path)}
    datasets, positions = materialize(strict, sources)
    output_dir.mkdir(parents=True)
    paths = {}
    for bucket, rows in datasets.items():
        path = output_dir / f"human_strict_l0_{bucket}.jsonl"
        with path.open("x", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        paths[bucket] = str(path.relative_to(ROOT))
    manifest = {
        "version": VERSION,
        "source": {
            str(strict_path.relative_to(ROOT)): sha256(strict_path),
            str(source_path.relative_to(ROOT)): sha256(source_path),
        },
        "prompt_policy": "Title, abstract, and regulator-target query only. Neither TRRUST MoR nor human gold label is shown to the model.",
        "datasets": {key: len(value) for key, value in datasets.items()},
        "answer_position_counts": {key: dict(value) for key, value in positions.items()},
        "paths": paths,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
