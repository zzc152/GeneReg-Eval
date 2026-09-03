#!/usr/bin/env bash
# Argument: Mistral OpenCompass parent PID.
set -euo pipefail
ROOT=/workspace/zzc/GeneReg-Eval
PY=/workspace/zzc/envs/project_800/bin/python
OUT="$ROOT/outputs/human_strict_l0_v2_20260902"
DATA="$ROOT/data/benchmarks/human_strict_l0_v2_20260902/opencompass"
PID="$1"
while kill -0 "$PID" 2>/dev/null; do sleep 30; done

mkdir -p "$OUT/audits"
export_one() {
  local model="$1" run_dir="$2" pred_dir="$3"
  "$PY" "$ROOT/scripts/analysis/export_opencompass_l0_audit_cases_v1.py" \
    --model "$model" \
    --direction-data "$DATA/human_strict_l0_direction.jsonl" \
    --presence-data "$DATA/human_strict_l0_presence.jsonl" \
    --direction-prediction "$run_dir/predictions/$pred_dir/human_strict_l0_v2_direction.json" \
    --presence-prediction "$run_dir/predictions/$pred_dir/human_strict_l0_v2_presence.json" \
    --output "$OUT/audits/${model}_cases_v1.jsonl" \
    --stats-output "$OUT/audits/${model}_stats_v1.json"
}

export_one qwen2_5_7b "$OUT/qwen25_7b/20260902_173804" qwen2_5_7b_instruct_human_strict_l0_v2
export_one qwen2_5_32b_awq "$OUT/qwen25_32b_awq_retry2/20260902_174617" qwen2_5_32b_awq_human_strict_l0_v2
export_one llama_3_3_70b_awq "$OUT/llama33_70b_awq_retry2/20260902_174617" llama_3_3_70b_instruct_awq_human_strict_l0_v2
MISTRAL_RUN=$(find "$OUT/mistral_small_31_24b_retry3" -mindepth 1 -maxdepth 1 -type d | sort | tail -1)
export_one mistral_small_3_1_24b "$MISTRAL_RUN" mistral_small_3_1_24b_human_strict_l0_v2
touch "$OUT/FOUR_MODEL_AUDITS_COMPLETED"
