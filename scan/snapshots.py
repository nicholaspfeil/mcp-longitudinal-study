"""Find, read and write registry snapshots, whichever layout they are in.

Why this exists (session 16): a snapshot used to be one file. They grew from
32.7 MB (2026-09-16) to 61.9 MB (2026-11-09), about 5.5 MB a week, and GitHub
rejects any pushed file over 100 MB, which would have stopped the weekly
snapshot around late December with nobody watching.

So from 2026-11 on, a snapshot is a DIRECTORY of parts, each under
PART_MAX_BYTES:

    data/raw/registry-20260928T154402Z.jsonl          old layout, kept as-is
    data/raw/registry-20261116T071700Z/part-000.jsonl new layout
    data/raw/registry-20261116T071700Z/part-001.jsonl

Old files are never rewritten -- history is append-only -- so every reader
must accept both layouts. Every reader goes through this module rather than
globbing data/raw itself, so the layout is decided in exactly one place.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from pathlib import Path

RAW_DIR = Path("data/raw")

# Comfortably under GitHub's 50 MB warning and 100 MB hard limit, so the
# limit is never approached however the registry grows: it just adds parts.
PART_MAX_BYTES = 40_000_000


def list_snapshots(raw_dir: Path = RAW_DIR) -> list[Path]:
    """Every COMPLETE snapshot, oldest first. Files and directories alike.

    Names start with a sortable UTC timestamp, so name order is time order.
    A directory still ending in .partial is a write that never finished and is
    not a snapshot.
    """
    found = [p for p in raw_dir.glob("registry-*.jsonl") if p.is_file()]
    found += [p for p in raw_dir.glob("registry-*") if p.is_dir() and not p.name.endswith(".partial")]
    return sorted(found, key=lambda p: p.name)


def iter_lines(snapshot: Path) -> Iterator[str]:
    """Every JSONL line of a snapshot, in order, from a file or its parts."""
    files = sorted(snapshot.glob("part-*.jsonl")) if snapshot.is_dir() else [snapshot]
    if not files:
        raise ValueError(f"{snapshot} contains no part files")
    for path in files:
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    yield line


def write_snapshot(records: Iterable[dict], out_dir: Path, stamp: str) -> Path:
    """Write records as registry-<stamp>/part-NNN.jsonl. Returns the directory.

    Written under a .partial name and renamed only once every part is on disk,
    so a run killed halfway never leaves something that looks like a snapshot.
    """
    final = out_dir / f"registry-{stamp}"
    tmp = out_dir / f"registry-{stamp}.partial"
    tmp.mkdir(parents=True, exist_ok=False)

    part, written, f = 0, 0, None
    try:
        for record in records:
            line = (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")
            if f is None or (written and written + len(line) > PART_MAX_BYTES):
                if f:
                    f.close()
                f = (tmp / f"part-{part:03d}.jsonl").open("wb")
                part, written = part + 1, 0
            f.write(line)
            written += len(line)
    finally:
        if f:
            f.close()

    tmp.rename(final)
    return final
