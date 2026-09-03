#!/usr/bin/env bash
# Arguments: <qwen32_opencompass_pid> <llama_opencompass_pid>
set -euo pipefail
ROOT=/workspace/zzc/GeneReg-Eval
OC=/workspace/zzc/envs/opencompass-py310/bin/opencompass
OUT="$ROOT/outputs/human_strict_l0_v2_20260902"

for pid in "$@"; do
  while kill -0 "$pid" 2>/dev/null; do
    sleep 30
  done
done

cd "$ROOT"
CUDA_VISIBLE_DEVICES=0,3 "$OC" \
  configs/opencompass/eval_human_strict_l0_v2_mistral_small_31_24b.py \
  -w outputs/human_strict_l0_v2_20260902/mistral_small_31_24b \
  --dump-eval-details > "$OUT/logs/mistral_small_31_24b.log" 2>&1
touch "$OUT/MISTRAL_RUN_COMPLETED"
