"""Freeze the study panel: the fixed set of servers followed for the year.

WRITE ONCE. RUN ONCE. DO NOT REGENERATE.

A panel is the group of subjects a longitudinal study follows over time -- the
same subjects, not "whoever is there this week." Deciding membership once, on a
recorded date, is what lets a trend mean "these servers changed" rather than
"different servers showed up."

Why this script refuses to overwrite an existing panel:

    Regenerating the panel later would select from servers that still exist
    later. That silently selects for servers which do not die, and the study
    would then measure how often they die. The answer would look clean and be
    completely wrong. This is survivorship bias, and the cheapest defence is
    making the mistake impossible rather than remembering not to make it.

Membership criteria, decided 2026-09-10 (see docs/sessions.md session 11):

    Every server in the source snapshot that has a `repository` field.

    Servers without a repository can never enter Tier 2 static analysis -- no
    source code to read -- so they cannot contribute to the security outcome
    this study measures. They continue to be collected weekly and remain
    available for Tier 1 analysis; they are simply not panel members.

    No other filter. Deprecated servers ARE included: deprecation is a state
    the study measures, and excluding it would bias the result toward servers
    that were healthy on day one.

The analysis strategy is Option B (open population, report both). Everything
keeps being collected. This file records who was here at the start, so results
can be computed over the panel, over everything, or both -- a choice that stays
open only because the list was written down today.

Usage:
    python -m scan.freeze_panel
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

META_KEY = "io.modelcontextprotocol.registry/official"


def build_panel(snapshot_path: Path) -> dict:
    """Read a snapshot and return the panel manifest.

    Stores enough per server to drive Tier 2 without re-reading a 30 MB
    snapshot: identity, publisher, and where the source lives. Version and
    status are recorded as they were at freeze time, so "what changed since
    the panel started" is answerable without hunting for the original file.
    """
    servers = []
    observed_at = ""
    skipped_no_repo = 0

    with snapshot_path.open(encoding="utf-8") as f:
        for line in f:
            record = json.loads(line)
            observed_at = record["observed_at"]
            entry = record["entry"]
            server = entry["server"]

            repository = server.get("repository")
            if not repository:
                skipped_no_repo += 1
                continue

            meta = entry.get("_meta", {}).get(META_KEY, {})
            name = server["name"]
            servers.append({
                "name": name,
                # Reverse-DNS namespace before the slash. Recorded now so
                # publisher-weighted analysis stays possible without having to
                # re-derive it, and because one publisher producing thousands
                # of servers is a known distortion in this data.
                "publisher": name.split("/")[0],
                "repository_url": repository.get("url"),
                "repository_source": repository.get("source"),
                "version_at_freeze": server.get("version"),
                "status_at_freeze": meta.get("status"),
                "published_at": meta.get("publishedAt"),
            })

    return {
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "source_snapshot": snapshot_path.name,
        "source_observed_at": observed_at,
        "criteria": "every server in the source snapshot with a repository field",
        "analysis_strategy": "Option B -- open population, report panel and all-servers side by side",
        "count": len(servers),
        "excluded_no_repository": skipped_no_repo,
        "servers": servers,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", nargs="?",
                        help="snapshot to freeze from (default: newest)")
    parser.add_argument("--out-dir", default="data")
    args = parser.parse_args()

    if args.snapshot:
        snapshot_path = Path(args.snapshot)
    else:
        snapshots = sorted(Path("data/raw").glob("registry-*.jsonl"))
        if not snapshots:
            raise SystemExit("No snapshots in data/raw.")
        snapshot_path = snapshots[-1]

    # Refuse if ANY panel already exists, not just one with today's name. A
    # second panel file would be a second answer to a question that must have
    # exactly one.
    out_dir = Path(args.out_dir)
    existing = sorted(out_dir.glob("panel-*.json"))
    if existing:
        raise SystemExit(
            f"A panel already exists: {existing[0]}\n"
            f"Refusing to create another. The panel is frozen once, on purpose.\n"
            f"Re-picking it later would select for servers that survived, and\n"
            f"the study would then be measuring survival in a sample chosen for\n"
            f"surviving. If you genuinely need to change the membership rule,\n"
            f"write down why in docs/sessions.md first, then move the old file\n"
            f"aside by hand so the decision leaves a trace."
        )

    print(f"reading {snapshot_path.name} ...")
    panel = build_panel(snapshot_path)

    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = out_dir / f"panel-{stamp}.json"

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(panel, f, indent=2, ensure_ascii=False)

    total = panel["count"] + panel["excluded_no_repository"]
    publishers = {s["publisher"] for s in panel["servers"]}
    sources: dict[str, int] = {}
    for s in panel["servers"]:
        sources[s["repository_source"] or "unknown"] = sources.get(s["repository_source"] or "unknown", 0) + 1

    print(f"\npanel frozen -> {out_path}")
    print(f"  members            {panel['count']:>7,}  ({panel['count']/total:.1%} of snapshot)")
    print(f"  excluded (no repo) {panel['excluded_no_repository']:>7,}")
    print(f"  distinct publishers{len(publishers):>7,}")
    for source, count in sorted(sources.items(), key=lambda kv: -kv[1]):
        print(f"  {source:<18} {count:>7,}")
    print(f"\n  source observed at {panel['source_observed_at']}")
    print("\nThis file is now permanent. Commit it and do not regenerate it.")


if __name__ == "__main__":
    main()
