#!/usr/bin/env python3
"""Source-bound contract fixture for the agent-outcome stack (W23-04).

    python tools/source_bound.py --check     # exit 1 if a contract changed
    python tools/source_bound.py --write     # record a deliberate change

The fixture records, as readable values, the contracts other code and frozen
evidence depend on: the actor step and observation schemas, the evaluator
fields an actor may never see, the episode budget defaults, the declared tool
schema, the model-actor failure codes, the diagnosis taxonomy, the matched-arm
registry and parity dimensions, and the public API's request schema and error
codes. Changing any of them in code without re-recording the fixture fails the
check, so a contract change is always a visible, reviewed edit.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for extra in (ROOT / "src", ROOT):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))
FIXTURE = ROOT / "research" / "fixtures" / "agent-outcome-source-bound.json"
SCHEMA_ID = "memory-fabric.agent-outcome-source-bound.v1"


def compute() -> dict[str, Any]:
    from benchmarks.outcome_arms import ARMS
    from memory_fabric.outcome_typed import api, diagnosis, episode, observations

    tools = episode.default_tools()
    return {
        "schema_id": SCHEMA_ID,
        "agent_step_fields": sorted(f.name for f in dataclasses.fields(observations.AgentStep)),
        "agent_step_intents": sorted(observations._INTENTS),  # noqa: SLF001
        "observation_fields": sorted(f.name for f in dataclasses.fields(observations.AgentObservation)),
        "evaluator_only_fields": sorted(observations._FORBIDDEN),  # noqa: SLF001
        "episode_limits": dataclasses.asdict(episode.EpisodeLimits()),
        "tools": {name: {"roles": sorted(spec.roles), "fields": dict(sorted(spec.fields.items())),
                         "required": sorted(spec.required), "protected": spec.protected}
                  for name, spec in sorted(tools._specs.items())},  # noqa: SLF001
        "actor_backend_codes": sorted(episode.ACTOR_BACKEND_CODES),
        "diagnosis_codes": sorted(d.value for d in diagnosis.Diagnosis),
        "arms": {arm_id: {"memory": arm.memory, "recovery": arm.recovery, "cdm": arm.cdm}
                 for arm_id, arm in sorted(ARMS.items())},
        "api_request_fields": sorted(api.REQUEST_FIELDS),
        "api_refused_fields": sorted(api.AUTHORITY_FIELDS),
        "api_errors": sorted(api.ERRORS),
    }


def diff(recorded: dict[str, Any], current: dict[str, Any]) -> list[str]:
    return sorted(key for key in set(recorded) | set(current) if recorded.get(key) != current.get(key))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    current = compute()
    if args.write:
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(current, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote {FIXTURE.relative_to(ROOT)}")
        return 0
    recorded = json.loads(FIXTURE.read_text(encoding="utf-8")) if FIXTURE.is_file() else {}
    changed = diff(recorded, current)
    if changed:
        print("contract changed without updating the fixture: " + ", ".join(changed))
        print("if deliberate, run: python tools/source_bound.py --write, and say why in the commit")
        return 1
    print("source-bound contracts match the fixture")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
