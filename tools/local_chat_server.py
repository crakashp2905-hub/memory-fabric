#!/usr/bin/env python3
"""Serve a locally cached chat model over the Ollama endpoints the stack uses. Real inference.

    ~/vega-venv/bin/python tools/local_chat_server.py --model Qwen/Qwen2.5-1.5B-Instruct \\
        --name qwen2.5:1.5b --port 11434

Runs in the optional model environment (transformers + torch), never in the core.
Weights are read from the local Hugging Face cache only (``HF_HUB_OFFLINE=1`` is set
before loading), the server binds to 127.0.0.1, and ``/api/tags`` reports the SHA-256 of
the actual weight files as the digest, so the model team's provenance check sees the
real checkpoint. Decoding is greedy when temperature is 0, seeded otherwise. No
constrained decoding: a reply that is not valid JSON is returned as is, and the caller
records it as a failed call, never as a scripted answer.

Endpoints: ``GET /api/version``, ``GET /api/tags``, ``POST /api/chat`` (non-streaming;
``prompt_eval_count`` and ``eval_count`` are the real token counts).
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

os.environ.setdefault("HF_HUB_OFFLINE", "1")


def weights_digest(path: str) -> str:
    h = hashlib.sha256()
    for f in sorted(glob.glob(os.path.join(path, "*.safetensors"))):
        with open(f, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
    return h.hexdigest()


def resolve_local(repo: str) -> str:
    """A local directory, or the cached snapshot of a Hub repo id; never a download."""
    if os.path.isdir(repo):
        return repo
    cache = os.environ.get("HF_HUB_CACHE", os.path.expanduser("~/.cache/huggingface/hub"))
    snaps = sorted(glob.glob(os.path.join(cache, "models--" + repo.replace("/", "--"), "snapshots", "*")))
    if not snaps or not glob.glob(os.path.join(snaps[-1], "*.safetensors")):
        raise SystemExit(f"{repo} is not in the local cache; download it first (MODEL_NOT_RUN)")
    return snaps[-1]


class Model:
    def __init__(self, repo: str, threads: int) -> None:
        import torch
        import transformers
        torch.set_num_threads(threads)
        self.path = resolve_local(repo)
        self.tokenizer = transformers.AutoTokenizer.from_pretrained(self.path)
        self.model = transformers.AutoModelForCausalLM.from_pretrained(self.path, torch_dtype=torch.bfloat16)
        self.model.eval()
        self.digest = weights_digest(self.path)
        self.version = f"transformers-{transformers.__version__}/torch-{torch.__version__}"
        self.size = sum(os.path.getsize(f) for f in glob.glob(os.path.join(self.path, "*.safetensors")))
        self.lock = threading.Lock()
        self.torch = torch

    def chat(self, messages: list[dict[str, Any]], options: dict[str, Any], schema: Any) -> dict[str, Any]:
        msgs = [dict(m) for m in messages]
        if schema:
            msgs[0] = {**msgs[0], "content": msgs[0]["content"] + "\n\nReply with one JSON object only."}
        encoded = self.tokenizer.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt",
                                                     return_dict=True)
        ids = encoded["input_ids"]
        temperature = float(options.get("temperature", 0.0))
        gen: dict[str, Any] = {"max_new_tokens": int(options.get("num_predict", 256)), "do_sample": temperature > 0}
        if temperature > 0:
            gen["temperature"] = temperature
            self.torch.manual_seed(int(options.get("seed", 0)))
        with self.lock, self.torch.no_grad():
            out = self.model.generate(input_ids=ids, attention_mask=encoded["attention_mask"], **gen,
                                      pad_token_id=self.tokenizer.eos_token_id)
        new = out[0][ids.shape[1]:]
        return {"content": self.tokenizer.decode(new, skip_special_tokens=True).strip(),
                "prompt_eval_count": int(ids.shape[1]), "eval_count": int(new.shape[0])}


def serve(model: Model, name: str, port: int) -> None:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: Any) -> None:
            pass

        def _send(self, payload: dict[str, Any], status: int = 200) -> None:
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/api/version":
                self._send({"version": model.version})
            elif self.path == "/api/tags":
                self._send({"models": [{"name": name, "digest": f"sha256:{model.digest}", "size": model.size,
                                        "details": {"format": "safetensors", "family": "qwen2",
                                                    "parameter_size": name.split(":")[-1],
                                                    "quantization_level": "BF16"}}]})
            else:
                self._send({"error": "not found"}, 404)

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/api/chat":
                self._send({"error": "not found"}, 404)
                return
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            started = time.perf_counter()
            result = model.chat(req["messages"], req.get("options", {}), req.get("format"))
            self._send({"model": req.get("model", name), "message": {"role": "assistant", "content": result["content"]},
                        "prompt_eval_count": result["prompt_eval_count"], "eval_count": result["eval_count"],
                        "total_duration": int((time.perf_counter() - started) * 1e9), "done": True})

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", default="Qwen/Qwen2.5-1.5B-Instruct")
    parser.add_argument("--name", default="qwen2.5:1.5b")
    parser.add_argument("--port", type=int, default=11434)
    parser.add_argument("--threads", type=int, default=2)
    args = parser.parse_args()
    serve(Model(args.model, args.threads), args.name, args.port)


if __name__ == "__main__":
    main()
