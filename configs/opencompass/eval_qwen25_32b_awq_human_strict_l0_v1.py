"""OpenCompass zero-shot L0 benchmark for local Qwen2.5-32B-AWQ."""
import os

from opencompass.datasets import CustomDataset
from opencompass.datasets.custom import OptionSimAccEvaluator
from opencompass.models import HuggingFacewithChatTemplate
from opencompass.openicl.icl_inferencer import GenInferencer
from opencompass.openicl.icl_prompt_template import PromptTemplate
from opencompass.openicl.icl_retriever import ZeroRetriever


DATA_ROOT = "/workspace/zzc/GeneReg-Eval/data/benchmarks/opencompass_human_strict_l0_v1_20260901"
READER_CFG = dict(input_columns=["question", "A", "B"], output_column="answer")
INFER_CFG = dict(
    prompt_template=dict(
        type=PromptTemplate,
        template=dict(round=[
            dict(role="HUMAN", prompt="{question}\n\nA. {A}\nB. {B}\nAnswer with exactly A or B."),
            dict(role="BOT", prompt="{answer}"),
        ]),
    ),
    retriever=dict(type=ZeroRetriever),
    inferencer=dict(type=GenInferencer),
)
EVAL_CFG = dict(evaluator=dict(type=OptionSimAccEvaluator, options=["A", "B"]), pred_role="BOT")

datasets = [
    dict(
        type=CustomDataset,
        abbr="human_strict_l0_direction_v1",
        path=f"{DATA_ROOT}/human_strict_l0_direction.jsonl",
        reader_cfg=READER_CFG,
        infer_cfg=INFER_CFG,
        eval_cfg=EVAL_CFG,
    ),
    dict(
        type=CustomDataset,
        abbr="human_strict_l0_presence_v1",
        path=f"{DATA_ROOT}/human_strict_l0_presence.jsonl",
        reader_cfg=READER_CFG,
        infer_cfg=INFER_CFG,
        eval_cfg=EVAL_CFG,
    ),
]

models = [
    dict(
        type=HuggingFacewithChatTemplate,
        abbr="qwen2_5_32b_awq_human_strict_l0_v1",
        path="/workspace/zzc/BioDesign-Agent/Qwen2.5-32B-AWQ",
        model_kwargs=dict(device_map="auto", local_files_only=True),
        tokenizer_kwargs=dict(
            padding_side="left", truncation_side="left", local_files_only=True),
        generation_kwargs=dict(do_sample=False, temperature=0.0),
        max_seq_len=8192,
        max_out_len=8,
        batch_size=1,
        run_cfg=dict(num_gpus=1, num_procs=1),
    )
]

if os.getenv("GENEREG_OPENCOMPASS_SMOKE") == "1":
    for dataset in datasets:
        dataset["abbr"] += "_smoke4"
        dataset["reader_cfg"] = dict(READER_CFG, test_range="[0:4]")

del os
