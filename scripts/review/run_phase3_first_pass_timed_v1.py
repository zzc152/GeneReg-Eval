"""Run a resumable, first-pass-only Phase 3 group on one remote GPU.

The planned record-key/PMID manifest is written before vLLM starts.  Raw
first-pass output is append-only; a completed PMID ledger is refreshed after
each small completed chunk, so interrupted groups can be resumed safely.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from urllib.request import urlopen


ROOT = Path("/workspace/zzc/GeneReg-Eval")
PYTHON = "/workspace/zzc/envs/project_800/bin/python"
VLLM = "/workspace/zzc/envs/project_800/bin/vllm"
MODEL = "/workspace/zzc/BioDesign-Agent/Qwen3.8-27B"


def count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(encoding="utf-8") as handle:
        return sum(bool(line.strip()) for line in handle)


def record_key(item: dict) -> str:
    species = item.get("species") or item.get("stratum", {}).get("species")
    return "|".join([species, item["tf_mention"], item["object_mention"], item["relation"], str(item["pmid"])])


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def wait_api(port: int) -> None:
    deadline = time.monotonic() + 480
    while time.monotonic() < deadline:
        try:
            if urlopen(f"http://127.0.0.1:{port}/v1/models", timeout=5).status == 200:
                return
        except Exception:
            time.sleep(3)
    raise TimeoutError(f"vLLM API did not become ready on port {port}")


def stop(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=60)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=30)


def refresh_completed_ledger(raw_path: Path, ledger_path: Path) -> tuple[int, int]:
    records: list[dict] = []
    pmids: set[str] = set()
    with raw_path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            item = row["input"]
            pmid = str(item["pmid"])
            records.append({"record_key": row["record_key"], "pmid": pmid})
            pmids.add(pmid)
    temporary = ledger_path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in records:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    temporary.replace(ledger_path)
    return len(records), len(pmids)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--input", default="data/intermediate/trrust_entity_both_mentioned_v1_20260826.jsonl")
    parser.add_argument("--start-offset", type=int, required=True)
    parser.add_argument("--records", type=int, required=True)
    parser.add_argument("--duration-hours", type=float, required=True)
    parser.add_argument("--chunk-size", type=int, default=25)
    parser.add_argument("--gpu", type=int, default=3)
    parser.add_argument("--port", type=int, default=8003)
    parser.add_argument("--resume", action="store_true", help="Resume an interrupted group from its immutable input manifest.")
    args = parser.parse_args()
    if args.start_offset < 0 or args.records <= 0 or args.chunk_size <= 0 or args.duration_hours <= 0:
        raise ValueError("offset must be non-negative; records, chunk-size, and duration-hours must be positive")

    run_dir = ROOT / args.run_dir
    input_path = run_dir / "input.jsonl"
    planned_path = run_dir / "planned_record_pmids.jsonl"
    raw_path = run_dir / "first_raw.jsonl"
    ledger_path = run_dir / "completed_record_pmids.jsonl"
    status_path = run_dir / "status.json"
    manifest_path = run_dir / "manifest.json"
    if run_dir.exists():
        if not args.resume:
            raise SystemExit(f"Refusing to overwrite existing run directory: {run_dir}; use --resume")
        if not input_path.exists() or not planned_path.exists() or not manifest_path.exists():
            raise SystemExit("Interrupted run lacks its immutable input/PMID manifest")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["planned_records"] != args.records or manifest["start_offset"] != args.start_offset:
            raise SystemExit("Resume arguments do not match the immutable planned group")
        selected = [line for line in input_path.open(encoding="utf-8") if line.strip()]
        if len(selected) != args.records or sha256(input_path) != manifest["input_sha256"]:
            raise SystemExit("Immutable input manifest integrity check failed")
        logs = run_dir / "logs"
        logs.mkdir(exist_ok=True)
        prior = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {}
        completed_records, completed_pmids = refresh_completed_ledger(raw_path, ledger_path) if raw_path.exists() else (0, 0)
        resume_history = list(prior.get("resume_history", []))
        resume_history.append({
            "started_at_epoch": time.time(),
            "gpu": args.gpu,
            "port": args.port,
            "duration_hours": args.duration_hours,
            "completed_records_at_start": completed_records,
        })
        state = dict(manifest, state="resuming", completed_records=completed_records, completed_unique_pmids=completed_pmids, stop_reason=None, errors=prior.get("errors", []), resumed_at_epoch=time.time(), active_gpu=args.gpu, active_port=args.port, resume_history=resume_history)
    else:
        run_dir.mkdir(parents=True)
        logs = run_dir / "logs"
        logs.mkdir()
        source = ROOT / args.input
        selected = []
        seen = 0
        with source.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                if seen >= args.start_offset:
                    selected.append(line)
                    if len(selected) == args.records:
                        break
                seen += 1
        if len(selected) != args.records:
            raise ValueError(f"could only select {len(selected)} records")
        input_path.write_text("".join(selected), encoding="utf-8")
        with planned_path.open("x", encoding="utf-8") as handle:
            for ordinal, line in enumerate(selected):
                item = json.loads(line)
                handle.write(json.dumps({"ordinal": ordinal, "record_key": record_key(item), "pmid": str(item["pmid"])}, ensure_ascii=False) + "\n")
        manifest = {
            "run_version": "phase3_first_pass_timed_v1_20260831",
            "stage": "first_pass_only",
            "input": str(source),
            "input_sha256": sha256(input_path),
            "start_offset": args.start_offset,
            "planned_records": args.records,
            "planned_unique_pmids": len({str(json.loads(line)["pmid"]) for line in selected}),
            "gpu": args.gpu,
            "port": args.port,
            "duration_hours": args.duration_hours,
            "chunk_size": args.chunk_size,
            "prompt_version": "phase3_adjudication_v4_no_tf_specific_perturbation_requirement",
        }
        write_json(manifest_path, manifest)
        state = dict(manifest, state="starting", completed_records=0, completed_unique_pmids=0, stop_reason=None, errors=[], active_gpu=args.gpu, active_port=args.port, resume_history=[])
    write_json(status_path, state)

    process: subprocess.Popen | None = None
    log_handle = None
    try:
        environment = dict(os.environ)
        environment.update({"PATH": "/workspace/zzc/envs/project_800/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", "CUDA_VISIBLE_DEVICES": str(args.gpu), "VLLM_USE_FLASHINFER_SAMPLER": "0"})
        log_handle = (logs / "vllm.log").open("a", encoding="utf-8")
        process = subprocess.Popen([VLLM, "serve", MODEL, "--served-model-name", "qwen35-fp8", "--host", "127.0.0.1", "--port", str(args.port), "--max-model-len", "8192", "--gpu-memory-utilization", "0.85", "--enforce-eager"], cwd=ROOT, env=environment, stdout=log_handle, stderr=subprocess.STDOUT)
        state["vllm_pid"] = process.pid
        wait_api(args.port)
        deadline = time.monotonic() + args.duration_hours * 3600
        state["state"] = "running"
        write_json(status_path, state)
        chunk_index = len(list(logs.glob("first_chunk_*.log")))
        while time.monotonic() < deadline:
            before = count(raw_path)
            if before >= args.records:
                state["stop_reason"] = "planned_records_complete"
                break
            command = [PYTHON, "scripts/review/run_deepseek_abstract_review_v1.py", "--input", str(input_path.relative_to(ROOT)), "--output", str(raw_path.relative_to(ROOT)), "--base-url", f"http://127.0.0.1:{args.port}", "--model", "qwen35-fp8", "--max-tokens", "1536", "--limit", str(args.chunk_size)]
            with (logs / f"first_chunk_{chunk_index:04d}.log").open("x", encoding="utf-8") as handle:
                result = subprocess.run(command, cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT, check=False)
            after = count(raw_path)
            completed_records, completed_pmids = refresh_completed_ledger(raw_path, ledger_path) if raw_path.exists() else (0, 0)
            state["completed_records"] = completed_records
            state["completed_unique_pmids"] = completed_pmids
            state["last_chunk"] = chunk_index
            write_json(status_path, state)
            if result.returncode != 0 or after <= before:
                state["stop_reason"] = "no_progress_or_runner_error"
                state["errors"].append(f"chunk={chunk_index}, returncode={result.returncode}, before={before}, after={after}")
                break
            chunk_index += 1
        if state["stop_reason"] is None:
            state["stop_reason"] = "duration_elapsed"
        state["state"] = "complete"
        state["finished_at_epoch"] = time.time()
        write_json(status_path, state)
    except Exception as exc:
        state["state"] = "failed"
        state["errors"].append(f"{type(exc).__name__}: {exc}")
        state["finished_at_epoch"] = time.time()
        write_json(status_path, state)
        raise
    finally:
        stop(process)
        if log_handle is not None:
            log_handle.close()


if __name__ == "__main__":
    main()
