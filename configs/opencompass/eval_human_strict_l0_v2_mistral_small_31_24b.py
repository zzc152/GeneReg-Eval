"""Frozen Human strict-L0 v2, official Mistral Small 3.1 24B, zero-shot MCQ."""
from opencompass.datasets import CustomDataset
from opencompass.datasets.custom import OptionSimAccEvaluator
from opencompass.models import VLLMwithChatTemplate
from opencompass.openicl.icl_inferencer import GenInferencer
from opencompass.openicl.icl_prompt_template import PromptTemplate
from opencompass.openicl.icl_retriever import ZeroRetriever

DATA_ROOT = "/workspace/zzc/GeneReg-Eval/data/benchmarks/human_strict_l0_v2_20260902/opencompass"
READER_CFG = dict(input_columns=["question", "A", "B"], output_column="answer")
INFER_CFG = dict(prompt_template=dict(type=PromptTemplate, template=dict(round=[dict(role="HUMAN", prompt="{question}\n\nA. {A}\nB. {B}\nAnswer with exactly A or B."), dict(role="BOT", prompt="{answer}")])), retriever=dict(type=ZeroRetriever), inferencer=dict(type=GenInferencer))
EVAL_CFG = dict(evaluator=dict(type=OptionSimAccEvaluator, options=["A", "B"]), pred_role="BOT")
datasets = [dict(type=CustomDataset, abbr="human_strict_l0_v2_direction", path=f"{DATA_ROOT}/human_strict_l0_direction.jsonl", reader_cfg=READER_CFG, infer_cfg=INFER_CFG, eval_cfg=EVAL_CFG), dict(type=CustomDataset, abbr="human_strict_l0_v2_presence", path=f"{DATA_ROOT}/human_strict_l0_presence.jsonl", reader_cfg=READER_CFG, infer_cfg=INFER_CFG, eval_cfg=EVAL_CFG)]
models = [dict(type=VLLMwithChatTemplate, abbr="mistral_small_3_1_24b_human_strict_l0_v2", path="/workspace/zzc/GeneReg-Eval/models/Mistral-Small-3.1-24B-Instruct-2503", max_seq_len=8192, max_out_len=8, batch_size=1, model_kwargs=dict(tensor_parallel_size=2, gpu_memory_utilization=0.94, max_model_len=8192, enforce_eager=True, disable_custom_all_reduce=True), generation_kwargs=dict(temperature=0.0), run_cfg=dict(num_gpus=2, num_procs=1))]
