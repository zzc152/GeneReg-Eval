"""Run a bounded Phase 3 two-layer pipeline on one remote GPU."""
from __future__ import annotations

import argparse
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


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def count(path: Path) -> int:
    with path.open(encoding="utf-8") as handle:
        return sum(bool(line.strip()) for line in handle)


def status(path: Path, **fields: object) -> None:
    path.write_text(json.dumps(fields, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(command: list[str], log: Path) -> None:
    with log.open("x", encoding="utf-8") as handle:
        result = subprocess.run(command, cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT, check=False)
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}); see {log}")


def wait_api(port: int) -> None:
    deadline = time.monotonic() + 480
    while time.monotonic() < deadline:
        try:
            if urlopen(f"http://127.0.0.1:{port}/v1/models", timeout=5).status == 200:
                return
        except Exception:
            time.sleep(3)
    raise TimeoutError("vLLM API did not become ready")


def stop(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=60)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=30)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--input", default="data/intermediate/trrust_entity_both_mentioned_v1_20260826.jsonl")
    parser.add_argument("--start-offset", type=int, default=100)
    parser.add_argument("--records", type=int, default=300)
    parser.add_argument("--gpu", type=int, default=3)
    parser.add_argument("--port", type=int, default=8002)
    args = parser.parse_args()
    if args.start_offset < 0 or args.records <= 0:
        raise ValueError("start-offset must be non-negative and records positive")
    run_dir = ROOT / args.run_dir
    if run_dir.exists():
        raise SystemExit(f"Refusing to overwrite existing run directory: {run_dir}")
    (run_dir / "logs").mkdir(parents=True)
    source = ROOT / args.input
    selected: list[str] = []
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
    batch = run_dir / "input.jsonl"
    batch.write_text("".join(selected), encoding="utf-8")
    first_raw, first_validated = run_dir / "first_raw.jsonl", run_dir / "first_validated.jsonl"
    second_raw, second_validated = run_dir / "second_raw.jsonl", run_dir / "second_validated.jsonl"
    queue_path, status_path = run_dir / "entity_risk_review_queue.jsonl", run_dir / "status.json"
    state: dict[str, object] = {"run_version": "phase3_single_gpu_pipeline_v1_20260830", "state": "starting", "records": args.records, "start_offset": args.start_offset, "gpu": args.gpu, "port": args.port, "stages": []}
    status(status_path, **state)
    process: subprocess.Popen | None = None
    vllm_log = None
    try:
        environment = dict(os.environ)
        environment.update({"PATH": "/workspace/zzc/envs/project_800/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", "CUDA_VISIBLE_DEVICES": str(args.gpu), "VLLM_USE_FLASHINFER_SAMPLER": "0"})
        vllm_log = (run_dir / "logs" / "vllm.log").open("x", encoding="utf-8")
        process = subprocess.Popen([VLLM, "serve", MODEL, "--served-model-name", "qwen35-fp8", "--host", "127.0.0.1", "--port", str(args.port), "--max-model-len", "8192", "--gpu-memory-utilization", "0.85", "--enforce-eager"], cwd=ROOT, env=environment, stdout=vllm_log, stderr=subprocess.STDOUT)
        wait_api(args.port)
        state["state"] = "running"; state["stages"] = ["vllm_ready"]; status(status_path, **state)
        run([PYTHON, "scripts/review/run_deepseek_abstract_review_v1.py", "--input", relative(batch), "--output", relative(first_raw), "--base-url", f"http://127.0.0.1:{args.port}", "--model", "qwen35-fp8", "--max-tokens", "1536"], run_dir / "logs" / "first.log")
        if count(first_raw) != args.records:
            raise RuntimeError("first pass incomplete")
        run([PYTHON, "scripts/review/validate_abstract_review_v1.py", "--input", relative(first_raw), "--output", relative(first_validated)], run_dir / "logs" / "first_validator.log")
        state["stages"] = ["vllm_ready", "first_complete", "first_validated"]; status(status_path, **state)
        run([PYTHON, "scripts/review/run_phase3_second_pass_verifier_v1.py", "--input", relative(first_raw), "--output", relative(second_raw), "--base-url", f"http://127.0.0.1:{args.port}", "--model", "qwen35-fp8", "--max-tokens", "384"], run_dir / "logs" / "second.log")
        if count(second_raw) != args.records:
            raise RuntimeError("second pass incomplete")
        run([PYTHON, "scripts/review/validate_phase3_second_pass_verifier_v1.py", "--input", relative(second_raw), "--output", relative(second_validated)], run_dir / "logs" / "second_validator.log")
        run([PYTHON, "scripts/review/build_phase3_entity_risk_queue_v1.py", "--input", relative(second_validated), "--output", relative(queue_path), "--supported-only"], run_dir / "logs" / "entity_queue.log")
        state["state"] = "complete"; state["stages"] = ["vllm_ready", "first_complete", "first_validated", "second_complete", "second_validated", "entity_queue_complete"]; state["entity_risk_queue_records"] = count(queue_path); status(status_path, **state)
    except Exception as exc:
        state["state"] = "failed"; state["error"] = f"{type(exc).__name__}: {exc}"; status(status_path, **state)
        raise
    finally:
        stop(process)
        if vllm_log is not None:
            vllm_log.close()


if __name__ == "__main__":
    main()
