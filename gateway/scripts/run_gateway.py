#!/usr/bin/env python3
"""
Run the OpenClaw gateway server.
Usage: python scripts/run_gateway.py
"""

import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from aiohttp import web
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

from app.main import create_app

if __name__ == "__main__":
    port = int(os.getenv("GATEWAY_PORT", "8443"))
    host = os.getenv("GATEWAY_HOST", "0.0.0.0")
    print(f"Starting OpenClaw gateway on {host}:{port}")
    print(f"Telegram: {os.getenv('ENABLE_TELEGRAM', 'true')}")
    print(f"SMS: {os.getenv('ENABLE_SMS', 'false')}")
    web.run_app(create_app(), host=host, port=port)
