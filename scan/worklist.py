"""Decide which repositories the scanner should clone this week.

Decision A of the scan pipeline (session 15). The output schema it reads is in
docs/scan-schema.md -- read that first.

The rule, as decided:

    Scan a repository if it is reachable in the newest liveness file AND we
    have no successful scan of the commit it is on now.

Compare against the last SCANNED commit, never against last week's liveness
SHA. Comparing liveness-to-liveness means a repo whose first scan failed, and
which then never changes, is never scanned again -- and quiet, abandoned repos
are exactly where unfixed leaks live.

Usage:
    python -m scan.worklist                # summary of this week's work list
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_STATE_DIR = Path("data/repo-state")
SCANS_DIR = Path("data/scans")


def load_jsonl(path: Path) -> list[dict]:
    """Read a JSON Lines file into a list of dicts. Mechanical."""
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_latest_liveness() -> list[dict]:
    """Rows of the newest liveness file. Mechanical.

    Filenames carry a sortable UTC timestamp, so the last one sorted is newest.
    """
    files = sorted(REPO_STATE_DIR.glob("repos-*.jsonl"))
    if not files:
        raise SystemExit(f"No liveness files in {REPO_STATE_DIR}")
    return load_jsonl(files[-1])


def load_scan_history() -> list[dict]:
    """Every scan line ever written, oldest file first. Mechanical.

    Empty list before the first scan has run -- which is the case right now,
    and select_repos() must handle it.
    """
    rows: list[dict] = []
    for path in sorted(SCANS_DIR.glob("scans-*.jsonl")):
        rows.extend(load_jsonl(path))
    return rows


def select_repos(liveness: list[dict], scan_history: list[dict]) -> list[str]:
    """Return the repository URLs to scan this week.

    ---- YOUR JOB. ----

    Inputs:
      liveness      rows from the newest liveness file. Each has at least
                    "repository_url", "reachable" (bool) and "head_sha"
                    (str, or None when unreachable).
      scan_history  every scan line ever written, in the docs/scan-schema.md
                    format. Each has at least "repository_url", "commit_sha"
                    and "status". May be empty.

    Output:
      A sorted list of repository URLs, with NO duplicates.

    The shape of the work:
      1. From scan_history, build the set of (repository_url, commit_sha)
         pairs that were scanned SUCCESSFULLY. Which status counts as success?
      2. Walk liveness. Keep a URL if it is reachable and its
         (repository_url, head_sha) pair is NOT in that set.
      3. Return the kept URLs, de-duplicated and sorted.

    Things that are easy to get wrong:
      - Liveness has one row per SERVER, and 16% of servers share a repo URL.
        The same URL appears several times. Scan it once.
      - Only one status means "we successfully read this commit". A repo
        whose last attempt timed out must come back next week.
      - An unreachable row has head_sha None. Do not let it through.
      - Why a set of pairs, and not a dict of url -> last scanned sha? Think
        about it, and be ready to explain your choice either way. (Hint:
        repos can be force-pushed back to an older commit.)
      - Sorted output is not cosmetic. The same inputs must always produce
        the same list, in the same order, so a run can be reproduced.

    Roughly 8-12 lines.
    """
    raise NotImplementedError("select_repos is Nicholas's to write")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    liveness = load_latest_liveness()
    history = load_scan_history()
    urls = select_repos(liveness, history)

    live_urls = {r["repository_url"] for r in liveness if r["reachable"]}
    print(f"liveness rows:        {len(liveness):,}")
    print(f"unique live URLs:     {len(live_urls):,}")
    print(f"past scan lines:      {len(history):,}")
    print(f"to scan this week:    {len(urls):,}")


if __name__ == "__main__":
    main()
