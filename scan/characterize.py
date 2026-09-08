"""Describe what's actually in a registry snapshot."""

import json
from pathlib import Path

# Newest snapshot in data/raw
path = sorted(Path("data/raw").glob("registry-*.jsonl"))[-1]

names = set()
total = 0

with path.open(encoding="utf-8") as f:
    for line in f:
        record = json.loads(line)
        names.add(record["entry"]["server"]["name"])
        total += 1

print(f"file:         {path.name}")
print(f"lines:        {total}")
print(f"unique names: {len(names)}")
print(f"duplicates:   {total - len(names)}")