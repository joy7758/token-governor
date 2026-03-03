"""Tool selection policy for governor mode."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


_DEFAULT_COST = {
    "search": 0.45,
    "read": 0.35,
    "extract": 0.30,
    "aggregate": 0.40,
    "write": 0.90,
    "modify": 0.80,
    "delete": 1.00,
    "send_email": 0.95,
    "unknown": 0.50,
}

_DEFAULT_RISK = {
    "search": 0.10,
    "read": 0.05,
    "extract": 0.12,
    "aggregate": 0.08,
    "write": 0.70,
    "modify": 0.75,
    "delete": 0.95,
    "send_email": 0.85,
    "unknown": 0.30,
}


@dataclass(frozen=True)
class ToolMeta:
    id: str
    capability_type: str
    provides: tuple[str, ...]
    requires: tuple[str, ...]
    io_schema: str
    cost: float
    risk: float


def _tool_text(tool: Any) -> str:
    name = str(getattr(tool, "name", "") or "")
    description = str(getattr(tool, "description", "") or "")
    return f"{name} {description}".strip().lower()


def _infer_capability_type(tool: Any) -> str:
    text = _tool_text(tool)
    if any(term in text for term in ("search", "web", "lookup", "browse")):
        return "search"
    if any(term in text for term in ("read", "file", "document")):
        return "read"
    if any(term in text for term in ("extract", "parse", "scrape")):
        return "extract"
    if any(term in text for term in ("aggregate", "summarize", "combine")):
        return "aggregate"
    if any(term in text for term in ("write", "create", "insert")):
        return "write"
    if any(term in text for term in ("update", "modify", "patch")):
        return "modify"
    if any(term in text for term in ("delete", "remove", "drop")):
        return "delete"
    if any(term in text for term in ("email", "mail", "send")):
        return "send_email"
    return "unknown"


def _tool_meta(tool: Any, idx: int) -> ToolMeta:
    metadata = getattr(tool, "metadata", None)
    if not isinstance(metadata, dict):
        metadata = {}

    name = str(getattr(tool, "name", f"tool_{idx}") or f"tool_{idx}")
    tool_id = str(metadata.get("id", name))
    capability_type = str(metadata.get("capability_type") or _infer_capability_type(tool))

    provides = metadata.get("provides", [capability_type])
    if not isinstance(provides, list):
        provides = [str(provides)]

    requires = metadata.get("requires", [])
    if not isinstance(requires, list):
        requires = [str(requires)]

    io_schema = str(
        metadata.get("io_schema")
        or getattr(getattr(tool, "args_schema", None), "__name__", "unknown")
    )

    default_cost = _DEFAULT_COST.get(capability_type, _DEFAULT_COST["unknown"])
    default_risk = _DEFAULT_RISK.get(capability_type, _DEFAULT_RISK["unknown"])

    cost = float(metadata.get("cost", default_cost) or default_cost)
    risk = float(metadata.get("risk", default_risk) or default_risk)

    return ToolMeta(
        id=tool_id,
        capability_type=capability_type,
        provides=tuple(str(item) for item in provides),
        requires=tuple(str(item) for item in requires),
        io_schema=io_schema,
        cost=cost,
        risk=risk,
    )


def _similarity_score(query: str, tool: Any) -> float:
    query_terms = [term for term in query.lower().split() if term]
    if not query_terms:
        return 0.0

    text = _tool_text(tool)
    hits = sum(1 for term in query_terms if term in text)
    return hits / max(len(query_terms), 1)


def _policy_weights(policy: dict[str, Any] | None) -> tuple[float, float, float]:
    config = (policy or {}).get("tool_selection", {})
    cost_weight = float(config.get("cost_weight", 0.5) or 0.5)
    similarity_weight = float(config.get("similarity_weight", 0.4) or 0.4)
    risk_weight = float(config.get("risk_weight", 0.1) or 0.1)
    return cost_weight, similarity_weight, risk_weight


def _apply_dependency_closure(
    ranked: list[tuple[Any, ToolMeta, float]],
    selected: list[tuple[Any, ToolMeta, float]],
    *,
    max_dependency_depth: int,
    closure_max_size: int,
) -> list[tuple[Any, ToolMeta, float]]:
    if not selected:
        return []

    provider_index: dict[str, list[tuple[Any, ToolMeta, float]]] = {}
    for item in ranked:
        _, meta, _ = item
        for capability in meta.provides:
            provider_index.setdefault(capability, []).append(item)

    closure: list[tuple[Any, ToolMeta, float]] = list(selected)
    closure_ids = {meta.id for _, meta, _ in closure}
    frontier = [(item, 0) for item in selected]

    while frontier:
        (tool, meta, score), depth = frontier.pop(0)
        if depth >= max_dependency_depth:
            continue
        for requirement in meta.requires:
            providers = provider_index.get(requirement, [])
            if not providers:
                continue
            best_provider = providers[0]
            _, provider_meta, _ = best_provider
            if provider_meta.id in closure_ids:
                continue
            closure.append(best_provider)
            closure_ids.add(provider_meta.id)
            frontier.append((best_provider, depth + 1))
            if len(closure) >= closure_max_size:
                return closure
    return closure


def select_tools(
    query: str,
    all_tools: list[Any],
    top_k: int | None = None,
    *,
    policy: dict[str, Any] | None = None,
    allowed_tool_types: set[str] | None = None,
    return_trace: bool = False,
) -> list[Any] | tuple[list[Any], dict[str, Any]]:
    """
    Select top-k tools using weighted scoring and optional dependency closure.
    """
    if not all_tools:
        empty_trace = {
            "top_k_candidates": [],
            "dependency_closure": [],
            "scores": {},
            "tool_types": [],
        }
        return ([], empty_trace) if return_trace else []

    selection_cfg = (policy or {}).get("tool_selection", {})
    dependency_cfg = (policy or {}).get("dependency", {})

    effective_top_k = top_k
    if effective_top_k is None:
        effective_top_k = int(selection_cfg.get("topK", 3) or 3)

    if effective_top_k <= 0:
        effective_top_k = len(all_tools)
    effective_top_k = min(effective_top_k, len(all_tools))

    max_dependency_depth = int(selection_cfg.get("max_dependency_depth", 2) or 2)
    closure_max_size = int(dependency_cfg.get("closure_max_size", 6) or 6)

    cost_weight, similarity_weight, risk_weight = _policy_weights(policy)

    ranked: list[tuple[Any, ToolMeta, float]] = []
    scores: dict[str, float] = {}

    for idx, tool in enumerate(all_tools):
        meta = _tool_meta(tool, idx)

        if allowed_tool_types is not None and meta.capability_type not in allowed_tool_types:
            continue

        similarity = _similarity_score(query, tool)
        score = (similarity_weight * similarity) - (cost_weight * meta.cost) - (risk_weight * meta.risk)
        score = round(score, 6)

        ranked.append((tool, meta, score))
        scores[meta.id] = score

    ranked.sort(key=lambda item: item[2], reverse=True)
    selected = ranked[:effective_top_k]

    if bool(dependency_cfg.get("closure_expansion", True)):
        final_selection = _apply_dependency_closure(
            ranked,
            selected,
            max_dependency_depth=max_dependency_depth,
            closure_max_size=closure_max_size,
        )
    else:
        final_selection = selected

    selected_tools = [tool for tool, _, _ in final_selection]
    trace = {
        "top_k_candidates": [meta.id for _, meta, _ in selected],
        "dependency_closure": [meta.id for _, meta, _ in final_selection],
        "scores": scores,
        "tool_types": [meta.capability_type for _, meta, _ in final_selection],
    }

    if return_trace:
        return selected_tools, trace
    return selected_tools
