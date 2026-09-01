"""Run a bounded two-GPU Phase 3 extraction/verification pipeline remotely.

GPU A performs first-pass evidence extraction; GPU B independently audits each
completed batch with the PASS/REJECT second-pass verifier.  All batch outputs
are immutable and retained even if the run is interrupted.
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.request import urlopen


ROOT = Path("/workspace/zzc/GeneReg-Eval")
PYTHON = "/workspace/zzc/envs/project_800/bin/python"
VLLM = "/workspace/zzc/envs/project_800/bin/vllm"
MODEL_PATH = "/workspace/zzc/BioDesign-Agent/Qwen3.8-27B"


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def line_count(path: Path) -> int:
    with path.open(encoding="utf-8") as handle:
        return sum(bool(line.strip()) for line in handle)


def wait_api(port: int, timeout_seconds: int = 480) -> None:
    deadline = time.monotonic() + timeout_seconds
    url = f"http://127.0.0.1:{port}/v1/models"
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=5) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(3)
    raise TimeoutError(f"vLLM API did not become ready: {url}")


def launch_vllm(gpu: int, port: int, log_path: Path) -> tuple[subprocess.Popen, object]:
    env = dict(os.environ)
    env.update({
        "PATH": "/workspace/zzc/envs/project_800/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "CC": "/usr/bin/gcc", "CXX": "/usr/bin/g++", "CUDA_VISIBLE_DEVICES": str(gpu), "VLLM_USE_FLASHINFER_SAMPLER": "0",
    })
    log = log_path.open("xb")
    command = [VLLM, "serve", MODEL_PATH, "--served-model-name", "qwen35-fp8", "--host", "127.0.0.1", "--port", str(port), "--max-model-len", "8192", "--gpu-memory-utilization", "0.85", "--enforce-eager"]
    return subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT), log


def terminate(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=60)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=30)


def run_command(command: list[str], log_path: Path) -> None:
    with log_path.open("xb") as log:
        completed = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"Command failed ({completed.returncode}); see {log_path}")


def write_status(path: Path, status: dict) -> None:
    path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/intermediate/trrust_entity_both_mentioned_v1_20260826.jsonl")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--start-offset", type=int, default=0, help="Number of source records to skip before this run.")
    parser.add_argument("--max-records", type=int, default=1600, help="Maximum candidates made available to this run.")
    parser.add_argument("--chunk-size", type=int, default=50)
    parser.add_argument("--duration-hours", type=float, help="Stop launching new first-pass batches after this wall-clock budget.")
    parser.add_argument("--gpu-first", type=int, default=0)
    parser.add_argument("--gpu-second", type=int, default=3)
    parser.add_argument("--port-first", type=int, default=8001)
    parser.add_argument("--port-second", type=int, default=8002)
    args = parser.parse_args()
    if args.start_offset < 0 or args.max_records <= 0 or args.chunk_size <= 0:
        raise ValueError("start-offset must be non-negative; max-records and chunk-size must be positive")
    if args.duration_hours is not None and args.duration_hours <= 0:
        raise ValueError("duration-hours must be positive")
    run_dir = ROOT / args.run_dir
    if run_dir.exists():
        raise SystemExit(f"Refusing to overwrite existing run directory: {run_dir}")
    for name in ("inputs", "first_raw", "first_validated", "second_raw", "second_validated", "logs"):
        (run_dir / name).mkdir(parents=True, exist_ok=False)
    source = ROOT / args.input
    records = []
    seen = 0
    with source.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            if seen >= args.start_offset:
                records.append(line)
                if len(records) == args.max_records:
                    break
            seen += 1
    if not records:
        raise ValueError("No input records selected")
    batches: list[tuple[int, Path, int]] = []
    for index, start in enumerate(range(0, len(records), args.chunk_size)):
        batch_path = run_dir / "inputs" / f"batch_{index:04d}.jsonl"
        lines = records[start : start + args.chunk_size]
        batch_path.write_text("".join(lines), encoding="utf-8")
        batches.append((index, batch_path, len(lines)))
    status_path = run_dir / "status.json"
    status = {"run_version": "phase3_two_gpu_pipeline_v2_timed_20260830", "state": "starting", "input": str(source), "start_offset": args.start_offset, "candidate_records": len(records), "chunk_size": args.chunk_size, "duration_hours": args.duration_hours, "gpus": {"first": args.gpu_first, "second": args.gpu_second}, "batches_total": len(batches), "first_pass_completed_batches": [], "second_pass_completed_batches": [], "errors": []}
    write_status(status_path, status)
    deadline = None
    batch_queue: queue.Queue[tuple[int, Path, int] | None] = queue.Queue()
    worker_error: list[str] = []
    first_process: subprocess.Popen | None = None
    second_process: subprocess.Popen | None = None
    first_log = second_log = None

    def second_worker() -> None:
        try:
            while True:
                batch = batch_queue.get()
                if batch is None:
                    return
                index, _, expected = batch
                first_raw = run_dir / "first_raw" / f"batch_{index:04d}.jsonl"
                second_raw = run_dir / "second_raw" / f"batch_{index:04d}.jsonl"
                second_validated = run_dir / "second_validated" / f"batch_{index:04d}.jsonl"
                run_command([PYTHON, "scripts/review/run_phase3_second_pass_verifier_v1.py", "--input", relative(first_raw), "--output", relative(second_raw), "--base-url", f"http://127.0.0.1:{args.port_second}", "--model", "qwen35-fp8", "--max-tokens", "256"], run_dir / "logs" / f"second_{index:04d}.log")
                if line_count(second_raw) != expected:
                    raise RuntimeError(f"Second-pass batch {index} incomplete: {line_count(second_raw)} != {expected}")
                run_command([PYTHON, "scripts/review/validate_phase3_second_pass_verifier_v1.py", "--input", relative(second_raw), "--output", relative(second_validated)], run_dir / "logs" / f"second_validate_{index:04d}.log")
                status["second_pass_completed_batches"].append(index)
                write_status(status_path, status)
        except Exception as exc:
            worker_error.append(f"second-pass: {type(exc).__name__}: {exc}")

    try:
        first_process, first_log = launch_vllm(args.gpu_first, args.port_first, run_dir / "logs" / "vllm_first.log")
        second_process, second_log = launch_vllm(args.gpu_second, args.port_second, run_dir / "logs" / "vllm_second.log")
        wait_api(args.port_first); wait_api(args.port_second)
        deadline = None if args.duration_hours is None else time.monotonic() + args.duration_hours * 3600
        status["state"] = "running"; write_status(status_path, status)
        worker = threading.Thread(target=second_worker, name="second-pass", daemon=True)
        worker.start()
        launched_batches: list[tuple[int, Path, int]] = []
        for index, batch_path, expected in batches:
            if deadline is not None and time.monotonic() >= deadline:
                status["stop_reason"] = "duration_elapsed"
                write_status(status_path, status)
                break
            if worker_error:
                raise RuntimeError(worker_error[0])
            first_raw = run_dir / "first_raw" / f"batch_{index:04d}.jsonl"
            first_validated = run_dir / "first_validated" / f"batch_{index:04d}.jsonl"
            run_command([PYTHON, "scripts/review/run_deepseek_abstract_review_v1.py", "--input", relative(batch_path), "--output", relative(first_raw), "--base-url", f"http://127.0.0.1:{args.port_first}", "--model", "qwen35-fp8", "--max-tokens", "1536"], run_dir / "logs" / f"first_{index:04d}.log")
            if line_count(first_raw) != expected:
                raise RuntimeError(f"First-pass batch {index} incomplete: {line_count(first_raw)} != {expected}")
            run_command([PYTHON, "scripts/review/validate_abstract_review_v1.py", "--input", relative(first_raw), "--output", relative(first_validated)], run_dir / "logs" / f"first_validate_{index:04d}.log")
            status["first_pass_completed_batches"].append(index)
            write_status(status_path, status)
            batch_queue.put((index, batch_path, expected))
            launched_batches.append((index, batch_path, expected))
        batch_queue.put(None)
        worker.join()
        if worker_error:
            raise RuntimeError(worker_error[0])
        if not launched_batches:
            raise RuntimeError("No first-pass batch completed before the duration limit")
        if len(status["second_pass_completed_batches"]) != len(launched_batches):
            raise RuntimeError("Second pass did not complete every launched batch")
        stages = {"first_raw": "first_raw.jsonl", "first_validated": "first_validated.jsonl", "second_raw": "second_raw.jsonl", "second_validated": "second_validated.jsonl"}
        for directory, filename in stages.items():
            merged = run_dir / filename
            with merged.open("x", encoding="utf-8") as sink:
                for index, _, _ in launched_batches:
                    with (run_dir / directory / f"batch_{index:04d}.jsonl").open(encoding="utf-8") as source_handle:
                        for line in source_handle:
                            sink.write(line)
            if line_count(merged) != sum(expected for _, _, expected in launched_batches):
                raise RuntimeError(f"Merged {directory} count mismatch")
        queue_path = run_dir / "entity_risk_review_queue.jsonl"
        run_command([PYTHON, "scripts/review/build_phase3_entity_risk_queue_v1.py", "--input", relative(run_dir / "second_validated.jsonl"), "--output", relative(queue_path), "--supported-only"], run_dir / "logs" / "entity_queue.log")
        status["state"] = "complete"; status["completed_records"] = sum(expected for _, _, expected in launched_batches); status["entity_risk_queue_records"] = line_count(queue_path); status["finished_at_epoch"] = time.time(); write_status(status_path, status)
    except Exception as exc:
        status["state"] = "failed"; status["errors"].append(f"{type(exc).__name__}: {exc}"); status["finished_at_epoch"] = time.time(); write_status(status_path, status)
        raise
    finally:
        terminate(first_process); terminate(second_process)
        if first_log is not None:
            first_log.close()
        if second_log is not None:
            second_log.close()


if __name__ == "__main__":
    main()
