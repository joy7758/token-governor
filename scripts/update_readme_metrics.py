#!/usr/bin/env python3
"""Auto-update README metrics and chart from benchmark comparison outputs."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REAL_START_MARKER = "<!-- REAL_METRICS_START -->"
REAL_END_MARKER = "<!-- REAL_METRICS_END -->"
LEGACY_START_MARKER = "<!-- METRICS_START -->"
LEGACY_END_MARKER = "<!-- METRICS_END -->"
CHART_START_MARKER = "<!-- CHART_IMAGE_START -->"
CHART_END_MARKER = "<!-- CHART_IMAGE_END -->"

DEFAULT_KEYWORDS = (
    "天将, TianJiang, Token Governor, LLM 成本优化, Token 节省, 推理成本, 智能体, "
    "上下文压缩, 语义缓存, 工具 Top-K, 预算守卫, 自动策略, 模型画像, 推理路由, "
    "LLM cost optimization, token savings, inference cost, AI agents, context compression, "
    "semantic cache, tool top-k, budget guard, auto strategy, model profiling, model routing"
)


def _parse_iso_datetime(text: str | None) -> datetime | None:
    if not text:
        return None
    candidate = text.strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _is_summary_dict(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    required = ("mean_token", "p95_token", "success_rate", "mean_latency", "count")
    return all(key in value for key in required)


def load_summary(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid JSON structure in {path}")
    return data


def extract_baseline(summary: dict[str, Any]) -> dict[str, float]:
    baseline = summary.get("baseline")
    if _is_summary_dict(baseline):
        return {k: float(v or 0.0) for k, v in baseline.items()}
    if isinstance(baseline, dict) and _is_summary_dict(baseline.get("summary")):
        block = baseline["summary"]
        return {k: float(v or 0.0) for k, v in block.items()}
    raise ValueError("Invalid comparison JSON: missing baseline summary.")


def extract_modes(summary: dict[str, Any]) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    modes = summary.get("modes")
    if isinstance(modes, dict):
        for mode_name, mode_value in modes.items():
            if isinstance(mode_value, dict) and _is_summary_dict(mode_value.get("summary")):
                result[mode_name] = {
                    k: float(v or 0.0) for k, v in mode_value["summary"].items()
                }
            elif _is_summary_dict(mode_value):
                result[mode_name] = {k: float(v or 0.0) for k, v in mode_value.items()}

    if result:
        return result

    # Backward compatibility for legacy single-mode reports.
    for name in ("governor", "eco", "auto", "comfort", "sport", "rocket"):
        value = summary.get(name)
        if _is_summary_dict(value):
            result[name] = {k: float(v or 0.0) for k, v in value.items()}
        elif isinstance(value, dict) and _is_summary_dict(value.get("summary")):
            result[name] = {k: float(v or 0.0) for k, v in value["summary"].items()}

    return result


def pick_mode_name(
    modes: dict[str, dict[str, float]],
    preferred_mode: str | None,
) -> str:
    if preferred_mode:
        if preferred_mode not in modes:
            available = ", ".join(sorted(modes.keys()))
            raise ValueError(
                f"Mode '{preferred_mode}' not found in report. Available modes: {available}"
            )
        return preferred_mode
    if "governor" in modes:
        return "governor"
    return min(modes, key=lambda name: modes[name].get("mean_token", 0.0))


def pct_change(new_value: float, baseline_value: float) -> float:
    if baseline_value == 0:
        return 0.0
    return ((new_value - baseline_value) / baseline_value) * 100.0


def token_savings_pct(baseline_tokens: float, optimized_tokens: float) -> float:
    if baseline_tokens == 0:
        return 0.0
    return ((baseline_tokens - optimized_tokens) / baseline_tokens) * 100.0


def format_tokens(value: float) -> str:
    rounded = round(value)
    if abs(value - rounded) < 1e-6:
        return f"{rounded:,}"
    return f"{value:,.2f}"


def format_usd(value: float) -> str:
    return f"${value:,.4f}"


def _as_rel_posix(path: Path, base_dir: Path) -> str:
    if path.is_absolute():
        rel = os.path.relpath(str(path), str(base_dir))
        return Path(rel).as_posix()
    return path.as_posix()


def build_metrics_block(
    summary: dict[str, Any],
    *,
    repo_root: Path,
    comparison_path: Path,
    selected_mode: str,
    usd_per_1k_tokens: float | None,
    keywords: str,
) -> str:
    baseline = extract_baseline(summary)
    modes = extract_modes(summary)
    optimized = modes[selected_mode]

    baseline_count = baseline.get("count", 0.0)
    optimized_count = optimized.get("count", 0.0)
    baseline_avg = baseline.get("mean_token", 0.0)
    optimized_avg = optimized.get("mean_token", 0.0)
    baseline_total = baseline_avg * baseline_count
    optimized_total = optimized_avg * optimized_count

    baseline_success_pct = baseline.get("success_rate", 0.0) * 100.0
    optimized_success_pct = optimized.get("success_rate", 0.0) * 100.0
    baseline_latency = baseline.get("mean_latency", 0.0)
    optimized_latency = optimized.get("mean_latency", 0.0)

    total_token_delta_pct = pct_change(optimized_total, baseline_total)
    success_delta_pp = (
        optimized.get("success_rate", 0.0) - baseline.get("success_rate", 0.0)
    ) * 100.0
    latency_delta_pct = pct_change(optimized_latency, baseline_latency)
    savings_pct = token_savings_pct(baseline_total, optimized_total)

    generated_at = summary.get("generated_at_utc", "N/A")
    comparison_display = _as_rel_posix(comparison_path, repo_root)
    mode_label = selected_mode

    lines: list[str] = []
    lines.append("### 📊 实测结果 / Real Benchmark Results")
    lines.append("")
    if savings_pct >= 0:
        lines.append(f"- **Token 节省 / Token Savings**：**{savings_pct:.2f}%**")
    else:
        lines.append(
            f"- **Token 变化 / Token Change**：**+{abs(savings_pct):.2f}%**（Token Increase）"
        )
    lines.append(
        f"- **成功率 / Success Rate**：Baseline **{baseline_success_pct:.2f}%** → TianJiang ({mode_label}) **{optimized_success_pct:.2f}%**"
    )
    lines.append(
        f"- **延迟 / Latency**：Baseline **{baseline_latency:.2f}s** → TianJiang ({mode_label}) **{optimized_latency:.2f}s** ({latency_delta_pct:+.2f}%)"
    )
    lines.append(
        f"- **总 Token / Total Tokens**：Baseline **{format_tokens(baseline_total)}** → TianJiang ({mode_label}) **{format_tokens(optimized_total)}** ({total_token_delta_pct:+.2f}%)"
    )
    lines.append(
        "- **统计口径 / Method**：Total Tokens = count × mean_token（input+output）"
    )

    if usd_per_1k_tokens is not None and usd_per_1k_tokens >= 0 and baseline_total > 0:
        baseline_cost = baseline_total / 1000.0 * usd_per_1k_tokens
        optimized_cost = optimized_total / 1000.0 * usd_per_1k_tokens
        cost_delta_pct = pct_change(optimized_cost, baseline_cost)
        lines.append(
            f"- **成本估算 / Cost (USD est.)**：Baseline **{format_usd(baseline_cost)}** → TianJiang ({mode_label}) **{format_usd(optimized_cost)}** ({cost_delta_pct:+.2f}%)"
        )

    lines.append("")
    lines.append(
        f"> 数据源 / Data source: `{comparison_display}` | Generated (UTC): `{generated_at}` | ΔSuccess: {success_delta_pp:+.2f}pp"
    )
    lines.append("")
    lines.append(f"**关键词 / Keywords**：{keywords}")
    return "\n".join(lines).strip()


def _replace_marked_block(
    content: str,
    start_marker: str,
    end_marker: str,
    block_text: str,
) -> tuple[str, bool]:
    pattern = re.compile(
        re.escape(start_marker) + r".*?" + re.escape(end_marker),
        flags=re.S,
    )
    if not pattern.search(content):
        return content, False
    replacement = f"{start_marker}\n{block_text}\n{end_marker}"
    return pattern.sub(replacement, content), True


def update_readme_blocks(
    readme_path: Path,
    *,
    metrics_block: str,
    chart_block: str | None,
) -> None:
    content = readme_path.read_text(encoding="utf-8")
    updated = content

    metrics_replaced = False
    for start_marker, end_marker in (
        (REAL_START_MARKER, REAL_END_MARKER),
        (LEGACY_START_MARKER, LEGACY_END_MARKER),
    ):
        candidate, replaced = _replace_marked_block(
            updated,
            start_marker,
            end_marker,
            metrics_block,
        )
        if replaced:
            updated = candidate
            metrics_replaced = True
            break

    if not metrics_replaced:
        replacement = f"{LEGACY_START_MARKER}\n{metrics_block}\n{LEGACY_END_MARKER}"
        updated = updated.rstrip() + "\n\n" + replacement + "\n"

    if chart_block is not None:
        candidate, replaced = _replace_marked_block(
            updated,
            CHART_START_MARKER,
            CHART_END_MARKER,
            chart_block,
        )
        if replaced:
            updated = candidate
        else:
            section = (
                "\n\n## 📊 策略对比图表（自动插入）\n\n"
                f"{CHART_START_MARKER}\n{chart_block}\n{CHART_END_MARKER}\n"
            )
            updated = updated.rstrip() + section

    readme_path.write_text(updated, encoding="utf-8")


def _extract_repo_from_remote(remote_url: str) -> str | None:
    # Supports:
    # - git@github.com:owner/repo.git
    # - https://github.com/owner/repo.git
    match = re.search(r"github\.com[:/]([^/]+)/([^/\s]+?)(?:\.git)?$", remote_url.strip())
    if not match:
        return None
    owner = match.group(1)
    repo = match.group(2)
    return f"{owner}/{repo}"


def detect_repo_root(start_dir: Path) -> Path:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(start_dir),
            check=True,
            capture_output=True,
            text=True,
        )
        repo_root = result.stdout.strip()
        if repo_root:
            return Path(repo_root)
    except (subprocess.SubprocessError, OSError):
        pass
    return start_dir


def detect_repo_slug(repo_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=str(repo_root),
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    return _extract_repo_from_remote(result.stdout)


def build_raw_url(repo_slug: str, branch: str, repo_relative_path: str) -> str:
    safe_path = repo_relative_path.lstrip("/")
    return f"https://raw.githubusercontent.com/{repo_slug}/{branch}/{safe_path}"


def build_chart_block(
    chart_path: Path,
    readme_path: Path,
    *,
    repo_root: Path,
    repo_slug: str | None,
    branch: str,
    link_mode: str,
    alt_text: str,
    width: int,
) -> str:
    relative_from_readme = _as_rel_posix(chart_path, readme_path.parent)

    if link_mode == "raw" and repo_slug:
        chart_abs = chart_path.resolve()
        try:
            repo_relative = chart_abs.relative_to(repo_root.resolve()).as_posix()
            src = build_raw_url(repo_slug, branch, repo_relative)
        except ValueError:
            src = relative_from_readme
    else:
        src = relative_from_readme

    if width > 0:
        return (
            "<div align=\"center\">\n"
            f"  <img src=\"{src}\" alt=\"{alt_text}\" width=\"{width}\" />\n"
            "</div>"
        )
    return f"![{alt_text}]({src})"


def find_latest_comparison_json(search_root: Path) -> Path:
    if not search_root.exists():
        raise FileNotFoundError(f"Reports directory not found: {search_root}")

    candidates = sorted(search_root.glob("**/comparison.json"))
    if not candidates:
        raise FileNotFoundError(f"No comparison.json found under: {search_root}")

    def candidate_score(path: Path) -> tuple[datetime, float]:
        generated = None
        try:
            data = load_summary(path)
            generated = _parse_iso_datetime(str(data.get("generated_at_utc", "")))
        except Exception:
            generated = None
        if generated is None:
            generated = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        return generated, path.stat().st_mtime

    return max(candidates, key=candidate_score)


def resolve_comparison_path(path_text: str | None, repo_root: Path) -> Path:
    if path_text:
        requested = Path(path_text)
        if requested.exists():
            return requested
        raise FileNotFoundError(f"Comparison JSON not found: {requested}")

    reports_root = repo_root / "metrics" / "reports"
    return find_latest_comparison_json(reports_root)


def resolve_chart_path(chart_path_text: str | None, comparison_path: Path) -> Path:
    if chart_path_text:
        return Path(chart_path_text)
    return comparison_path.parent / "comparison_summary.png"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Auto-calculate token savings and update README sections."
    )
    parser.add_argument(
        "--comparison",
        type=str,
        default=None,
        help="Path to comparison JSON. If omitted, auto-select latest metrics/reports/**/comparison.json.",
    )
    parser.add_argument(
        "--readme",
        type=str,
        default="README.md",
        help="README file path to patch.",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default=None,
        help="Optimized mode to compare against baseline. Default: governor if present, else lowest mean_token mode.",
    )
    parser.add_argument(
        "--no-chart",
        action="store_true",
        help="Disable chart block insertion/replacement.",
    )
    parser.add_argument(
        "--chart-path",
        type=str,
        default=None,
        help="Chart image path. Default: sibling comparison_summary.png of selected comparison JSON.",
    )
    parser.add_argument(
        "--chart-alt",
        type=str,
        default="天将 TianJiang - 推理成本与 Token 节省对比图 | LLM inference cost and token savings comparison",
        help="Alt text for inserted chart image.",
    )
    parser.add_argument(
        "--chart-width",
        type=int,
        default=0,
        help="Optional chart width in px. If >0 uses HTML <img> tag.",
    )
    parser.add_argument(
        "--chart-link-mode",
        type=str,
        choices=("raw", "relative"),
        default="raw",
        help="Use raw GitHub image URL or repository-relative path in README.",
    )
    parser.add_argument(
        "--repo",
        type=str,
        default=None,
        help="GitHub repo slug owner/repo for raw image links. Auto-detected from git remote if omitted.",
    )
    parser.add_argument(
        "--branch",
        type=str,
        default="main",
        help="Branch name used in raw image URLs.",
    )
    parser.add_argument(
        "--usd-per-1k-tokens",
        type=float,
        default=None,
        help="Optional estimated USD price per 1K tokens for cost row.",
    )
    parser.add_argument(
        "--keywords",
        type=str,
        default=DEFAULT_KEYWORDS,
        help="SEO keywords line appended to metrics block.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    readme_path = Path(args.readme)
    repo_root = detect_repo_root(readme_path.parent.resolve())

    comparison_path = resolve_comparison_path(args.comparison, repo_root)
    summary = load_summary(comparison_path)
    modes = extract_modes(summary)
    if not modes:
        raise ValueError(f"No optimized modes found in {comparison_path}")

    selected_mode = pick_mode_name(modes, args.mode)
    metrics_block = build_metrics_block(
        summary,
        repo_root=repo_root,
        comparison_path=comparison_path,
        selected_mode=selected_mode,
        usd_per_1k_tokens=args.usd_per_1k_tokens,
        keywords=args.keywords,
    )

    chart_block: str | None = None
    resolved_repo_slug = args.repo or detect_repo_slug(repo_root)
    if not args.no_chart:
        chart_path = resolve_chart_path(args.chart_path, comparison_path)
        if not chart_path.exists():
            raise FileNotFoundError(f"Chart image not found: {chart_path}")
        chart_block = build_chart_block(
            chart_path,
            readme_path,
            repo_root=repo_root,
            repo_slug=resolved_repo_slug,
            branch=args.branch,
            link_mode=args.chart_link_mode,
            alt_text=args.chart_alt,
            width=args.chart_width,
        )

    update_readme_blocks(
        readme_path,
        metrics_block=metrics_block,
        chart_block=chart_block,
    )

    print(f"Updated README: {readme_path}")
    print(f"Comparison JSON: {comparison_path}")
    print(f"Selected mode: {selected_mode}")
    if chart_block is not None:
        mode_label = args.chart_link_mode
        print(f"Chart mode: {mode_label} (repo={resolved_repo_slug or 'N/A'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
