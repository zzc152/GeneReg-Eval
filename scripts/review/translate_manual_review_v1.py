"""Translate manual-review title/abstract text with the local Qwen vLLM API."""
from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib import request

ROOT = Path("/workspace/zzc/GeneReg-Eval")
PROMPT = """Translate the supplied biomedical article title and abstract from English into accurate Simplified Chinese. Preserve gene/protein symbols, abbreviations, PMID-independent scientific terminology, numbers, and hedging. Do not add interpretation or facts. Return JSON only: {\"title_zh\": string, \"abstract_zh\": string}."""


def call(base_url: str, record: dict) -> tuple[str, dict]:
    body = {"model": "qwen35-fp8", "temperature": 0.0, "top_p": 0.9, "max_tokens": 1024,
            "chat_template_kwargs": {"enable_thinking": False}, "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": PROMPT}, {"role": "user", "content": "Title:\n" + record["title"] + "\n\nAbstract:\n" + record["abstract"]}]}
    req = request.Request(base_url.rstrip("/") + "/v1/chat/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    raw = json.loads(request.urlopen(req, timeout=300).read())["choices"][0]["message"]["content"]
    parsed = json.loads(raw)
    if not isinstance(parsed.get("title_zh"), str) or not isinstance(parsed.get("abstract_zh"), str):
        raise ValueError("translation JSON lacks title_zh or abstract_zh")
    return raw, parsed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    completed = set()
    if output.exists():
        completed = {json.loads(line)["sample_id"] for line in output.open(encoding="utf-8") if line.strip()}
    pending = [json.loads(line) for line in (ROOT / args.input).open(encoding="utf-8") if line.strip() and json.loads(line)["sample_id"] not in completed]
    def translate(record: dict) -> dict:
        try:
            raw, translated = call(args.base_url, record)
            return {"sample_id": record["sample_id"], "pmid": record["pmid"], "translation_status": "OK", **translated, "raw_output": raw}
        except Exception as error:
            return {"sample_id": record["sample_id"], "pmid": record["pmid"], "translation_status": "ERROR", "error": f"{type(error).__name__}: {error}"}
    with output.open("a", encoding="utf-8") as sink, ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(translate, record): record["sample_id"] for record in pending}
        for future in as_completed(futures):
            result = future.result()
            sink.write(json.dumps(result, ensure_ascii=False) + "\n")
            sink.flush()
            print(result["sample_id"], result["translation_status"], flush=True)


if __name__ == "__main__":
    main()
