#!/usr/bin/env python3
"""Send guardrail notification to DingTalk webhook."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib import request


def _read_text(*, msg: str | None, msg_file: str | None) -> str:
    if msg_file:
        path = Path(msg_file)
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    return (msg or "").strip()


def send_dingtalk_notification(msg: str) -> int:
    webhook_url = os.getenv("DINGTALK_WEBHOOK_URL", "").strip()
    if not webhook_url:
        print("[DingTalk] skip: DINGTALK_WEBHOOK_URL is not configured")
        return 0

    payload = {"msgtype": "text", "text": {"content": msg}}
    req = request.Request(
        webhook_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=15) as resp:  # noqa: S310
            body = resp.read().decode("utf-8", errors="replace")
            print(f"[DingTalk] status={resp.status}, resp={body}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[DingTalk] error: {exc}", file=sys.stderr)
        return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send DingTalk notification")
    parser.add_argument("--msg", default=None, help="Message text")
    parser.add_argument("--msg-file", default=None, help="Path to markdown/text file")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    msg = _read_text(msg=args.msg, msg_file=args.msg_file)
    return send_dingtalk_notification(msg)


if __name__ == "__main__":
    raise SystemExit(main())
