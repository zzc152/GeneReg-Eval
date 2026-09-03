#!/usr/bin/env bash
# Schedule the remaining v2 benchmark models without overlapping GPU0/GPU3.
# Arguments: <qwen7_opencompass_pid> <qwen32_opencompass_pid>
set -euo pipefail

ROOT=/workspace/zzc/GeneReg-Eval
OC=/workspace/zzc/envs/opencompass-py310/bin/opencompass
OUT="$ROOT/outputs/human_strict_l0_v2_20260902"
LOG="$OUT/logs"
QWEN7_PID="$1"
QWEN32_PID="$2"

wait_for_external_pid() {
  local pid="$1"
  while kill -0 "$pid" 2>/dev/null; do
    sleep 30
  done
}

cd "$ROOT"
wait_for_external_pid "$QWEN7_PID"
CUDA_VISIBLE_DEVICES=0 "$OC" \
  configs/opencompass/eval_human_strict_l0_v2_llama33_70b_awq.py \
  -w outputs/human_strict_l0_v2_20260902/llama33_70b_awq \
  --dump-eval-details > "$LOG/llama33_70b_awq.log" 2>&1

wait_for_external_pid "$QWEN32_PID"
CUDA_VISIBLE_DEVICES=0,3 "$OC" \
  configs/opencompass/eval_human_strict_l0_v2_mistral_small_31_24b.py \
  -w outputs/human_strict_l0_v2_20260902/mistral_small_31_24b \
  --dump-eval-details > "$LOG/mistral_small_31_24b.log" 2>&1

touch "$OUT/FOUR_MODEL_RUN_COMPLETED"
