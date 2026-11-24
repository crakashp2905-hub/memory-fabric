"""Diagnosis accuracy against a hidden oracle (W06-10).

    python -m benchmarks.outcome_diagnosis --seeds 4 --out research/results/agent-outcomes/diagnosis-dev.json

Each case builds a real store condition: a current claim, a superseded one,
one withdrawn, one erased, one in another tenant, one never recorded, one
recorded but phrased so the search cannot find it, and a damaged certificate.
The oracle label is set by construction and never shown to the diagnoser. The
diagnoser sees only what an actor-side host sees: what the governed search
returned and the codes certificate verification gave. Its answer is compared in
the actor-visible space, where ``no_permission`` and ``no_evidence`` are the
same ``not_available`` (W06-03).

The report gives a confusion matrix per family, false-denial and false-allow
counts, and a release rule: any false allow in a guard-sensitive class, or more
false allows than the frozen baseline, blocks release.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from memory_fabric.outcome_typed.diagnosis import (
    Diagnosis, Rung, availability, classify, search_ladder,
)

SCHEMA_ID = "memory-fabric.agent-outcome-diagnosis.v1"
FAMILIES: Mapping[str, tuple[str, ...]] = {
    "relevance": ("answerable", "no_evidence", "retrieval_miss"),
    "validity": ("superseded", "withdrawn", "erased", "malformed"),
    "authority": ("no_permission",),
}
EXPECTED: Mapping[str, str] = {
    "answerable": "answerable", "no_evidence": "not_available",
    "retrieval_miss": "not_available", "superseded": "superseded", "withdrawn": "withdrawn",
    "erased": "withdrawn", "malformed": "malformed_assertion", "no_permission": "not_available",
}
"""Oracle label -> the correct actor-visible diagnosis. A retrieval miss is, from the
actor's side, indistinguishable from absence; it is counted as a false denial
against the oracle, which knows the fact existed and was permitted."""
GUARD_SENSITIVE = frozenset({"superseded", "withdrawn", "erased", "malformed", "no_permission"})


def run_case(label: str, seed: int) -> dict[str, Any]:
    from memory_fabric import MemoryFabric
    from memory_fabric.certificates import CertificateError, EvidenceCertificate

    fabric = MemoryFabric(":memory:", auto_activate=True)
    try:
        subject = f"valve V-{seed:03d}-{label}"
        query = f"{subject} pressure limit"
        text = f"{subject} pressure limit is {10 + seed} bar"
        tenant = "tn_default"
        if label == "no_permission":
            fabric.remember("ana", text, scope="team", tenant_id="tn_other")
        elif label == "retrieval_miss":
            # Recorded, permitted, but worded so the query terms do not match.
            fabric.remember("ana", f"the release setting on that unit reads {10 + seed}",
                            scope="team", tenant_id=tenant)
        elif label != "no_evidence":
            fabric.remember("ana", text, scope="team", tenant_id=tenant)

        def lexical(q: str) -> Sequence[Any]:
            return list(fabric.retrieve(agent_id="ops", query=q, k=3, tenant_id=tenant,
                                        method="lexical"))

        ladder = search_ladder(query, [Rung("lexical", lexical)], budget=2)
        found = list(ladder.results)
        codes: tuple[str, ...] = ()
        evidence: list[tuple[str, int]] = []
        if found:
            memory_id = str(getattr(found[0], "memory_id", None) or getattr(found[0], "id"))
            certificate = fabric.certify(subject, [memory_id], "ops", tenant_id=tenant)
            evidence = [(str(memory_id), 1)]
            if label == "superseded":
                fabric.revise(memory_id, text.replace("bar", "bar (revised)"), "ana", "vendor update")
            elif label == "withdrawn":
                fabric.quarantine(memory_id, reason="wrong value", actor="op")
            elif label == "erased":
                fabric.erase_content(memory_id, reason="erasure request", actor="op")
            if label == "malformed":
                damaged = dict(certificate.to_json())
                damaged.pop("evidence")
                try:
                    EvidenceCertificate.from_json(damaged)
                    codes = ("ok",)
                except (CertificateError, KeyError, TypeError, ValueError):
                    codes = ("malformed_certificate",)
            else:
                codes = tuple(fabric.verify_certificate(certificate, "ops", tenant_id=tenant).reason_codes)
        result = availability(exists=bool(found), retrieved=bool(found), authorized=bool(found),
                              answers=bool(found), reason_codes=codes, evidence=evidence)
        actor = result.to_actor()["diagnosis"]
        return {"label": label, "seed": seed, "expected": EXPECTED[label], "diagnosed": actor,
                "correct": actor == EXPECTED[label], "codes": list(codes),
                "ladder": list(ladder.costs)}
    finally:
        fabric.close()


def confusion(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, int]]:
    matrix: dict[str, dict[str, int]] = {}
    for row in rows:
        matrix.setdefault(row["label"], {}).setdefault(row["diagnosed"], 0)
        matrix[row["label"]][row["diagnosed"]] += 1
    return matrix


def run(seeds: int = 4, baseline: Mapping[str, Any] | None = None) -> dict[str, Any]:
    rows = [run_case(label, seed) for labels in FAMILIES.values() for label in labels
            for seed in range(seeds)]
    false_allow = [r for r in rows if r["label"] in GUARD_SENSITIVE and r["diagnosed"] == "answerable"]
    false_deny = [r for r in rows if r["label"] in {"answerable", "retrieval_miss"}
                  and r["diagnosed"] != "answerable"]
    by_family = {family: confusion([r for r in rows if r["label"] in labels])
                 for family, labels in FAMILIES.items()}
    previous = None if baseline is None else baseline.get("false_allow")
    release = ("BLOCKED" if false_allow or (previous is not None and len(false_allow) > previous)
               else "ALLOWED")
    return {"schema_id": SCHEMA_ID, "population": "SCRIPTED_DEVELOPMENT", "seeds": seeds,
            "cases": len(rows), "accuracy": round(sum(r["correct"] for r in rows) / len(rows), 4),
            "false_allow": len(false_allow), "false_deny": len(false_deny),
            "false_deny_labels": sorted({r["label"] for r in false_deny}),
            "confusion_by_family": by_family, "release": release,
            "not_exercised": sorted(d.value for d in Diagnosis
                                    if d.value not in {"answerable", "no_evidence", "retrieval_miss",
                                                       "superseded", "withdrawn",
                                                       "malformed_assertion", "no_permission"}),
            "rows": rows}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, default=4)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    baseline = json.loads(args.baseline.read_text()) if args.baseline else None
    report = run(args.seeds, baseline)
    if args.out:
        args.out.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"accuracy {report['accuracy']}; false allow {report['false_allow']}; false deny "
          f"{report['false_deny']} ({report['false_deny_labels']}); release {report['release']}")
    return 0 if report["release"] == "ALLOWED" else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
