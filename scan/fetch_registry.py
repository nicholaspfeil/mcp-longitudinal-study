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
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://registry.modelcontextprotocol.io/v0/servers"

# We identify ourselves. docs/ethics.md, "Operating rules".
USER_AGENT = (
    "mcp-longitudinal-study/0.1 "
    "(academic measurement research; "
    "https://github.com/nicholaspfeil/mcp-longitudinal-study)"
)

PAGE_SIZE = 100          # tune after you find out what the API actually allows
SLEEP_BETWEEN_PAGES = 1.0  # seconds. We are never in a hurry.
MAX_PAGES = 1000         # safety rail against an infinite loop

# A full walk is ~300 requests. Run weekly for a year that is ~15,700 requests
# against a free public API with no SLA, so a transient failure is not a risk
# being accepted, it is an event being scheduled. On 2026-09-10 a single 500 on
# page 53 killed a run that already held 52 pages of good data, and a lost run
# is a lost week of the series -- Monday does not come back.
#
# Retry 5xx, 429 and connection errors. Never retry 4xx: those mean we sent
# something wrong, so retrying sends the same wrong thing and turns our own bug
# into a silent hang.
RETRY_POLICY = Retry(
    total=5,
    backoff_factor=1.0,        # sleeps roughly 2s, 4s, 8s, 16s between tries
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=("GET",),  # only ever retry idempotent requests
    respect_retry_after_header=True,  # if they tell us to wait, we wait
    raise_on_status=True,      # still fail loudly once retries are exhausted
)


def _make_session() -> requests.Session:
    """One Session for the whole walk: retries, plus connection reuse."""
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    session.mount("https://", HTTPAdapter(max_retries=RETRY_POLICY))
    return session


SESSION = _make_session()


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

    response = SESSION.get(BASE_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_all_servers(updated_since: str | None = None) -> list[dict]:
    """Fetch all servers from the registry, following pagination.

    Returns a list of raw registry entries. Each entry is the full record as
    the API returned it, containing both "server" (the description) and
    "_meta" (status and timestamps). Nothing is unwrapped here — reshaping
    happens at analysis time.

    If updated_since is provided, only fetch entries changed since that timestamp.
    """
    servers: list[dict] = []
    cursor: str | None = None
    seen_cursors: set[str] = set()
    page_count = 0

    while True:
        page_count += 1
        if page_count > MAX_PAGES:
            raise RuntimeError(f"Exceeded max pages ({MAX_PAGES})")

        print(f"Fetching page {page_count} (cursor={cursor})...")
        data = fetch_page(cursor=cursor, updated_since=updated_since)
        servers.extend(data.get("servers", []))

        next_cursor = data.get("metadata", {}).get("nextCursor")

        # No cursor means the last page. This check MUST come before the
        # repeat check below: cursor=None means "start from the beginning"
        # to fetch_page(), so letting None through would silently restart
        # the walk and duplicate every entry.
        if not next_cursor:
            break

        # Pagination that does not advance. Raise rather than break — a
        # truncated snapshot written to disk is indistinguishable from a
        # real one later, and would read as a mass deletion event.
        if next_cursor in seen_cursors:
            raise RuntimeError(
                f"Registry returned an already-used cursor ({next_cursor!r}) "
                f"on page {page_count}. Pagination is not advancing; aborting "
                f"rather than looping or writing a truncated snapshot."
            )

        seen_cursors.add(next_cursor)
        cursor = next_cursor

        time.sleep(SLEEP_BETWEEN_PAGES)

    return servers


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
