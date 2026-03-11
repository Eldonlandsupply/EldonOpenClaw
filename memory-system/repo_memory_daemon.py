"""
repo_memory_daemon.py — watches repos and keeps the index up to date.
"""
from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import yaml

from repo_indexer import discover_repos, index_repos, load_config

logging.basicConfig(
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "msg": "%(message)s"}',
)
logger = logging.getLogger("repo_memory_daemon")

_running = True


def _handle_signal(sig, frame):
    global _running
    logger.info("Signal received — shutting down daemon")
    _running = False


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


def pull_repos(cfg: dict):
    repos = discover_repos(cfg.get("repo_root", "~/eldon/repos"))
    for repo in repos:
        try:
            result = subprocess.run(
                ["git", "pull", "--ff-only"],
                cwd=repo,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if "Already up to date" not in result.stdout:
                logger.info(f"Pulled updates for {repo.name}: {result.stdout.strip()}")
        except Exception as e:
            logger.warning(f"git pull failed for {repo.name}: {e}")


def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    cfg = load_config(config_path)
    interval = cfg.get("scan_interval_seconds", 600)

    logger.info(f"Repo memory daemon started. Scan interval: {interval}s")

    # Initial full index on startup
    logger.info("Running initial index build...")
    try:
        n = index_repos(cfg)
        logger.info(f"Initial index complete: {n} chunks")
    except Exception as e:
        logger.error(f"Initial index failed: {e}")

    while _running:
        logger.info(f"Sleeping {interval}s until next scan...")
        for _ in range(interval):
            if not _running:
                break
            time.sleep(1)

        if not _running:
            break

        logger.info("Pulling repos...")
        try:
            pull_repos(cfg)
        except Exception as e:
            logger.warning(f"Pull phase error: {e}")

        logger.info("Running incremental index update...")
        try:
            n = index_repos(cfg)
            logger.info(f"Incremental update complete: {n} new/changed chunks")
        except Exception as e:
            logger.error(f"Index update failed: {e}")

    logger.info("Daemon stopped cleanly")


if __name__ == "__main__":
    main()
