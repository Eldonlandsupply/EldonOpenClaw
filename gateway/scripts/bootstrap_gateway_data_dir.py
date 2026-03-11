#!/usr/bin/env python3
"""Create required data directories."""

import os
from pathlib import Path

data_dir = Path(os.getenv("DATA_DIR", "./data"))
dirs = [data_dir, data_dir / "attachments", Path("./agents")]

for d in dirs:
    d.mkdir(parents=True, exist_ok=True)
    print(f"Created: {d}")

print("Bootstrap complete.")
