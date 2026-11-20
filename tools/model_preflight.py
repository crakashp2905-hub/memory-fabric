#!/usr/bin/env python3
"""List the local models already installed, without downloading anything (W12-01).

    python tools/model_preflight.py                         # what is installed here
    python tools/model_preflight.py --require qwen2.5:1.5b  # NOT_RUN unless it is
    python tools/model_preflight.py --out preflight.json

Talks only to a loopback Ollama server (127.0.0.0/8, ::1 or localhost); any other
host is refused before a connection is attempted. It never pulls a model and never
substitutes a scripted agent: if the runtime is not running, or a required model
is not installed, the status is ``REAL_AGENT_NOT_RUN`` with the reason, and the
exit code is 3 so a workflow can tell "no model here" apart from a failure (1).

For each installed model the inventory carries its name, content digest,
quantization, parameter size and family, which is what a later inference record
pins (W12-02).
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from memory_fabric.adapters.ollama import DEFAULT_HOST, OllamaClient, OllamaError  # noqa: E402

SCHEMA_ID = "memory-fabric.model-preflight.v1"
EXIT_AVAILABLE, EXIT_ERROR, EXIT_NOT_RUN = 0, 1, 3


class NonLocalHostError(ValueError):
    """Raised for any host that is not loopback."""


def require_loopback(host: str) -> str:
    parsed = urllib.parse.urlsplit(host)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise NonLocalHostError(f"not an http(s) URL: {host!r}")
    name = parsed.hostname
    if name == "localhost":
        return host.rstrip("/")
    try:
        address = ipaddress.ip_address(name)
    except ValueError as exc:
        raise NonLocalHostError(f"only loopback hosts are allowed, got {name!r}") from exc
    if not address.is_loopback:
        raise NonLocalHostError(f"only loopback hosts are allowed, got {name!r}")
    return host.rstrip("/")


def _runtime_version(host: str) -> str | None:
    try:
        with urllib.request.urlopen(host + "/api/version", timeout=5) as response:
            version = json.load(response).get("version")
    except Exception:  # noqa: BLE001 - the version is informative, never required
        return None
    return str(version) if version is not None else None


def preflight(host: str = DEFAULT_HOST, required: list[str] | None = None,
              client: Any | None = None) -> dict[str, Any]:
    host = require_loopback(host)
    required = sorted(set(required or []))
    query_version = client is None
    client = client or OllamaClient(host=host, retries=0, timeout=10)
    base = {"schema_id": SCHEMA_ID, "host": host, "required": required,
            "download_attempted": False, "scripted_substitute_used": False}
    try:
        inventory = client.inventory()
    except (OllamaError, OSError) as exc:
        return {**base, "status": "REAL_AGENT_NOT_RUN", "reason": "LOCAL_RUNTIME_UNAVAILABLE",
                "detail": type(exc).__name__, "runtime_version": None, "models": [],
                "missing": required}
    models = sorted((
        {"name": item["name"], "digest": item.get("digest"),
         "quantization": (item.get("details") or {}).get("quantization_level"),
         "parameter_size": (item.get("details") or {}).get("parameter_size"),
         "family": (item.get("details") or {}).get("family"),
         "size_bytes": item.get("size")}
        for item in inventory), key=lambda model: model["name"])
    names = [model["name"] for model in models]
    missing = [name for name in required if OllamaClient.resolve(name, names) is None]
    undigested = [model["name"] for model in models
                  if OllamaClient.resolve(model["name"], required) and not model["digest"]]
    version = _runtime_version(host) if query_version else None
    if missing:
        return {**base, "status": "REAL_AGENT_NOT_RUN", "reason": "PINNED_MODEL_NOT_INSTALLED",
                "runtime_version": version, "models": models, "missing": missing}
    if undigested:
        return {**base, "status": "REAL_AGENT_NOT_RUN", "reason": "MODEL_DIGEST_UNAVAILABLE",
                "runtime_version": version, "models": models, "missing": []}
    if not models:
        return {**base, "status": "REAL_AGENT_NOT_RUN", "reason": "NO_LOCAL_MODEL_INSTALLED",
                "runtime_version": version, "models": [], "missing": []}
    return {**base, "status": "MODELS_AVAILABLE", "reason": "inventory read from local runtime",
            "runtime_version": version, "models": models, "missing": []}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--require", action="append", default=[], metavar="MODEL")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        report = preflight(args.host, args.require)
    except NonLocalHostError as exc:
        print(json.dumps({"schema_id": SCHEMA_ID, "status": "REFUSED", "reason": str(exc)}))
        return EXIT_ERROR
    text = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if args.out is not None:
        args.out.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return EXIT_AVAILABLE if report["status"] == "MODELS_AVAILABLE" else EXIT_NOT_RUN


if __name__ == "__main__":
    raise SystemExit(main())
