"""Describe what's actually in a registry snapshot."""
import json
from collections import Counter
from pathlib import Path

# The registry nests its bookkeeping under this very long key.
META_KEY = "io.modelcontextprotocol.registry/official"

# Newest snapshot in data/raw
path = sorted(Path("data/raw").glob("registry-*.jsonl"))[-1]

# --- counters, set up before the loop ---
names = set()
total = 0
with_repo = 0
with_packages = 0
with_remotes = 0
repo_sources = Counter()
statuses = Counter()
published = []

# --- one pass over the file, updating counters as records go by ---
with path.open(encoding="utf-8") as f:
    for line in f:
        record = json.loads(line)
        entry = record["entry"]
        server = entry["server"]
        meta = entry.get("_meta", {}).get(META_KEY, {})

        total += 1
        names.add(server["name"])

        repository = server.get("repository")
        if repository:
            with_repo += 1
            repo_sources[repository.get("source", "unknown")] += 1

        if server.get("packages"):
            with_packages += 1

        if server.get("remotes"):
            with_remotes += 1

        statuses[meta.get("status", "MISSING")] += 1

        if "publishedAt" in meta:
            published.append(meta["publishedAt"])

# --- printing, after the loop ---
print(f"file:          {path.name}")
print(f"lines:         {total}")
print(f"unique names:  {len(names)}")

print("\nfields present:")
print(f"  repository  {with_repo:>6}  ({with_repo / total:.1%})")
print(f"  packages    {with_packages:>6}  ({with_packages / total:.1%})")
print(f"  remotes     {with_remotes:>6}  ({with_remotes / total:.1%})")

print("\nrepository sources:")
for source, count in repo_sources.most_common():
    print(f"  {source:<12} {count:>6}")

print("\nstatus breakdown:")
for status, count in statuses.most_common():
    print(f"  {status:<12} {count:>6}")

if published:
    print(f"\npublishedAt earliest: {min(published)}")
    print(f"publishedAt latest:   {max(published)}")