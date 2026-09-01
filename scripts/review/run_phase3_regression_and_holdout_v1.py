"""Run Phase 3 regression plus an independent, stratified blind holdout.

This script starts and later stops only the vLLM process it creates.  It never
overwrites existing artifacts; rerun with new versioned output names instead.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import signal
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from urllib.request import urlopen

ROOT = Path("/workspace/zzc/GeneReg-Eval")
SPECIES, MORS = ("human", "mouse"), ("Activation", "Repression", "Unknown")


def quotas(total: int) -> dict[tuple[str, str], int]:
    strata = [(species, mor) for species in SPECIES for mor in MORS]
    base, remainder = divmod(total, len(strata))
    return {key: base + (index < remainder) for index, key in enumerate(strata)}


def create_holdout(args: argparse.Namespace) -> dict:
    sample_path, stats_path = ROOT / args.holdout_sample, ROOT / args.holdout_stats
    if sample_path.exists() or stats_path.exists():
        raise SystemExit("Refusing to overwrite an existing holdout sample/stats artifact")
    with (ROOT / args.calibration_input).open(encoding="utf-8") as handle:
        excluded_pmids = {str(json.loads(line)["pmid"]) for line in handle if line.strip()}
    with (ROOT / args.articles).open(encoding="utf-8") as handle:
        articles = {str(x["pmid"]): x for x in (json.loads(line) for line in handle if line.strip())}
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    with (ROOT / args.holdout_source).open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            key, pmid = (row.get("species"), row.get("relation")), str(row.get("pmid"))
            article = articles.get(pmid)
            if key in {(s, m) for s in SPECIES for m in MORS} and row.get("both_mentions_found") and pmid not in excluded_pmids and article and article.get("abstract"):
                groups[key].append(row)
    rng, used, selected, requested = random.Random(args.seed), set(), [], quotas(args.holdout_size)
    for key, amount in requested.items():
        rows = list(groups[key]); rng.shuffle(rows); taken = 0
        for row in rows:
            if row["pmid"] in used:
                continue
            article = articles[str(row["pmid"])]
            selected.append({
                "sample_id": f"phase3_holdout_v1_{len(selected)+1:03d}", "species": key[0], "stratum": {"species": key[0], "mor": key[1]},
                "pmid": str(row["pmid"]), "tf_mention": row["tf_mention"], "object_mention": row["object_mention"], "relation": row["relation"],
                "tf_matched_candidate": row.get("tf_matched_candidate"), "target_matched_candidate": row.get("target_matched_candidate"),
                "title": article["title"], "abstract": article["abstract"], "journal": article.get("journal"), "publication_year": article.get("publication_year"),
            })
            used.add(row["pmid"]); taken += 1
            if taken == amount:
                break
        if taken != amount:
            raise SystemExit(f"Holdout stratum {key} only supplied {taken}/{amount} unique PMIDs")
    sample_path.parent.mkdir(parents=True, exist_ok=True)
    sample_path.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in selected) + "\n", encoding="utf-8")
    counts = Counter((x["species"], x["relation"]) for x in selected)
    stats = {"sample_version": "phase3_holdout_v1_20260828", "seed": args.seed, "sample_size": len(selected), "unique_pmids": len(used), "excluded_calibration_pmids": len(excluded_pmids), "strata": [{"species": k[0], "mor": k[1], "sampled": counts[k]} for k in requested]}
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return stats


def wait_for_api(base_url: str, process: subprocess.Popen[bytes], timeout: int = 360) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"vLLM exited before readiness with code {process.returncode}")
        try:
            with urlopen(base_url.rstrip("/") + "/v1/models", timeout=5) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(5)
    raise TimeoutError("vLLM did not become ready within timeout")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--calibration-input", default="data/intermediate/both_mentioned_support_audit_sample_v1_20260827.jsonl")
    p.add_argument("--holdout-source", default="data/intermediate/trrust_entity_both_mentioned_v1_20260826.jsonl")
    p.add_argument("--articles", default="data/intermediate/trrust_pubmed_articles_v1_20260826.jsonl")
    p.add_argument("--holdout-size", type=int, default=120); p.add_argument("--seed", type=int, default=20260828)
    p.add_argument("--holdout-sample", required=True); p.add_argument("--holdout-stats", required=True)
    p.add_argument("--regression-output", required=True); p.add_argument("--holdout-output", required=True)
    p.add_argument("--regression-validated", required=True); p.add_argument("--regression-evaluation", required=True); p.add_argument("--regression-report", required=True)
    p.add_argument("--status-output", required=True); p.add_argument("--gpu", default="0"); p.add_argument("--base-url", default="http://127.0.0.1:8001")
    p.add_argument("--vllm", default="/workspace/zzc/envs/project_800/bin/vllm"); p.add_argument("--model-path", default="/workspace/zzc/BioDesign-Agent/Qwen3.8-27B")
    p.add_argument("--served-model-name", default="qwen35-fp8"); p.add_argument("--python", default="/workspace/zzc/envs/project_800/bin/python")
    p.add_argument("--runner", default="scripts/review/run_deepseek_abstract_review_v1.py"); p.add_argument("--validator", default="scripts/review/validate_abstract_review_v1.py"); p.add_argument("--evaluator", default="scripts/review/evaluate_qwen_human_benchmark_v2.py")
    p.add_argument("--benchmark-v2", default="data/intermediate/human_review_benchmark_v2_20260828.jsonl"); p.add_argument("--log-dir", default="logs")
    args = p.parse_args()
    all_outputs = [args.regression_output, args.holdout_output, args.regression_validated, args.regression_evaluation, args.regression_report, args.status_output]
    if any((ROOT / item).exists() for item in all_outputs):
        raise SystemExit("Refusing to overwrite one or more run outputs")
    holdout = create_holdout(args)
    log_dir = ROOT / args.log_dir; log_dir.mkdir(parents=True, exist_ok=True)
    vllm_log = (log_dir / "phase3_regression_holdout_v1_20260828_vllm.log").open("xb")
    env = dict(os.environ); env.update({"CUDA_VISIBLE_DEVICES": args.gpu, "VLLM_USE_FLASHINFER_SAMPLER": "0", "CC": "/usr/bin/gcc", "CXX": "/usr/bin/g++"})
    vllm = subprocess.Popen([args.vllm, "serve", args.model_path, "--served-model-name", args.served_model_name, "--host", "127.0.0.1", "--port", "8001", "--max-model-len", "8192", "--gpu-memory-utilization", "0.85", "--enforce-eager"], cwd=ROOT, env=env, stdout=vllm_log, stderr=subprocess.STDOUT)
    status = {"run_version": "phase3_regression_holdout_v1_20260828", "holdout": holdout, "vllm_pid": vllm.pid, "state": "started"}
    try:
        wait_for_api(args.base_url, vllm)
        common = [args.python, str(ROOT / args.runner), "--base-url", args.base_url, "--model", args.served_model_name, "--max-tokens", "1536"]
        regression_log = (log_dir / "phase3_regression_v3_20260828.log").open("xb")
        holdout_log = (log_dir / "phase3_holdout_v1_20260828.log").open("xb")
        regression = subprocess.Popen(common + ["--input", args.calibration_input, "--output", args.regression_output], cwd=ROOT, stdout=regression_log, stderr=subprocess.STDOUT)
        holdout_run = subprocess.Popen(common + ["--input", args.holdout_sample, "--output", args.holdout_output], cwd=ROOT, stdout=holdout_log, stderr=subprocess.STDOUT)
        regression_code, holdout_code = regression.wait(), holdout_run.wait()
        regression_log.close(); holdout_log.close()
        if regression_code or holdout_code:
            raise RuntimeError(f"runner exit codes: regression={regression_code}, holdout={holdout_code}")
        subprocess.run([args.python, str(ROOT / args.validator), "--input", args.regression_output, "--output", args.regression_validated], cwd=ROOT, check=True)
        subprocess.run([args.python, str(ROOT / args.evaluator), "--model", args.regression_validated, "--benchmark", args.benchmark_v2, "--output", args.regression_evaluation, "--report-output", args.regression_report], cwd=ROOT, check=True)
        status["state"] = "complete"; status["regression_records"] = sum(1 for x in (ROOT / args.regression_output).open(encoding="utf-8") if x.strip()); status["holdout_records"] = sum(1 for x in (ROOT / args.holdout_output).open(encoding="utf-8") if x.strip())
    except Exception as error:
        status["state"] = "failed"; status["error"] = f"{type(error).__name__}: {error}"; raise
    finally:
        if vllm.poll() is None:
            vllm.send_signal(signal.SIGTERM)
            try: vllm.wait(timeout=45)
            except subprocess.TimeoutExpired: vllm.kill()
        vllm_log.close(); status["vllm_returncode"] = vllm.poll(); status["finished_at_epoch"] = time.time()
        status_path = ROOT / args.status_output; status_path.parent.mkdir(parents=True, exist_ok=True); status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
