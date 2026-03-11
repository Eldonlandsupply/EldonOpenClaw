#!/usr/bin/env python3
"""
Register the Telegram webhook URL.
Usage: python scripts/setup_telegram_webhook.py https://your.domain.com
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.services.telegram_service import set_webhook, get_webhook_info


async def main():
    if len(sys.argv) < 2:
        print("Usage: python setup_telegram_webhook.py <BASE_URL>")
        print("Example: python setup_telegram_webhook.py https://mypi.duckdns.org")
        sys.exit(1)

    base_url = sys.argv[1].rstrip("/")
    webhook_url = f"{base_url}/webhooks/telegram"
    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")

    print(f"Setting webhook to: {webhook_url}")
    result = await set_webhook(webhook_url, secret_token=secret or None)
    print(f"Result: {result}")

    print("\nWebhook info:")
    info = await get_webhook_info()
    print(info)


asyncio.run(main())
