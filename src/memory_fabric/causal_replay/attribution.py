"""Small deterministic estimands for evidence effects and credit allocation."""

from __future__ import annotations

__stability__ = "experimental"

import itertools
import math
import random
import time
import tracemalloc
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Iterable, TypeVar

from .types import CDMError
from .verifier import VerificationResult

T = TypeVar("T")


@dataclass(frozen=True)
class ComputationCost:
    cpu_nanoseconds: int
    wall_nanoseconds: int
    event_transitions: int
    peak_memory_bytes: int
    simulated_calls: int
    certificate_bytes: int
    disk_bytes: int
    model_calls: int = 0
    api_tokens: int = 0
    external_charges: int = 0


def measure_computation(operation: Callable[[], T], *, event_transitions: int,
                        simulated_calls: int = 0,
                        certificate: str | bytes | None = None,
                        artifact_paths: Iterable[str | Path] = ()) -> tuple[T, ComputationCost]:
    """Measure a local operation; external/model/API cost is always recorded as zero."""
    if (not callable(operation) or type(event_transitions) is not int or event_transitions < 0
            or type(simulated_calls) is not int or simulated_calls < 0):
        raise CDMError("computation cost counters must be non-negative integers")
    if certificate is None:
        certificate_bytes = 0
    elif isinstance(certificate, str):
        certificate_bytes = len(certificate.encode("utf-8"))
    elif isinstance(certificate, bytes):
        certificate_bytes = len(certificate)
    else:
        raise CDMError("certificate must be text, bytes or missing")
    disk_bytes = 0
    for raw_path in artifact_paths:
        path = Path(raw_path)
        try:
            if path.is_file():
                disk_bytes += path.stat().st_size
        except OSError as exc:
            raise CDMError("artifact footprint could not be measured") from exc
    was_tracing = tracemalloc.is_tracing()
    if not was_tracing:
        tracemalloc.start()
    baseline, _ = tracemalloc.get_traced_memory()
    tracemalloc.reset_peak()
    cpu_start = time.process_time_ns()
    wall_start = time.perf_counter_ns()
    try:
        result = operation()
    finally:
        wall_ns = time.perf_counter_ns() - wall_start
        cpu_ns = time.process_time_ns() - cpu_start
        _, peak = tracemalloc.get_traced_memory()
        if not was_tracing:
            tracemalloc.stop()
    cost = ComputationCost(cpu_ns, wall_ns, event_transitions, max(0, peak - baseline),
        simulated_calls, certificate_bytes, disk_bytes)
    return result, cost


@dataclass(frozen=True)
class Effect:
    candidate_id: str
    status: str
    decision_flip: bool | None
    total_variation: float | None
    utility_difference: float | None
    exposure: str


@dataclass(frozen=True)
class PairedEstimate:
    coupling_id: str
    replications: int
    skipped_trials: int
    mean_difference: float | None
    standard_error: float | None


@dataclass(frozen=True)
class DistributionalEstimate:
    factual_replications: int
    counterfactual_replications: int
    skipped_factual: int
    skipped_counterfactual: int
    mean_difference: float | None
    standard_error: float | None


@dataclass(frozen=True)
class PruningResult:
    candidates: tuple[str, ...]
    exact_eligible: bool
    reason: str


@dataclass(frozen=True)
class SourceRootAssessment:
    status: str
    independent_root_count: int | None
    groups: tuple[tuple[str, tuple[str, ...]], ...]


@dataclass(frozen=True)
class FederatedEvidenceVersion:
    evidence_id: str
    local_version: int
    source_root: str
    origin_version: int | None


@dataclass(frozen=True)
class FederatedVersionAssessment:
    status: str
    local_snapshot_replayable: bool
    bindings: tuple[FederatedEvidenceVersion, ...]


def total_variation(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    if set(left) != set(right) or not left:
        raise CDMError("option distributions must have the same non-empty support")
    for distribution in (left, right):
        if any(not math.isfinite(value) or value < 0 for value in distribution.values()):
            raise CDMError("distribution values must be finite and non-negative")
        if not math.isclose(sum(distribution.values()), 1.0, abs_tol=1e-12):
            raise CDMError("option distribution must sum to one")
    return 0.5 * sum(abs(left[key] - right[key]) for key in left)


def compare_effect(candidate_id: str, factual_distribution: Mapping[str, float],
                   counterfactual_distribution: Mapping[str, float], *,
                   factual_choice: str | None, counterfactual_choice: str | None,
                   factual_utility: float | None = None,
                   counterfactual_utility: float | None = None,
                   dependency_complete: bool, verification: VerificationResult,
                   exposure: str) -> Effect:
    if exposure not in {"retrieved", "cited", "consumed", "unknown"}:
        raise CDMError("unknown evidence exposure label")
    if (not dependency_complete or type(verification) is not VerificationResult
            or not verification.verified or verification.code != "VERIFIED"
            or exposure == "unknown"):
        return Effect(candidate_id, "NON_IDENTIFIABLE", None, None, None, exposure)
    tv = total_variation(factual_distribution, counterfactual_distribution)
    utility = None
    if factual_utility is not None and counterfactual_utility is not None:
        if not all(math.isfinite(value) for value in (factual_utility, counterfactual_utility)):
            raise CDMError("utilities must be finite")
        utility = counterfactual_utility - factual_utility
    return Effect(candidate_id, "IDENTIFIED_UNDER_REPLAY_CONTRACT",
                  factual_choice != counterfactual_choice, tv, utility, exposure)


def exhaustive_shapley(players: tuple[str, ...], value: Callable[[frozenset[str]], float]
                       ) -> dict[str, float]:
    """Exact Shapley values for at most 10 players; caller supplies frozen game."""
    if len(players) > 10 or len(set(players)) != len(players):
        raise CDMError("exhaustive Shapley requires at most 10 unique players")
    n = len(players)
    if n == 0:
        return {}
    result: dict[str, float] = {}
    for player in players:
        others = tuple(item for item in players if item != player)
        credit = 0.0
        for size in range(n):
            weight = math.factorial(size) * math.factorial(n - size - 1) / math.factorial(n)
            for subset in itertools.combinations(others, size):
                coalition = frozenset(subset)
                credit += weight * (value(coalition | {player}) - value(coalition))
        result[player] = credit
    return result


def sampled_shapley(players: tuple[str, ...], value: Callable[[frozenset[str]], float], *,
                    seed: int, permutations: int) -> dict[str, float]:
    if not players or len(set(players)) != len(players):
        raise CDMError("sampled Shapley requires unique players")
    if type(permutations) is not int or permutations < 1:
        raise CDMError("permutations must be positive")
    totals = {player: 0.0 for player in players}
    rng = random.Random(seed)
    for _ in range(permutations):
        order = list(players)
        rng.shuffle(order)
        coalition: frozenset[str] = frozenset()
        previous = value(coalition)
        for player in order:
            coalition = coalition | {player}
            current = value(coalition)
            totals[player] += current - previous
            previous = current
    return {player: amount / permutations for player, amount in totals.items()}


def pairwise_interaction_screen(players: tuple[str, ...], *,
                                coalition_values: Mapping[tuple[str, ...], float]
                                ) -> tuple[dict[str, object], ...]:
    """Return exact context-specific second differences for every player pair."""
    if not players or len(players) > 10 or len(set(players)) != len(players):
        raise CDMError("interaction screen requires 1..10 unique players")
    ordered = tuple(sorted(players))
    expected = {tuple(sorted(group)) for size in range(len(players) + 1)
                for group in itertools.combinations(ordered, size)}
    if set(coalition_values) != expected:
        raise CDMError("interaction screen requires every coalition value")
    if any(not math.isfinite(value) for value in coalition_values.values()):
        raise CDMError("coalition values must be finite")
    rows: list[dict[str, object]] = []
    for left_index, left in enumerate(ordered):
        for right in ordered[left_index + 1:]:
            contexts = tuple(group for size in range(len(ordered) - 1)
                for group in itertools.combinations(
                    tuple(item for item in ordered if item not in {left, right}), size))
            terms = []
            for context in contexts:
                base = tuple(sorted(context))
                with_left = tuple(sorted((*context, left)))
                with_right = tuple(sorted((*context, right)))
                with_both = tuple(sorted((*context, left, right)))
                terms.append(coalition_values[with_both] - coalition_values[with_left]
                             - coalition_values[with_right] + coalition_values[base])
            rows.append({"left": left, "right": right, "context_terms": tuple(terms),
                         "max_abs_interaction": max((abs(item) for item in terms), default=0.0)})
    return tuple(rows)


def paired_common_random_estimate(factual: Iterable[float | None],
                                  counterfactual: Iterable[float | None], *,
                                  coupling_valid: bool,
                                  run_manifest: Mapping[str, object]) -> PairedEstimate:
    """Estimate paired CF-F differences only under an explicitly declared coupling."""
    coupling_id = run_manifest.get("coupling_id")
    if (coupling_valid is not True or run_manifest.get("common_random_numbers") is not True
            or not isinstance(coupling_id, str) or not coupling_id.strip()):
        raise CDMError("paired estimate requires a valid manifest-declared coupling")
    left, right = tuple(factual), tuple(counterfactual)
    if len(left) != len(right):
        raise CDMError("paired outcome sequences must have equal lengths")
    differences: list[float] = []
    skipped = 0
    for before, after in zip(left, right):
        if before is None or after is None:
            skipped += 1
            continue
        if (isinstance(before, bool) or isinstance(after, bool)
                or not isinstance(before, (int, float)) or not isinstance(after, (int, float))
                or not math.isfinite(before) or not math.isfinite(after)):
            raise CDMError("paired outcomes must be finite numeric values or missing")
        differences.append(float(after - before))
    if not differences:
        return PairedEstimate(coupling_id, 0, skipped, None, None)
    mean = math.fsum(differences) / len(differences)
    if len(differences) < 2:
        standard_error = None
    else:
        variance = math.fsum((value - mean) ** 2 for value in differences) / (len(differences) - 1)
        standard_error = math.sqrt(variance / len(differences))
    return PairedEstimate(coupling_id, len(differences), skipped, mean, standard_error)


def distributional_effect(factual: Iterable[float | None],
                          counterfactual: Iterable[float | None]) -> DistributionalEstimate:
    """Unpaired CF-F mean effect with Welch-style standard error and skip counts."""
    def collect(values: Iterable[float | None]) -> tuple[list[float], int]:
        usable: list[float] = []
        skipped = 0
        for value in values:
            if value is None:
                skipped += 1
            elif (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value)):
                raise CDMError("outcomes must be finite numeric values or missing")
            else:
                usable.append(float(value))
        return usable, skipped

    before, skipped_before = collect(factual)
    after, skipped_after = collect(counterfactual)
    if not before or not after:
        return DistributionalEstimate(len(before), len(after), skipped_before,
                                      skipped_after, None, None)
    mean_before = math.fsum(before) / len(before)
    mean_after = math.fsum(after) / len(after)
    mean_difference = mean_after - mean_before
    if len(before) < 2 or len(after) < 2:
        standard_error = None
    else:
        var_before = math.fsum((value - mean_before) ** 2 for value in before) / (len(before) - 1)
        var_after = math.fsum((value - mean_after) ** 2 for value in after) / (len(after) - 1)
        standard_error = math.sqrt(var_before / len(before) + var_after / len(after))
    return DistributionalEstimate(len(before), len(after), skipped_before,
                                  skipped_after, mean_difference, standard_error)


def prune_candidates_by_lineage(candidate_ids: Iterable[str], target_id: str, *,
                                dependencies: Mapping[str, tuple[str, ...]],
                                dependencies_complete: bool) -> PruningResult:
    """Prune to decision ancestry only when the dependency graph is certified complete."""
    candidates = tuple(sorted(set(candidate_ids)))
    if not target_id or any(not item for item in candidates):
        raise CDMError("candidate and target IDs must be non-empty")
    if not dependencies_complete:
        return PruningResult(candidates, False, "dependency completeness unknown; full candidate set retained")
    ancestors = {target_id}
    frontier = [target_id]
    while frontier:
        current = frontier.pop()
        for parent in dependencies.get(current, ()):
            if parent not in ancestors:
                ancestors.add(parent)
                frontier.append(parent)
    selected = tuple(candidate for candidate in candidates if candidate in ancestors)
    return PruningResult(selected, True, "complete dependency graph; non-ancestors pruned")


def assess_source_roots(evidence_ids: Iterable[str], *,
                        root_by_evidence: Mapping[str, str | None],
                        lineage_complete: bool) -> SourceRootAssessment:
    """Group copies by source root and refuse an independence count if lineage is unknown."""
    evidence = tuple(sorted(set(evidence_ids)))
    if not evidence or any(not item for item in evidence):
        raise CDMError("evidence IDs must be non-empty")
    missing = [item for item in evidence if item not in root_by_evidence
               or not root_by_evidence[item]]
    if not lineage_complete or missing:
        groups: dict[str, list[str]] = {}
        for item in evidence:
            root = root_by_evidence.get(item)
            if root:
                groups.setdefault(root, []).append(item)
        return SourceRootAssessment("AMBIGUOUS_LINEAGE", None,
                                    tuple((root, tuple(values))
                                          for root, values in sorted(groups.items())))
    grouped: dict[str, list[str]] = {}
    for item in evidence:
        grouped.setdefault(str(root_by_evidence[item]), []).append(item)
    resolved_groups = tuple((root, tuple(values)) for root, values in sorted(grouped.items()))
    return SourceRootAssessment("ROOTS_RESOLVED", len(resolved_groups), resolved_groups)


def assess_fabric_source_roots(fabric: Any, session: Any,
                               evidence_ids: Iterable[str]) -> SourceRootAssessment:
    """Resolve local, copied, derived, and imported evidence to portable source roots.

    Every item is rechecked against the caller's current read permission. A
    missing local item refuses generically; unavailable or malformed remote
    root metadata yields ambiguous lineage and no independence count.
    """
    from collections.abc import Mapping as MappingABC
    from ..identity import PERM_READ
    from ..service import Session
    from .types import Erased, Unauthorized

    if type(session) is not Session or session.service._fabric is not fabric:
        raise Unauthorized("source-root assessment requires a fabric-bound session")
    try:
        principal = session.principal()
        principal.require_permission(PERM_READ)
    except Exception as exc:
        raise Unauthorized("source-root authorization is unavailable") from exc
    ids = tuple(evidence_ids)
    if (not ids or len(ids) > 100 or len(set(ids)) != len(ids)
            or any(type(item) is not str or not item for item in ids)):
        raise CDMError("source-root assessment requires 1 to 100 unique evidence IDs")
    roots: dict[str, str | None] = {}
    for memory_id in ids:
        if memory_id in fabric.state.erased:
            raise Erased("requested evidence is unavailable")
        try:
            current = fabric.use(memory_id, agent_id=principal.agent_id,
                tenant_id=principal.tenant_id, audit=False)
        except Exception as exc:
            raise Erased("requested evidence is unavailable") from exc
        if not current.usable:
            raise Erased("requested evidence is unavailable")
        try:
            local_root = fabric.source_root(memory_id)
            root_memory = fabric.state.memories.get(local_root)
        except Exception:
            roots[memory_id] = None
            continue
        if root_memory is None:
            roots[memory_id] = None
            continue
        context = root_memory.context if isinstance(root_memory.context, MappingABC) else {}
        origin = context.get("federation")
        is_import = getattr(root_memory.provenance.method, "value",
                            root_memory.provenance.method) == "imported"
        if is_import:
            remote_root = origin.get("root") if isinstance(origin, MappingABC) else None
            if isinstance(remote_root, MappingABC):
                store_id = remote_root.get("store")
                source_id = remote_root.get("memory_id")
                if (isinstance(store_id, str) and store_id
                        and isinstance(source_id, str) and source_id):
                    roots[memory_id] = f"{store_id}/{source_id}"
                    continue
            roots[memory_id] = None
        else:
            # User-authored context cannot mint a foreign source root. Only a
            # memory recorded as a federation import may supply remote root metadata.
            roots[memory_id] = f"{fabric.store_id}/{local_root}"
    return assess_source_roots(ids, root_by_evidence=roots, lineage_complete=True)


def assess_federated_versions(fabric: Any, session: Any,
                              evidence_ids: Iterable[str]) -> FederatedVersionAssessment:
    """Bind authorized local versions to any preserved federation origin versions."""
    from collections.abc import Mapping as MappingABC
    from ..identity import PERM_READ
    from ..service import Session
    from .types import Erased, Unauthorized

    if type(session) is not Session or session.service._fabric is not fabric:
        raise Unauthorized("version assessment requires a fabric-bound session")
    try:
        principal = session.principal()
        principal.require_permission(PERM_READ)
    except Exception as exc:
        raise Unauthorized("version assessment authorization is unavailable") from exc
    ids = tuple(evidence_ids)
    if (not ids or len(ids) > 100 or len(set(ids)) != len(ids)
            or any(type(item) is not str or not item for item in ids)):
        raise CDMError("version assessment requires 1 to 100 unique evidence IDs")
    roots = assess_fabric_source_roots(fabric, session, ids)
    root_by_evidence = {evidence_id: root for root, members in roots.groups
                        for evidence_id in members}
    bindings: list[FederatedEvidenceVersion] = []
    versions_by_root: dict[str, set[int]] = {}
    unknown_origin = False
    for memory_id in ids:
        try:
            current = fabric.use(memory_id, agent_id=principal.agent_id,
                tenant_id=principal.tenant_id, audit=False)
            local_root = fabric.source_root(memory_id)
            root_memory = fabric.state.memories[local_root]
        except Exception as exc:
            raise Erased("requested evidence is unavailable") from exc
        if (memory_id in fabric.state.erased or not current.usable
                or memory_id not in root_by_evidence):
            raise Erased("requested evidence is unavailable")
        context = root_memory.context if isinstance(root_memory.context, MappingABC) else {}
        origin = context.get("federation")
        is_import = getattr(root_memory.provenance.method, "value",
                            root_memory.provenance.method) == "imported"
        origin_version: int | None = None
        if is_import:
            raw_version = origin.get("version") if isinstance(origin, MappingABC) else None
            if type(raw_version) is int and raw_version >= 1:
                origin_version = raw_version
                versions_by_root.setdefault(root_by_evidence[memory_id], set()).add(raw_version)
            else:
                unknown_origin = True
        bindings.append(FederatedEvidenceVersion(memory_id, current.memory.version,
            root_by_evidence[memory_id], origin_version))
    if unknown_origin:
        status = "ORIGIN_VERSION_UNKNOWN"
    elif any(len(versions) > 1 for versions in versions_by_root.values()):
        status = "MIXED_ORIGIN_VERSIONS"
    else:
        status = "CONSISTENT_ORIGIN_VERSIONS"
    return FederatedVersionAssessment(status, True, tuple(bindings))


def paired_bootstrap_interval(differences: tuple[float, ...], *, seed: int = 0,
                              replicates: int = 2_000,
                              confidence: float = 0.95) -> tuple[float, float]:
    if (not differences or any(not math.isfinite(value) for value in differences)
            or type(replicates) is not int or replicates < 100
            or not 0 < confidence < 1):
        raise CDMError("invalid paired bootstrap inputs")
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(differences) for _ in differences) / len(differences)
                   for _ in range(replicates))
    tail = (1 - confidence) / 2
    return (means[int(tail * replicates)], means[min(replicates - 1,
            math.ceil((1 - tail) * replicates) - 1)])


def wilson_interval(successes: int, trials: int, *, z: float = 1.959963984540054
                    ) -> tuple[float, float]:
    if (type(successes) is not int or type(trials) is not int or trials < 1
            or not 0 <= successes <= trials or not math.isfinite(z) or z <= 0):
        raise CDMError("invalid Wilson interval inputs")
    p = successes / trials
    if successes == 0:
        return 0.0, z * z / (trials + z * z)
    if successes == trials:
        return trials / (trials + z * z), 1.0
    scale = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / scale
    radius = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / scale
    return max(0.0, center - radius), min(1.0, center + radius)
