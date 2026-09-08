"""
Walk the official MCP Registry and write every server entry to a JSONL file.

This is the Tier 1 collector: registry metadata only. See docs/ethics.md.

Usage:
    python -m scan.fetch_registry
    python -m scan.fetch_registry --updated-since 2026-09-01T00:00:00Z
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE_URL = "https://registry.modelcontextprotocol.io/v0/servers"

# We identify ourselves. docs/ethics.md, "Operating rules".
# TODO(nicholas): put your real repo URL here once the repo exists.
USER_AGENT = (
    "mcp-longitudinal-study/0.1 "
    "(academic measurement research; https://github.com/USERNAME/REPO)"
)

PAGE_SIZE = 100          # tune after you find out what the API actually allows
SLEEP_BETWEEN_PAGES = 1.0  # seconds. We are never in a hurry.
MAX_PAGES = 1000         # safety rail against an infinite loop


def fetch_page(cursor: str | None = None,
               updated_since: str | None = None) -> dict:
    """Fetch ONE page from the registry. Returns the parsed JSON body.

    You do not need to modify this. It is the single-request building block
    that fetch_all_servers() calls in a loop.

    The response looks like:
        {
          "servers":  [ {"server": {...}, "_meta": {...}}, ... ],
          "metadata": {"nextCursor": "some-string", "count": 100}
        }

    When there are no more pages, "nextCursor" is absent from "metadata".
    """
    params: dict[str, str | int] = {"limit": PAGE_SIZE, "version": "latest"}
    if cursor is not None:
        params["cursor"] = cursor
    if updated_since is not None:
        params["updated_since"] = updated_since

    response = requests.get(
        BASE_URL,
        params=params,
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def fetch_all_servers(updated_since: str | None = None) -> list[dict]:
    """Walk every page of the registry and return all server entries.

    ---- YOUR JOB. Read the spec in the session notes before starting. ----

    Contract:
      - Returns a flat list of the objects found in each page's "servers"
        array. Do not unwrap or reshape them; we want the raw records.
      - Calls fetch_page() repeatedly, passing the previous page's
        metadata.nextCursor as the next call's cursor.
      - Stops when there is no nextCursor.
      - Passes updated_since straight through on every call.

    Requirements that are easy to forget:
      - Sleep SLEEP_BETWEEN_PAGES between requests.
      - Do not loop more than MAX_PAGES times, whatever the API says.
      - If the cursor comes back identical to the one you just sent, stop.
        (Think about why this guard matters and what would happen without it.)
      - Print progress. A silent 40-page walk is impossible to debug.
    """
    raise NotImplementedError("Nicholas writes this one.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--updated-since",
        default=None,
        help="RFC3339 timestamp; only fetch entries changed since then.",
    )
    parser.add_argument(
        "--out-dir",
        default="data/raw",
        help="Where to write the JSONL snapshot.",
    )
    args = parser.parse_args()

    # The ACTUAL observation time, recorded before we start.
    # Never infer this from the schedule — see docs/sessions.md, session 2.
    observed_at = datetime.now(timezone.utc).isoformat()

    servers = fetch_all_servers(updated_since=args.updated_since)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = out_dir / f"registry-{stamp}.jsonl"

    with out_path.open("w", encoding="utf-8") as f:
        for entry in servers:
            record = {"observed_at": observed_at, "entry": entry}
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"\nWrote {len(servers)} entries to {out_path}")


if __name__ == "__main__":
    main()
