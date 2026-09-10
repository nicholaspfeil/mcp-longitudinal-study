"""Compare two registry snapshots and report what changed between them.

This is the first code in the project that uses the time dimension. Everything
before it described a single moment; this describes a transition.

Deliberately prints a summary rather than writing an event file. The event
schema is an expensive, hard-to-reverse decision and should be made against
real numbers, the same way the storage decision was. Look first.

Usage:
    python -m scan.diff                       # two newest snapshots
    python -m scan.diff OLD.jsonl NEW.jsonl   # specific pair
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

# The registry nests its bookkeeping under this very long key. Note this is the
# _meta on `entry`, present 100% of the time -- NOT the server-level `_meta`,
# which is publisher-supplied and present in only ~4% of records.
META_KEY = "io.modelcontextprotocol.registry/official"

# If more than this share of servers vanish between two snapshots, assume the
# snapshot is bad rather than the ecosystem. See the note in summarise().
MASS_DISAPPEARANCE_THRESHOLD = 0.05


def load_snapshot(path: Path) -> tuple[dict[str, dict], str]:
    """Read one snapshot file.

    You do not need to modify this. It is the mechanical part.

    Returns (entries_by_name, observed_at) where entries_by_name maps a
    server's `name` to its full raw entry, and observed_at is the timestamp
    the collector recorded when it started the walk.

    Raises if two records share a name. Every snapshot so far has had exactly
    one entry per name, and everything downstream assumes it -- so this
    asserts the assumption instead of trusting it. An assumption that is
    checked on every run is a fact; one that is merely believed is a bug
    waiting for a quiet week.
    """
    by_name: dict[str, dict] = {}
    observed_at = ""

    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            record = json.loads(line)
            observed_at = record["observed_at"]
            entry = record["entry"]
            name = entry["server"]["name"]
            if name in by_name:
                raise ValueError(
                    f"{path.name} line {line_no}: duplicate name {name!r}. "
                    f"Identity is not unique in this snapshot, so every "
                    f"comparison downstream is unsound. Investigate before "
                    f"going further."
                )
            by_name[name] = entry

    return by_name, observed_at


def status_of(entry: dict) -> str | None:
    """Pull the registry status out of an entry's _meta block.

    You do not need to modify this. It exists mostly so the long key name
    appears once instead of five times.
    """
    return entry.get("_meta", {}).get(META_KEY, {}).get("status")


def diff_snapshots(old: dict[str, dict], new: dict[str, dict]) -> dict[str, list]:
    """Compare two snapshots and return the events between them.

    ---- YOUR JOB. ----

    Contract:
      - `old` and `new` are the entries_by_name dicts from load_snapshot().
      - Returns a dict with exactly these five keys, each holding a list:

            "appeared"            names present in new but not old
            "disappeared"         names present in old but not new
            "version_changed"     (name, old_version, new_version)
            "description_changed" (name, old_description, new_description)
            "status_changed"      (name, old_status, new_status)

      - The three "changed" lists only ever contain names present in BOTH
        snapshots. A server that appeared has not "changed version"; it has
        appeared. Keep the categories disjoint or the counts will not add up
        and you will not be able to tell why.

    The shape of the work:
      - Names are the identity. Getting the three sets you need -- only in
        old, only in new, in both -- is three lines if you use set operations
        on `old.keys()` and `new.keys()`. Look up `-` and `&` on sets.
      - Then one loop over the names in both, comparing three fields.

    Things that are easy to get wrong:
      - `version` and `description` live on entry["server"]. `status` does
        not; use status_of(). If you reach for entry["server"]["_meta"] you
        will get None for ~96% of records and silently find no changes.
      - A server can change more than one field at once. It belongs in every
        list that applies, not just the first one you check.
      - Compare descriptions exactly. Whether "trailing whitespace changed"
        counts as a real change is a research decision, and quietly
        normalising it is you making that decision without noticing.

    Roughly 20 lines.
    """
    raise NotImplementedError("Nicholas writes this one.")


def summarise(events: dict[str, list], old_count: int, new_count: int,
              old_at: str, new_at: str) -> None:
    """Print the report. Mechanical; you do not need to modify this."""
    print(f"old snapshot: {old_count:>7,} entries   observed {old_at}")
    print(f"new snapshot: {new_count:>7,} entries   observed {new_at}")
    print(f"net change:   {new_count - old_count:>+7,}\n")

    for kind in ("appeared", "disappeared", "version_changed",
                 "description_changed", "status_changed"):
        items = events.get(kind, [])
        print(f"  {kind:<22} {len(items):>6,}")

    # A snapshot that lost a large fraction of its servers is far more likely
    # to be a bad snapshot than a real extinction event. Saying so loudly is
    # the difference between noticing and publishing it.
    if old_count and len(events.get("disappeared", [])) / old_count > MASS_DISAPPEARANCE_THRESHOLD:
        share = len(events["disappeared"]) / old_count
        print(f"\n  *** {share:.1%} of servers disappeared. That is more likely")
        print(f"      a truncated snapshot than a real event. Check before")
        print(f"      treating any of these as deletions. ***")

    for kind in ("appeared", "disappeared", "version_changed",
                 "description_changed", "status_changed"):
        items = events.get(kind, [])
        if not items:
            continue
        print(f"\n{kind} -- first 5 of {len(items):,}:")
        for item in items[:5]:
            print(f"  {item}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("old", nargs="?", help="older snapshot (default: second newest)")
    parser.add_argument("new", nargs="?", help="newer snapshot (default: newest)")
    args = parser.parse_args()

    if args.old and args.new:
        old_path, new_path = Path(args.old), Path(args.new)
    else:
        snapshots = sorted(Path("data/raw").glob("registry-*.jsonl"))
        if len(snapshots) < 2:
            raise SystemExit("Need at least two snapshots to diff.")
        old_path, new_path = snapshots[-2], snapshots[-1]

    print(f"comparing {old_path.name} -> {new_path.name}\n")

    old, old_at = load_snapshot(old_path)
    new, new_at = load_snapshot(new_path)
    events = diff_snapshots(old, new)
    summarise(events, len(old), len(new), old_at, new_at)


if __name__ == "__main__":
    main()
