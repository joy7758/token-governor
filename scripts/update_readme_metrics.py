"""Update README metrics block from comparison JSON output."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any


REAL_START_MARKER = "<!-- REAL_METRICS_START -->"
REAL_END_MARKER = "<!-- REAL_METRICS_END -->"
LEGACY_START_MARKER = "<!-- METRICS_START -->"
LEGACY_END_MARKER = "<!-- METRICS_END -->"
CHART_START_MARKER = "<!-- CHART_IMAGE_START -->"
CHART_END_MARKER = "<!-- CHART_IMAGE_END -->"

INDUSTRY_RANGE_ITEMS = (
    (
        "Prompt / Context Compression",
        "提示/上下文压缩",
        "~30%–60%+ token reduction",
        "High-redundancy prompts can see larger gains, depends on compression quality",
    ),
    (
        "Semantic / Prompt Caching",
        "语义/Prompt 缓存",
        "~40%–80% cost savings",
        "High cache-hit workloads can approach ~90% in practice",
    ),
    (
        "Model Routing",
        "模型路由",
        "Significant end-to-end efficiency gains",
        "Depends on task complexity split, model price gap, and routing quality",
    ),
    (
        "Combined Multi-Strategy",
        "多策略组合",
        "~60%–80%+ composite savings",
        "Compression + caching + routing + retrieval usually gives the largest gains",
    ),
)

INDUSTRY_SOURCES = (
    (
        "[1] Advanced Strategies to Optimize LLM Costs (Medium)",
        "https://medium.com/%40giuseppetrisciuoglio/advanced-strategies-to-optimize-large-language-model-costs-351c6777afbc",
    ),
    (
        "[2] SCOPE: Generative Prompt Compression (arXiv)",
        "https://arxiv.org/abs/2508.15813",
    ),
    (
        "[3] Clarifai: LLM Inference Optimization",
        "https://www.clarifai.com/blog/llm-inference-optimization/",
    ),
    (
        "[4] Zenn: Semantic Cache Cost Reduction",
        "https://zenn.dev/0h_n0/articles/531d06b7a17e9d",
    ),
    (
        "[5] Adaptive Semantic Prompt Caching with VectorQ (arXiv)",
        "https://arxiv.org/abs/2502.03771",
    ),
    (
        "[6] LLM Cost Optimization 2026 (abhyashsuchi.in)",
        "https://abhyashsuchi.in/llm-cost-optimization-2026-proven-strategies/",
    ),
    (
        "[7] Reducing LLM Costs Without Sacrificing Quality (Dev.to)",
        "https://dev.to/kuldeep_paul/the-complete-guide-to-reducing-llm-costs-without-sacrificing-quality-4gp3",
    ),
    (
        "[8] Reducing Costs in a Prompt-Centric Internet (arXiv)",
        "https://arxiv.org/html/2410.11857",
    ),
    (
        "[9] Prompt Compression Techniques (Medium)",
        "https://medium.com/%40kuldeep.paul08/prompt-compression-techniques-reducing-context-window-costs-while-improving-llm-performance-afec1e8f1003",
    ),
    (
        "[10] Prompt Caching up to 90% (Medium)",
        "https://medium.com/%40pur4v/prompt-caching-reducing-llm-costs-by-up-to-90-part-1-of-n-042ff459537f",
    ),
    (
        "[11] LLM Cost Optimization Pipelines (Leanware)",
        "https://www.leanware.co/insights/llm-cost-optimization-pipelines",
    ),
    (
        "[12] Future AGI Cost Optimization Guide",
        "https://futureagi.com/blogs/llm-cost-optimization-2025",
    ),
)


def pct_change(value: float, baseline: float) -> float:
    if baseline == 0:
        return 0.0
    return ((value - baseline) / baseline) * 100.0


def load_summary(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _is_summary_dict(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    required = ("mean_token", "p95_token", "success_rate", "mean_latency")
    return all(key in value for key in required)


def extract_baseline(summary: dict[str, Any]) -> dict[str, Any]:
    baseline = summary.get("baseline")
    if _is_summary_dict(baseline):
        return baseline
    if isinstance(baseline, dict) and _is_summary_dict(baseline.get("summary")):
        return baseline["summary"]
    raise ValueError("Invalid comparison JSON: missing baseline summary.")


def extract_modes(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}

    modes = summary.get("modes")
    if isinstance(modes, dict):
        for mode_name, mode_value in modes.items():
            if isinstance(mode_value, dict) and _is_summary_dict(mode_value.get("summary")):
                result[mode_name] = mode_value
            elif _is_summary_dict(mode_value):
                result[mode_name] = {"summary": mode_value}
    if result:
        return result

    # Backward compatibility: top-level mode objects.
    for name in ("governor", "eco", "auto", "comfort", "sport", "rocket"):
        value = summary.get(name)
        if not isinstance(value, dict):
            continue
        if _is_summary_dict(value):
            result[name] = {"summary": value}
            continue
        if _is_summary_dict(value.get("summary")):
            result[name] = value
    return result


def ensure_vs_baseline(
    mode_data: dict[str, Any],
    baseline: dict[str, float],
) -> dict[str, float]:
    existing = mode_data.get("vs_baseline")
    if isinstance(existing, dict):
        return {
            "mean_token_pct": float(existing.get("mean_token_pct", 0.0) or 0.0),
            "p95_token_pct": float(existing.get("p95_token_pct", 0.0) or 0.0),
            "mean_latency_pct": float(existing.get("mean_latency_pct", 0.0) or 0.0),
            "success_rate_pp": float(existing.get("success_rate_pp", 0.0) or 0.0),
        }

    mode_summary = mode_data["summary"]
    return {
        "mean_token_pct": pct_change(mode_summary["mean_token"], baseline["mean_token"]),
        "p95_token_pct": pct_change(mode_summary["p95_token"], baseline["p95_token"]),
        "mean_latency_pct": pct_change(
            mode_summary["mean_latency"],
            baseline["mean_latency"],
        ),
        "success_rate_pp": (
            mode_summary["success_rate"] - baseline["success_rate"]
        )
        * 100.0,
    }


def build_metrics_block(summary: dict[str, Any]) -> str:
    baseline = extract_baseline(summary)
    modes = extract_modes(summary)
    if not modes:
        raise ValueError("No modes found in comparison summary.")

    ordered = [
        name
        for name in ("governor", "eco", "auto", "comfort", "sport", "rocket")
        if name in modes
    ]
    ordered += [name for name in modes.keys() if name not in ordered]

    lines: list[str] = []
    lines.append("### 🔥 LLM Cost Optimization — 实测结果与行业参考区间")
    lines.append("")
    lines.append(
        "In real-world LLM systems, inference cost is tied to token usage, model selection, and runtime strategy."
    )
    lines.append(
        "We combine real measured benchmark outputs with publicly reported industry ranges for practical reference."
    )
    lines.append(
        "在真实生产级 LLM 场景中，推理成本取决于 Token 使用量、模型选型与优化策略。"
    )
    lines.append("本区块同时展示本仓库实测数据与公开工程经验区间，便于评估可达成节省空间。")
    lines.append("")
    lines.append("#### 📊 Measured Results / 实测结果（自动填充）")
    lines.append("")
    lines.append(
        "- 实测数据来源：自动生成的 `comparison.json`（Baseline vs 多模式运行结果）"
    )
    lines.append(
        "- Data source: auto-generated benchmark report (`comparison.json`) from baseline vs optimized modes"
    )
    lines.append("")

    baseline_file = summary.get("baseline_file", "baseline")
    mode_files = summary.get("mode_files", {})
    if isinstance(mode_files, dict) and mode_files:
        mode_files_text = ", ".join(f"{name}={path}" for name, path in mode_files.items())
    else:
        mode_files_text = "N/A"
    lines.append(f"- 数据源：`baseline={baseline_file}`")
    lines.append(f"- 对比文件：`{mode_files_text}`")
    lines.append("- 说明：百分比为相对 Baseline 变化（负值代表下降/节省）。")
    lines.append("")

    best_mode: str | None = None
    best_delta = 0.0
    for name in ordered:
        diff = ensure_vs_baseline(modes[name], baseline)
        token_delta = float(diff["mean_token_pct"])
        if best_mode is None or token_delta < best_delta:
            best_mode = name
            best_delta = token_delta

    if best_mode is not None:
        best_summary = modes[best_mode]["summary"]
        best_diff = ensure_vs_baseline(modes[best_mode], baseline)
        best_savings_pct = -best_diff["mean_token_pct"]
        if best_diff["mean_token_pct"] < 0:
            lines.append(
                f"- 最优 Token 模式：`{best_mode}`（平均 Token {best_summary['mean_token']:.2f}，"
                f"相对 Baseline 节省 {best_savings_pct:+.2f}%）"
            )
        else:
            lines.append(
                f"- 本轮暂无低于 Baseline 的模式；增幅最小模式为 `{best_mode}`（平均 Token {best_summary['mean_token']:.2f}，"
                f"相对 Baseline {best_diff['mean_token_pct']:+.2f}%）"
            )
        lines.append(
            f"- 该模式成功率：{best_summary['success_rate'] * 100:.2f}% "
            f"（变化 {best_diff['success_rate_pp']:+.2f}pp）"
        )
        lines.append(
            f"- 该模式平均延迟：{best_summary['mean_latency']:.2f}s "
            f"（变化 {best_diff['mean_latency_pct']:+.2f}%）"
        )
        lines.append("")

    lines.append(
        "| Mode / 模式 | Avg Token | Token Savings vs Baseline | Token Delta vs Baseline | Success Rate |"
    )
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    lines.append(
        f"| `baseline` | {baseline['mean_token']:.2f} | +0.00% | +0.00% | {baseline['success_rate'] * 100:.2f}% |"
    )

    for name in ordered:
        mode_summary = modes[name]["summary"]
        diff = ensure_vs_baseline(modes[name], baseline)
        savings_pct = -float(diff["mean_token_pct"])
        lines.append(
            f"| `{name}` | {mode_summary['mean_token']:.2f} | {savings_pct:+.2f}% | "
            f"{diff['mean_token_pct']:+.2f}% | {mode_summary['success_rate'] * 100:.2f}% |"
        )

    lines.append("")
    lines.append("#### 📈 Industry Reference Ranges / 行业典型优化区间（参考）")
    lines.append("")
    for en_name, zh_name, range_text, note in INDUSTRY_RANGE_ITEMS:
        lines.append(f"- **{en_name}（{zh_name}）**: {range_text} ({note})")
    lines.append("")
    lines.append("> These ranges are not fixed guarantees; actual gains depend on workload and model behavior.")
    lines.append("> 行业区间仅作参考，不代表固定收益；实际效果请以本仓库实测数据为准。")
    lines.append("")
    lines.append("#### 💡 Why This Matters / 为什么这对你重要")
    lines.append(
        "- **EN:** Efficient optimization pipelines can reduce token cost while maintaining quality by combining compression, caching, routing, and retrieval strategies."
    )
    lines.append(
        "- **中文：** 通过压缩、缓存、路由和检索等策略组合，可在保证质量的同时系统性降低 Token 成本。"
    )
    lines.append("")
    lines.append("#### 🔗 References / 来源")
    lines.append("")
    for label, url in INDUSTRY_SOURCES:
        lines.append(f"- {label}: {url}")
    lines.append("")
    lines.append("#### 🔎 SEO Keywords / 搜索关键词")
    lines.append(
        "- LLM cost optimization, token reduction, prompt compression, semantic caching, model routing, RAG, LLM 成本优化, Token 节省, 提示压缩, 语义缓存"
    )

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


def _to_readme_relative_path(target_path: Path, readme_path: Path) -> str:
    if target_path.is_absolute():
        rel = os.path.relpath(str(target_path), str(readme_path.parent))
        return Path(rel).as_posix()
    return target_path.as_posix()


def build_chart_block(
    chart_path: Path,
    readme_path: Path,
    *,
    alt_text: str,
    width: int,
) -> str:
    relative_path = _to_readme_relative_path(chart_path, readme_path)
    if width > 0:
        return f'<img src="{relative_path}" alt="{alt_text}" width="{width}" />'
    return f"![{alt_text}]({relative_path})"


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
        updated_candidate, replaced = _replace_marked_block(
            updated,
            start_marker,
            end_marker,
            metrics_block,
        )
        if replaced:
            updated = updated_candidate
            metrics_replaced = True
            break
    if not metrics_replaced:
        replacement = f"{LEGACY_START_MARKER}\n{metrics_block}\n{LEGACY_END_MARKER}"
        updated = updated.rstrip() + "\n\n" + replacement + "\n"

    if chart_block is not None:
        updated_candidate, chart_replaced = _replace_marked_block(
            updated,
            CHART_START_MARKER,
            CHART_END_MARKER,
            chart_block,
        )
        if chart_replaced:
            updated = updated_candidate
        else:
            section = (
                "\n\n## 📊 策略对比图表（自动插入）\n\n"
                f"{CHART_START_MARKER}\n{chart_block}\n{CHART_END_MARKER}\n"
            )
            updated = updated.rstrip() + section

    readme_path.write_text(updated, encoding="utf-8")


def resolve_comparison_path(path_text: str) -> Path:
    requested = Path(path_text)
    if requested.exists():
        return requested

    fallback_candidates = (
        Path("metrics/reports/compare-real/comparison-real.json"),
        Path("metrics/reports/compare-real/comparison.json"),
    )
    for candidate in fallback_candidates:
        if candidate.exists():
            return candidate
    return requested


def resolve_chart_path(chart_path_text: str | None, comparison_path: Path) -> Path:
    if chart_path_text:
        return Path(chart_path_text)
    return comparison_path.parent / "comparison_summary.png"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update README metrics from comparison JSON.")
    parser.add_argument(
        "--comparison",
        type=str,
        default="metrics/reports/compare-real/comparison.json",
        help="Path to comparison JSON generated by metrics.report.",
    )
    parser.add_argument(
        "--readme",
        type=str,
        default="README.md",
        help="README file path to patch.",
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
        help=(
            "Chart image path for README insertion. "
            "Defaults to sibling of comparison JSON: comparison_summary.png"
        ),
    )
    parser.add_argument(
        "--chart-alt",
        type=str,
        default="LLM Token Savings and Cost Optimization Results / LLM 成本节省对比图",
        help="Alt text for inserted chart image.",
    )
    parser.add_argument(
        "--chart-width",
        type=int,
        default=0,
        help="Optional chart width in px. If >0 uses HTML <img> tag.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    comparison_path = resolve_comparison_path(args.comparison)
    readme_path = Path(args.readme)

    summary = load_summary(comparison_path)
    metrics_block = build_metrics_block(summary)
    chart_block: str | None = None
    if not args.no_chart:
        chart_path = resolve_chart_path(args.chart_path, comparison_path)
        chart_block = build_chart_block(
            chart_path,
            readme_path,
            alt_text=args.chart_alt,
            width=args.chart_width,
        )

    update_readme_blocks(
        readme_path,
        metrics_block=metrics_block,
        chart_block=chart_block,
    )
    print(f"Updated README metrics block: {readme_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
