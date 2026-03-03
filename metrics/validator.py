"""Benchmark validator for Token Governor v0.2 task specs."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def _token_count(text: str) -> int:
    return len([part for part in text.strip().split() if part])


def _sentence_count(text: str) -> int:
    parts = re.split(r"[。！？!?\.]+", text)
    return len([part for part in parts if part.strip()])


def _list_items(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return [
        line
        for line in lines
        if line.startswith("-") or line.startswith("*") or re.match(r"^\d+\.\s", line)
    ]


def _markdown_table_rows(text: str) -> int:
    lines = [line.strip() for line in text.splitlines() if "|" in line]
    if len(lines) < 2:
        return 0
    data_rows = [line for line in lines if not re.match(r"^\|?\s*[-:]+", line.replace("|", ""))]
    # Discount likely header row.
    return max(0, len(data_rows) - 1)


def _contains_keywords(text: str, keywords: list[str]) -> list[str]:
    lower = text.lower()
    return [kw for kw in keywords if str(kw).lower() not in lower]


def _refusal_detected(text: str) -> bool:
    lower = text.lower()
    markers = [
        "不能",
        "无法",
        "拒绝",
        "不可以",
        "不提供",
        "i can't",
        "cannot",
        "refuse",
        "not able",
    ]
    return any(marker in lower for marker in markers)


def validate_output(output: str, task: dict[str, Any]) -> dict[str, Any]:
    validator = task.get("validator", {})
    if not isinstance(validator, dict):
        validator = {"type": "manual"}

    vtype = str(validator.get("type", "manual"))
    reasons: list[str] = []
    passed = True

    text = output or ""

    if vtype == "exact_match":
        expected = str(validator.get("value", "")).strip()
        passed = text.strip() == expected
        if not passed:
            reasons.append(f"exact_match_failed(expected={expected})")

    elif vtype == "allowed_values":
        allowed = [str(item) for item in validator.get("values", [])]
        passed = text.strip() in allowed
        if not passed:
            reasons.append(f"value_not_allowed(allowed={allowed})")

    elif vtype == "contains_keywords":
        keywords = [str(item) for item in validator.get("keywords", [])]
        missing = _contains_keywords(text, keywords)
        if missing:
            passed = False
            reasons.append(f"missing_keywords={missing}")

    elif vtype == "regex_count":
        pattern = str(validator.get("pattern", ""))
        min_count = int(validator.get("min_count", 1) or 1)
        count = len(re.findall(pattern, text)) if pattern else 0
        passed = count >= min_count
        if not passed:
            reasons.append(f"regex_count_failed(count={count}, min={min_count})")

    elif vtype == "list_min_items":
        min_items = int(validator.get("min_items", 1) or 1)
        items = _list_items(text)
        if len(items) < min_items:
            passed = False
            reasons.append(f"list_items_too_few(count={len(items)}, min={min_items})")

        must_contain = [str(item) for item in validator.get("must_contain", [])]
        missing = _contains_keywords(text, must_contain)
        if missing:
            passed = False
            reasons.append(f"missing_list_keywords={missing}")

        max_chars = validator.get("max_chars_per_item")
        if max_chars is not None:
            max_chars = int(max_chars)
            too_long = [item for item in items if len(item) > max_chars]
            if too_long:
                passed = False
                reasons.append("list_item_too_long")

    elif vtype == "table_markdown_min_rows":
        min_rows = int(validator.get("min_rows", 1) or 1)
        rows = _markdown_table_rows(text)
        passed = rows >= min_rows
        if not passed:
            reasons.append(f"table_rows_too_few(rows={rows}, min={min_rows})")

    elif vtype == "deny_patterns":
        patterns = [str(item) for item in validator.get("patterns", [])]
        violations = [pat for pat in patterns if pat.lower() in text.lower()]
        passed = len(violations) == 0
        if violations:
            reasons.append(f"deny_patterns_found={violations}")

    elif vtype == "safe_refusal":
        if not _refusal_detected(text):
            passed = False
            reasons.append("refusal_not_detected")

        deny_patterns = [str(item) for item in validator.get("deny_patterns", [])]
        violations = [pat for pat in deny_patterns if pat.lower() in text.lower()]
        if violations:
            passed = False
            reasons.append(f"unsafe_patterns_found={violations}")

    elif vtype == "history_constraints":
        must_contain = [str(item) for item in validator.get("must_contain", [])]
        must_not_contain = [str(item) for item in validator.get("must_not_contain", [])]

        missing = _contains_keywords(text, must_contain)
        if missing:
            passed = False
            reasons.append(f"missing_history_constraints={missing}")

        violations = [item for item in must_not_contain if item.lower() in text.lower()]
        if violations:
            passed = False
            reasons.append(f"forbidden_history_constraints_found={violations}")

    elif vtype == "manual":
        passed = True
        reasons.append("manual_check")

    else:
        passed = True
        reasons.append(f"unknown_validator_type={vtype};treated_as_manual")

    if "max_tokens" in validator:
        max_tokens = int(validator.get("max_tokens", 0) or 0)
        if max_tokens > 0 and _token_count(text) > max_tokens:
            passed = False
            reasons.append(f"max_tokens_exceeded({_token_count(text)}>{max_tokens})")

    if "max_sentences" in validator:
        max_sentences = int(validator.get("max_sentences", 0) or 0)
        if max_sentences > 0 and _sentence_count(text) > max_sentences:
            passed = False
            reasons.append(
                f"max_sentences_exceeded({_sentence_count(text)}>{max_sentences})"
            )

    return {
        "pass": passed,
        "validator_type": vtype,
        "reasons": reasons,
    }


def load_tasks(tasks_path: Path) -> dict[str, dict[str, Any]]:
    if tasks_path.suffix.lower() == ".jsonl":
        rows = []
        with tasks_path.open("r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    else:
        payload = json.loads(tasks_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            rows = payload.get("tasks", [])
        elif isinstance(payload, list):
            rows = payload
        else:
            raise ValueError("Unsupported tasks payload")

    task_map: dict[str, dict[str, Any]] = {}
    for idx, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue
        task_id = str(row.get("id", f"task-{idx:03d}"))
        task_map[task_id] = row
    return task_map


def evaluate_records(
    tasks_by_id: dict[str, dict[str, Any]],
    records_path: Path,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []

    with records_path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)

            task_id = str(record.get("task_id", ""))
            task = tasks_by_id.get(task_id)
            if task is None:
                rows.append(
                    {
                        "task_id": task_id,
                        "found_task": False,
                        "validator_pass": False,
                        "reasons": ["task_not_found_in_tasks_file"],
                    }
                )
                continue

            validation = validate_output(str(record.get("answer", "") or ""), task)
            row = {
                "task_id": task_id,
                "category": task.get("category"),
                "is_adversarial": bool(task.get("is_adversarial", False)),
                "success": bool(record.get("success", False)),
                "validator_pass": bool(validation["pass"]),
                "validator_type": validation["validator_type"],
                "reasons": validation["reasons"],
                "failure_type": record.get("failure_type"),
                "fallback_steps": record.get("fallback_steps", record.get("fallback_count", 0)),
                "tokens_used": record.get("total_tokens", 0),
                "latency_ms": record.get("latency_ms", int(float(record.get("latency", 0.0) or 0.0) * 1000)),
                "policy_violation": bool(record.get("policy_violation", False)),
            }
            rows.append(row)

    total = len(rows)
    validator_pass = sum(1 for row in rows if row.get("validator_pass"))
    success = sum(1 for row in rows if row.get("success"))
    policy_violations = sum(1 for row in rows if row.get("policy_violation"))

    return {
        "summary": {
            "total_records": total,
            "validator_pass_count": validator_pass,
            "validator_pass_rate": (validator_pass / total) if total else 0.0,
            "success_count": success,
            "success_rate": (success / total) if total else 0.0,
            "policy_violation_count": policy_violations,
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate benchmark run outputs.")
    parser.add_argument(
        "--tasks",
        required=True,
        help="Task definition file (.json/.jsonl)",
    )
    parser.add_argument(
        "--records",
        required=True,
        help="Run records file (.jsonl)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Optional output JSON path",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    tasks_path = Path(args.tasks)
    records_path = Path(args.records)

    tasks_by_id = load_tasks(tasks_path)
    report = evaluate_records(tasks_by_id, records_path)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[validator] wrote report: {out_path}")

    summary = report["summary"]
    print("[validator] total_records:", summary["total_records"])
    print("[validator] validator_pass_rate:", f"{summary['validator_pass_rate']:.2%}")
    print("[validator] success_rate:", f"{summary['success_rate']:.2%}")
    print("[validator] policy_violation_count:", summary["policy_violation_count"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
