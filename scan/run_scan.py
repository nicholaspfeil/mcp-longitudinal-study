"""Clone this week's repositories and run the credential detector on each.

Tier 3. Ties together the pieces decided in session 15:

    scan.worklist.select_repos   which repos to scan (decision A)
    scan.detect.scan_repo        what to look for
    docs/scan-schema.md          what gets written (decisions B and C)

One scan line is written for EVERY repository attempted, whatever happens to
it. A missing line must only ever mean "not attempted" -- never "clean".

Sharding: the work list is split into N shards by a stable hash of the URL, so
shard i always gets the same repos for the same list, and the Actions workflow
runs the shards as parallel jobs. Python's built-in hash() is NOT used: it is
randomised per process for strings, so two shards would disagree about who owns
what, and some repos would be scanned twice and others never.

Usage:
    python -m scan.run_scan --limit 10                # try it locally
    python -m scan.run_scan --shard 3 --shards 16     # one shard of a real run
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from scan.check_repos import USER_AGENT
from scan.detect import RULES_VERSION, scan_repo
from scan.worklist import load_latest_liveness, load_scan_history, select_repos

# A shallow clone is ~3.4s on average. Three minutes is ~50x that, so anything
# hitting it is genuinely huge or stuck. Those become status "timeout" -- kept
# separate from "unreachable" because they are NOT random: the same large repos
# will hit it every week. If the timeout count grows, raise this rather than
# accept a study that silently never looks at big projects.
CLONE_TIMEOUT_SECONDS = 180

# docs/ethics.md, "Be gentle". 8 shards at a time x 3 workers = 24 concurrent
# clones at most. Not a hurry; the study runs for a year.
WORKERS_PER_SHARD = 3

GIT_ENV = {
    **os.environ,
    "GIT_HTTP_USER_AGENT": USER_AGENT,
    # Never authenticate -- see check_repos.check_one for why each is needed.
    "GIT_TERMINAL_PROMPT": "0",
    "GCM_INTERACTIVE": "never",
    "GIT_ASKPASS": "",
    "SSH_ASKPASS": "",
    # Do not download Git LFS objects. They are large binaries by definition,
    # never hand-written source, and would turn a 3-second clone into minutes.
    "GIT_LFS_SKIP_SMUDGE": "1",
}


def shard_of(url: str, shards: int) -> int:
    """Stable shard number for a URL. Same answer on every machine, forever."""
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % shards


def classify_clone_error(stderr: str) -> str:
    """Map git's error text to a scan status. Keep in step with check_repos."""
    e = stderr.lower()
    # "not found" is GitHub's answer for deleted repos; a request for
    # credentials is what a private (or deleted) repo looks like anonymously.
    # Both mean "not publicly readable", which is death for this study.
    if "not found" in e or "could not read username" in e or "authentication" in e:
        return "not_found"
    return "unreachable"


def _force_remove(func, path, _exc) -> None:
    """Let rmtree delete git's read-only object files on Windows."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def scan_one(url: str) -> tuple[dict, list[dict]]:
    """Clone one repository, scan it, delete it. Returns (scan line, findings).

    Never raises. Every outcome, including our own bugs, becomes a scan line,
    because one bad repo must not end a run over thousands.
    """
    observed_at = datetime.now(timezone.utc).isoformat()
    line = {
        "repository_url": url,
        "observed_at": observed_at,
        "commit_sha": None,
        "rules_version": RULES_VERSION,
        "status": None,
        "n_findings": None,
        "error": None,
    }
    findings: list[dict] = []
    workdir = Path(tempfile.mkdtemp(prefix="mcpscan-"))
    checkout = workdir / "repo"

    try:
        proc = subprocess.run(
            [
                "git",
                "-c", "credential.helper=",
                # Check symlinks out as small text files holding the target
                # path. A repo can contain a symlink to anywhere on the runner;
                # followed, it would scan files that are not the repo's code.
                "-c", "core.symlinks=false",
                "clone",
                "--depth", "1",        # newest commit only; history is not scanned
                "--single-branch",     # default branch only, matching check_repos' HEAD
                "--no-tags",
                "--quiet",
                url, str(checkout),
            ],
            capture_output=True, text=True,
            timeout=CLONE_TIMEOUT_SECONDS, env=GIT_ENV,
        )
        if proc.returncode != 0:
            line["status"] = classify_clone_error(proc.stderr)
            line["error"] = (proc.stderr.strip().splitlines() or ["no output"])[-1][:200]
            return line, findings

        # Decision C: record the commit we actually cloned, read from the
        # checkout itself, not the SHA the liveness check saw days earlier.
        line["commit_sha"] = subprocess.run(
            ["git", "-C", str(checkout), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()

        try:
            found = scan_repo(checkout)
        except Exception as exc:  # noqa: BLE001 - our bug, recorded as such
            line["status"] = "scan_error"
            line["error"] = f"{type(exc).__name__}: {exc}"[:200]
            return line, findings

        line["status"] = "scanned"
        line["n_findings"] = len(found)
        # Only the link fields plus what scan_text returned. Facts about the
        # scan (commit, rules version) live on the scan line alone.
        findings = [{"repository_url": url, "observed_at": observed_at, **f} for f in found]

    except subprocess.TimeoutExpired:
        line["status"] = "timeout"
        line["error"] = f"clone exceeded {CLONE_TIMEOUT_SECONDS}s"
    except Exception as exc:  # noqa: BLE001
        line["status"] = "scan_error"
        line["error"] = f"{type(exc).__name__}: {exc}"[:200]
    finally:
        # A leftover temp dir costs disk; a raise here would cost the scan line.
        try:
            shutil.rmtree(workdir, onexc=_force_remove)
        except OSError:
            pass

    return line, findings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--shards", type=int, default=1)
    parser.add_argument("--limit", type=int, default=None,
                        help="scan only the first N of this shard (for trying it out)")
    parser.add_argument("--run-stamp", default=None,
                        help="shared timestamp naming every shard's files in one run")
    parser.add_argument("--out-dir", default="data/scans")
    parser.add_argument("--workers", type=int, default=WORKERS_PER_SHARD)
    args = parser.parse_args()

    if not 0 <= args.shard < args.shards:
        raise SystemExit(f"--shard must be in 0..{args.shards - 1}")

    urls = select_repos(load_latest_liveness(), load_scan_history())
    mine = [u for u in urls if shard_of(u, args.shards) == args.shard]
    if args.limit:
        mine = mine[:args.limit]

    stamp = args.run_stamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = f"{stamp}-shard{args.shard:02d}of{args.shards:02d}"
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    scans_path = out_dir / f"scans-{suffix}.jsonl"
    findings_path = out_dir / f"findings-{suffix}.jsonl"

    print(f"work list: {len(urls):,} repos; shard {args.shard}/{args.shards} "
          f"takes {len(mine):,}, {args.workers} workers\n", flush=True)

    # Written as .partial and renamed at the end, same as check_repos: a file
    # without .partial is a finished shard, so a killed one is never mistaken
    # for a complete observation.
    scans_tmp = scans_path.with_name(scans_path.name + ".partial")
    findings_tmp = findings_path.with_name(findings_path.name + ".partial")

    counts: dict[str, int] = {}
    total_findings = 0
    started = time.time()
    with scans_tmp.open("w", encoding="utf-8") as scans_out, \
         findings_tmp.open("w", encoding="utf-8") as findings_out:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            for i, (line, findings) in enumerate(pool.map(scan_one, mine), 1):
                scans_out.write(json.dumps(line, ensure_ascii=False) + "\n")
                for f in findings:
                    findings_out.write(json.dumps(f, ensure_ascii=False) + "\n")
                counts[line["status"]] = counts.get(line["status"], 0) + 1
                total_findings += len(findings)

                if i % 50 == 0 or i == len(mine):
                    scans_out.flush()
                    rate = i / (time.time() - started)
                    print(f"  {i:>5,}/{len(mine):,}  {rate:4.1f}/s  "
                          f"{total_findings} finding(s) so far", flush=True)

    scans_tmp.replace(scans_path)
    findings_tmp.replace(findings_path)

    print(f"\nwrote {scans_path} and {findings_path}")
    for status, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {status:<12} {n:>6,}")
    print(f"  findings     {total_findings:>6,}")
    print(f"  took {(time.time() - started) / 60:.1f} min")


if __name__ == "__main__":
    main()
