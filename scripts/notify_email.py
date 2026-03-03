#!/usr/bin/env python3
"""Send guardrail notification via SMTP email."""

from __future__ import annotations

import argparse
import os
import smtplib
import ssl
import sys
from email.mime.text import MIMEText
from pathlib import Path


def _read_text(*, body: str | None, body_file: str | None) -> str:
    if body_file:
        path = Path(body_file)
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    return (body or "").strip()


def send_email(subject: str, body: str) -> int:
    smtp_server = os.getenv("EMAIL_SMTP_SERVER", "").strip()
    smtp_port = int(os.getenv("EMAIL_SMTP_PORT", "587") or "587")
    user = os.getenv("EMAIL_USER", "").strip()
    pwd = os.getenv("EMAIL_PASSWORD", "").strip()
    to_raw = os.getenv("EMAIL_TO", "").strip()

    recipients = [item.strip() for item in to_raw.split(",") if item.strip()]

    if not smtp_server or not user or not pwd or not recipients:
        print(
            "[Email] skip: EMAIL_SMTP_SERVER/EMAIL_USER/EMAIL_PASSWORD/EMAIL_TO is not fully configured"
        )
        return 0

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = ", ".join(recipients)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_server, smtp_port, timeout=20) as server:
            server.starttls(context=context)
            server.login(user, pwd)
            server.sendmail(user, recipients, msg.as_string())
        print(f"[Email] sent to: {recipients}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[Email] error: {exc}", file=sys.stderr)
        return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send email notification")
    parser.add_argument("--subject", required=True, help="Email subject")
    parser.add_argument("--body", default=None, help="Email body")
    parser.add_argument("--body-file", default=None, help="Path to markdown/text file")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    body = _read_text(body=args.body, body_file=args.body_file)
    return send_email(args.subject, body)


if __name__ == "__main__":
    raise SystemExit(main())
