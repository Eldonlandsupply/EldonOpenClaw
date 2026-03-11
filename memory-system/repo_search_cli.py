#!/usr/bin/env python3
"""
repo_search_cli.py — command-line interface for semantic repo search.

Usage:
    repo-search "where is the telegram bot handler"
    repo-search "ERCOT real time price parsing" --top 5
    repo-search "MLB projection model" --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running from any directory
sys.path.insert(0, str(Path(__file__).parent))

from memory_query_engine import search_repo_memory


def main():
    parser = argparse.ArgumentParser(
        prog="repo-search",
        description="Semantic search across all repos on this machine",
    )
    parser.add_argument("query", nargs="+", help="Search query")
    parser.add_argument("--top", type=int, default=8, help="Number of results (default: 8)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument(
        "--config",
        default=str(Path(__file__).parent / "config.yaml"),
        help="Path to config.yaml",
    )
    args = parser.parse_args()

    query = " ".join(args.query)

    try:
        from repo_indexer import load_config
        from memory_query_engine import memory_search
        cfg = load_config(args.config)
        cfg["top_k"] = args.top
        results = memory_search(query, cfg)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if not results:
        print("No results found.")
        sys.exit(0)

    if args.json:
        print(json.dumps(results, indent=2))
        return

    print(f'\nSearch: "{query}"')
    print("=" * 60)

    for i, r in enumerate(results, 1):
        score_bar = "█" * int(r["score"] * 20)
        print(f"\n[{i}] {r['repo']} / {r['file']}")
        if r["function"]:
            print(f"    Function : {r['function']}")
        print(f"    Score    : {r['score']:.3f}  {score_bar}")
        if r["start_line"]:
            print(f"    Line     : {r['start_line']}")
        print(f"    Language : {r['language']}")
        print()
        snippet = r["code_snippet"].strip()
        for line in snippet.splitlines()[:12]:
            print(f"    {line}")
        if len(snippet.splitlines()) > 12:
            print("    ...")
        print("-" * 60)


if __name__ == "__main__":
    main()
