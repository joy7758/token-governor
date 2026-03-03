#!/usr/bin/env python3
"""Send guardrail notification to Slack webhook."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib import request


def _read_text(*, text: str | None, text_file: str | None) -> str:
    if text_file:
        path = Path(text_file)
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    return (text or "").strip()


def send_slack_notification(title: str, text: str) -> int:
    webhook_url = os.getenv("SLACK_WEBHOOK_URL", "").strip()
    if not webhook_url:
        print("[Slack] skip: SLACK_WEBHOOK_URL is not configured")
        return 0

    payload = {"text": f"*{title}*\n{text}".strip()}
    req = request.Request(
        webhook_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=15) as resp:  # noqa: S310
            body = resp.read().decode("utf-8", errors="replace")
            print(f"[Slack] status={resp.status}, resp={body}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[Slack] error: {exc}", file=sys.stderr)
        return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send Slack notification")
    parser.add_argument("--title", required=True, help="Notification title")
    parser.add_argument("--text", default=None, help="Notification text")
    parser.add_argument("--text-file", default=None, help="Path to markdown/text file")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    text = _read_text(text=args.text, text_file=args.text_file)
    return send_slack_notification(args.title, text)


if __name__ == "__main__":
    raise SystemExit(main())
