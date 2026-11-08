"""Local certificate acceptance confusion matrix for genuine and attack fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from memory_fabric.causal_replay.certificates import issue, verify
from memory_fabric.causal_replay.types import CDMError


def run() -> dict[str, Any]:
    valid = issue(capture_digest="a" * 64, intervention_digest="b" * 64,
        factual_fingerprint="c" * 64, counterfactual_fingerprint="d" * 64,
        updater_id="up-v1", policy_id="policy-v1", status="EXACT",
        factual_proposal="monitor", counterfactual_proposal="investigate", complete=True)
    valid_payload = json.loads(valid.to_json())
    cases = [{"case": "genuine_exact", "expected_accept": True, "payload": valid_payload}]
    for name, field, fixture_value in (
            ("tampered_capture", "capture_digest", "f" * 64),
            ("tampered_intervention", "intervention_digest", "f" * 64),
            ("tampered_policy", "policy_id", "policy-forged"),
            ("forged_action_authority", "action_entitlement", True),
            ("unsupported_physical", "world_semantics", "physical_counterfactual_unsupported")):
        altered = dict(valid_payload)
        altered[field] = fixture_value
        cases.append({"case": name, "expected_accept": False, "payload": altered})
    truncated_refused = False
    try:
        issue(capture_digest="a" * 64, intervention_digest="b" * 64,
            factual_fingerprint="c" * 64, counterfactual_fingerprint="d" * 64,
            updater_id="up-v1", policy_id="policy-v1", status="EXACT",
            factual_proposal="monitor", counterfactual_proposal="investigate", complete=False)
    except CDMError:
        truncated_refused = True
    cases.append({"case": "genuine_truncated", "expected_accept": False,
                  "payload": None, "accepted": not truncated_refused})
    for case in cases:
        if "accepted" not in case:
            case["accepted"] = verify(case["payload"])
    tp = sum(row["expected_accept"] and row["accepted"] for row in cases)
    tn = sum(not row["expected_accept"] and not row["accepted"] for row in cases)
    fp = sum(not row["expected_accept"] and row["accepted"] for row in cases)
    fn = sum(row["expected_accept"] and not row["accepted"] for row in cases)
    ablation_cases = [{"case": "genuine_exact", "expected_accept": True,
                       "payload": valid_payload}]
    for name, field, value in (
            ("tampered_capture", "capture_digest", "f" * 64),
            ("tampered_intervention", "intervention_digest", "f" * 64),
            ("tampered_policy", "policy_id", "policy-forged"),
            ("forged_action_authority", "action_entitlement", True),
            ("unsupported_physical", "world_semantics", "physical_counterfactual_unsupported"),
            ("missing_limitations", "limitations", ["no_action_entitlement"]),
            ("injected_completeness", "complete", True)):
        altered = dict(valid_payload)
        altered[field] = value
        ablation_cases.append({"case": name, "expected_accept": False,
                               "payload": altered})
    truncated_payload = dict(valid_payload)
    truncated_payload["complete"] = False
    ablation_cases.append({"case": "fabricated_truncated_exact", "expected_accept": False,
                           "payload": truncated_payload})
    for case in ablation_cases:
        case["self_certifying_executor_accepts"] = (
            case["payload"].get("status") == "EXACT")
        case["separate_verifier_accepts"] = _independent_certificate_verify(case["payload"])

    def confusion(field: str) -> dict[str, int]:
        tp = sum(row["expected_accept"] and row[field] for row in ablation_cases)
        tn = sum(not row["expected_accept"] and not row[field] for row in ablation_cases)
        fp = sum(not row["expected_accept"] and row[field] for row in ablation_cases)
        fn = sum(row["expected_accept"] and not row[field] for row in ablation_cases)
        return {"true_accept": tp, "true_reject": tn, "false_accept": fp,
                "false_reject": fn, "cases": len(ablation_cases)}
    return {"schema": "cdm-certificate-acceptance-v1", "cases": cases,
        "confusion_matrix": {"true_accept": tp, "true_reject": tn,
                             "false_accept": fp, "false_reject": fn,
                             "attack_cases": len(cases) - 1},
        "verifier_ablation": {"protocol": "CDM-R9",
            "scope": "deterministic local fixtures; not an empirical attack-rate estimate",
            "cases": ablation_cases,
            "self_certifying_executor": confusion("self_certifying_executor_accepts"),
            "separate_first_party_verifier": confusion("separate_verifier_accepts")},
        "scope": "first-party deterministic fixtures; not an empirical attack-rate estimate"}


def _independent_certificate_verify(value: Any) -> bool:
    """Separate stdlib certificate checker; intentionally avoids production verify()."""
    import hashlib
    import re

    expected = {"schema", "capture_digest", "intervention_digest", "factual_fingerprint",
        "counterfactual_fingerprint", "updater_id", "policy_id", "status",
        "proposal_changed", "claims", "action_entitlement", "estimand", "world_semantics",
        "minimality_claim", "minimality_proof_digest", "limitations", "certificate_digest"}
    if type(value) is not dict or set(value) != expected:
        return False
    if value.get("schema") != "memory-fabric-cdm-v1" or value.get("status") != "EXACT":
        return False
    if value.get("action_entitlement") is not False:
        return False
    if value.get("world_semantics") == "physical_counterfactual_unsupported":
        return False
    limitations = value.get("limitations")
    if (not isinstance(limitations, list)
            or "no_action_entitlement" not in limitations
            or "physical_world_not_verified" not in limitations
            or any(not isinstance(item, str) or not item for item in limitations)
            or len(set(limitations)) != len(limitations)):
        return False
    for field in ("capture_digest", "intervention_digest", "factual_fingerprint",
                  "counterfactual_fingerprint"):
        if not isinstance(value.get(field), str) or not re.fullmatch(r"[0-9a-f]{64}", value[field]):
            return False
    if (not isinstance(value.get("updater_id"), str) or not value["updater_id"]
            or not isinstance(value.get("policy_id"), str) or not value["policy_id"]):
        return False
    changed = value.get("proposal_changed")
    expected_claims = ["caused_internal_decision_change"] if changed is True else []
    if type(changed) is not bool or value.get("claims") != expected_claims:
        return False
    payload = {key: item for key, item in value.items() if key != "certificate_digest"}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False, allow_nan=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return value.get("certificate_digest") == digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="research/results/cdm/certificate-acceptance")
    args = parser.parse_args()
    result = run()
    output = Path(args.out)
    output.mkdir(parents=True, exist_ok=True)
    path = output / "acceptance.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    prereg = Path(__file__).resolve().parents[1] / "research" / "prereg" / \
        "cdm-r9-verifier-ablation.md"
    manifest = {"schema": "cdm-certificate-acceptance-manifest-v1",
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "output_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "confusion_matrix": result["confusion_matrix"], "network_calls": 0,
        "verifier_ablation": result["verifier_ablation"],
        "protocol": "research/prereg/cdm-r9-verifier-ablation.md",
        "protocol_sha256": hashlib.sha256(prereg.read_bytes()).hexdigest()}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True)
                                           + "\n", encoding="utf-8")
    print(json.dumps(manifest, sort_keys=True))
    matrix = result["confusion_matrix"]
    return 0 if matrix["false_accept"] == 0 and matrix["false_reject"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
