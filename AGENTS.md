# GeneReg-Eval agent handoff

本文件供新 Codex 助手阅读。先读 `README.md`、`docs/migration_handoff.md` 与 `docs/decision_log.md`，再修改代码或数据。

## 工作约束

- 用户要求：**所有项目代码、抽取、测试和评测仅在远程服务器运行。** 本地只创建/编辑文件、下载产物和浏览 HTML。
- 不重跑或覆盖前序项目的结果文件；新项目应写出新的版本化产物。
- 不把 TRRUST 标签直接提供给抽取模型。模型输入仅为 PMID、标题、摘要；TRRUST 仅在抽取后用于对齐和误差分析。
- 不把“摘要确实支持”与“TRRUST 关系存在”混为同一个标签。
- 对 ontology 不确定的名称（如 AF1）不得靠常识强制判为 TF；先要求文本锚点，实体标准化是独立后续层。

## 已知远程环境

```text
SSH: gf@122.207.108.8, port 11922
前序仓库: /workspace/zzc/BioDesign-Agent
项目 Python: /workspace/zzc/envs/project_800/bin/python
Qwen 环境: /workspace/zzc/envs/... （启动前先检查 envs 目录）
TRRUST human PubMed 摘要: /workspace/zzc/BioDesign-Agent/data/trrust/trrust_human_pubmed_abstracts_v1.jsonl
```

远程环境缺少 `rg` 和 `pytest`。先用 `python -m py_compile`，再用最小 import/callable smoke test。vLLM 默认应保持关闭；仅在用户授权的批量抽取期间启动，结束后关闭。

用户曾配置服务器经由本地代理：远程 `127.0.0.1:17890` 对应本地代理 `127.0.0.1:7890`。使用前检查隧道是否仍存在，不要假设它持续可用。

## 数据与产物命名

- 原始不可变输入：`raw` 或 `source`。
- 人工标签：`human_review_*`。
- 含助手裁决的标签：必须显式称为 `human_assisted_*`，不伪装为纯人工 gold。
- 所有运行结果使用 `*_vN_YYYYMMDD`，绝不覆盖基线。

