"""Frozen Human strict-L0 v2, Qwen2.5-7B-Instruct, zero-shot MCQ."""
from opencompass.datasets import CustomDataset
from opencompass.datasets.custom import OptionSimAccEvaluator
from opencompass.models import HuggingFacewithChatTemplate
from opencompass.openicl.icl_inferencer import GenInferencer
from opencompass.openicl.icl_prompt_template import PromptTemplate
from opencompass.openicl.icl_retriever import ZeroRetriever

DATA_ROOT = "/workspace/zzc/GeneReg-Eval/data/benchmarks/human_strict_l0_v2_20260902/opencompass"
READER_CFG = dict(input_columns=["question", "A", "B"], output_column="answer")
INFER_CFG = dict(prompt_template=dict(type=PromptTemplate, template=dict(round=[
    dict(role="HUMAN", prompt="{question}\n\nA. {A}\nB. {B}\nAnswer with exactly A or B."),
    dict(role="BOT", prompt="{answer}"),
])), retriever=dict(type=ZeroRetriever), inferencer=dict(type=GenInferencer))
EVAL_CFG = dict(evaluator=dict(type=OptionSimAccEvaluator, options=["A", "B"]), pred_role="BOT")
datasets = [
    dict(type=CustomDataset, abbr="human_strict_l0_v2_direction", path=f"{DATA_ROOT}/human_strict_l0_direction.jsonl", reader_cfg=READER_CFG, infer_cfg=INFER_CFG, eval_cfg=EVAL_CFG),
    dict(type=CustomDataset, abbr="human_strict_l0_v2_presence", path=f"{DATA_ROOT}/human_strict_l0_presence.jsonl", reader_cfg=READER_CFG, infer_cfg=INFER_CFG, eval_cfg=EVAL_CFG),
]
models = [dict(type=HuggingFacewithChatTemplate, abbr="qwen2_5_7b_instruct_human_strict_l0_v2", path="/workspace/zzc/BioDesign-Agent/Qwen2.5-7B-Instruct", model_kwargs=dict(device_map="auto", local_files_only=True), tokenizer_kwargs=dict(padding_side="left", truncation_side="left", local_files_only=True), generation_kwargs=dict(do_sample=False, temperature=0.0), max_seq_len=8192, max_out_len=8, batch_size=4, run_cfg=dict(num_gpus=1, num_procs=1))]
