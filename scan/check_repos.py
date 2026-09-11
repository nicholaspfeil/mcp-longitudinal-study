"""Check whether every panel repository still exists, and what its HEAD is.

This is the Tier 2 liveness collector. It downloads no code. For each panel
member it asks the remote "what commit are you on?" via `git ls-remote`, which
transfers a single 40-character hash.

Why this exists, and why it runs before any scanner:

    Scan results are backfillable. A detector written in January can be run
    against any past commit, because git keeps history. Repo *liveness* is not
    backfillable -- once a repository is deleted or made private there is
    nothing left to ask, and the moment it vanished is unrecoverable. So the
    ephemeral signal gets collected first, exactly as registry metadata was
    collected before detectors at Tier 1.

Two things are recorded per repo, and both matter:

    reachable   A repository can die while its registry entry lives on. That
                is a SECOND, independent kind of disappearance -- a competing
                risk distinct from the server being delisted. A server can do
                either without the other.

    head_sha    The commit the default branch points at. If it is unchanged
                since last week, the code is byte-identical and there is
                nothing to re-scan. This is what makes Tier 2 affordable: a
                full clone of the panel is ~22 hours and ~28 GB, while
                checking it is ~30 minutes and no disk at all.

Measured 2026-09-11 on a 300-repo sample: 16.3% of panel repositories were
already unreachable (95% CI 12.2-20.5%), so expect roughly 3,800 dead links on
the first run. The registry does not validate the `repository` field.

Usage:
    python -m scan.check_repos
    python -m scan.check_repos --limit 100      # try a small slice first
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

# docs/ethics.md, "Operating rules": identify ourselves. git does not use our
# requests User-Agent, so it has to be set through the environment.
USER_AGENT = (
    "mcp-longitudinal-study/0.1 "
    "(academic measurement research; "
    "https://github.com/nicholaspfeil/mcp-longitudinal-study)"
)

# Deliberately modest. ~8 concurrent lightweight requests is nowhere near
# anything that could be mistaken for abuse, and finishing in 30 minutes
# instead of 15 costs us nothing -- the study runs for a year.
MAX_WORKERS = 8
TIMEOUT_SECONDS = 30


def check_one(repo: dict) -> dict:
    """Ask one remote for its HEAD commit. Downloads no code.

    Never raises: a failure here is data (the repo is gone), not an error, and
    one dead repo must not abort a run over 23,000 of them.
    """
    url = repo["repository_url"]
    started = time.time()
    result = {
        "name": repo["name"],
        "repository_url": url,
        "reachable": False,
        "head_sha": None,
        "error": None,
    }

    try:
        proc = subprocess.run(
            # -c credential.helper= disables the credential helper for this
            # call only. Without it, Git Credential Manager on Windows opens a
            # GUI sign-in window for private or missing repos -- GIT_TERMINAL_
            # PROMPT=0 does not suppress that, because it is not a terminal
            # prompt -- and the run blocks forever waiting for a human.
            #
            # We never want to authenticate here. This study reads what is
            # publicly readable; a repo we cannot read anonymously IS
            # unreachable for our purposes, and that is a finding, not a
            # problem to log into.
            ["git", "-c", "credential.helper=", "ls-remote", url, "HEAD"],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            env={
                **os.environ,
                "GIT_HTTP_USER_AGENT": USER_AGENT,
                "GIT_TERMINAL_PROMPT": "0",   # no terminal prompt
                "GCM_INTERACTIVE": "never",   # no Credential Manager GUI
                "GIT_ASKPASS": "",            # no askpass helper either
                "SSH_ASKPASS": "",
            },
        )
        if proc.returncode == 0 and proc.stdout.strip():
            result["reachable"] = True
            result["head_sha"] = proc.stdout.split()[0]
        else:
            # Distinguish "gone" from "something else went wrong". Both are
            # unreachable, but only one is interesting later.
            result["error"] = (proc.stderr.strip().splitlines() or ["empty response"])[-1][:200]
    except subprocess.TimeoutExpired:
        result["error"] = f"timeout after {TIMEOUT_SECONDS}s"
    except Exception as exc:  # noqa: BLE001 - a crash here must not end the run
        result["error"] = f"{type(exc).__name__}: {exc}"[:200]

    result["check_seconds"] = round(time.time() - started, 2)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", default=None, help="panel file (default: the one in data/)")
    parser.add_argument("--out-dir", default="data/repo-state")
    parser.add_argument("--limit", type=int, default=None,
                        help="check only the first N (for trying it out)")
    parser.add_argument("--workers", type=int, default=MAX_WORKERS)
    args = parser.parse_args()

    if args.panel:
        panel_path = Path(args.panel)
    else:
        panels = sorted(Path("data").glob("panel-*.json"))
        if not panels:
            raise SystemExit("No panel file found. Run scan.freeze_panel first.")
        panel_path = panels[0]

    panel = json.loads(panel_path.read_text(encoding="utf-8"))
    repos = panel["servers"]
    if args.limit:
        repos = repos[:args.limit]

    # The ACTUAL observation time, recorded before we start. Never inferred
    # from the schedule -- see docs/sessions.md session 2.
    observed_at = datetime.now(timezone.utc).isoformat()

    print(f"panel:   {panel_path.name} ({panel['count']:,} members)")
    print(f"checking {len(repos):,} repositories with {args.workers} workers\n")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Resume support. This run takes ~30 minutes against 23,000 external hosts,
    # so it WILL be interrupted sometimes -- killed for memory, a laptop lid,
    # a dropped network. Results are streamed to disk as they arrive and an
    # interrupted run is resumed rather than restarted, because throwing away
    # 6,000 completed checks to redo them is both wasteful and rude to the
    # hosts being re-asked.
    partial = sorted(out_dir.glob("repos-*.jsonl.partial"))
    done: dict[str, dict] = {}
    if partial and not args.limit:
        out_path = partial[-1].with_suffix("")          # repos-<stamp>.jsonl
        partial_path = partial[-1]
        with partial_path.open(encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue          # a torn last line from the kill; drop it
                done[rec["name"]] = rec
        observed_at = next(iter(done.values()))["observed_at"] if done else observed_at
        print(f"resuming: {len(done):,} already checked, "
              f"{len(repos) - len(done):,} to go\n", flush=True)
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_path = out_dir / f"repos-{stamp}.jsonl"
        partial_path = out_dir / f"repos-{stamp}.jsonl.partial"

    todo = [r for r in repos if r["name"] not in done]
    counts = {"alive": sum(1 for r in done.values() if r["reachable"]),
              "dead": sum(1 for r in done.values() if not r["reachable"])}
    results = list(done.values())

    started = time.time()
    with partial_path.open("a", encoding="utf-8") as out:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            for i, result in enumerate(pool.map(check_one, todo), 1):
                record = {"observed_at": observed_at, **result}
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                results.append(record)
                counts["alive" if result["reachable"] else "dead"] += 1

                if i % 500 == 0 or i == len(todo):
                    out.flush()          # survive a kill
                    os.fsync(out.fileno())
                    elapsed = time.time() - started
                    rate = i / elapsed
                    eta = (len(todo) - i) / rate if rate else 0
                    seen = len(done) + i
                    print(f"  {seen:>6,}/{len(repos):,}  {counts['alive']:>6,} alive  "
                          f"{rate:>5.1f}/s  eta {eta/60:>5.1f} min", flush=True)

    # Only now is the observation complete. Renaming the .partial is what marks
    # it as a finished run, so a half-written file is never mistaken for one.
    partial_path.replace(out_path)

    alive, dead = counts["alive"], counts["dead"]
    total = alive + dead
    elapsed = time.time() - started
    print(f"\nwrote {total:,} records to {out_path}")
    print(f"  reachable    {alive:>7,}  ({alive/total:.1%})")
    print(f"  unreachable  {dead:>7,}  ({dead/total:.1%})")
    print(f"  took {elapsed/60:.1f} min this session")

    if dead:
        from collections import Counter
        reasons = Counter()
        for r in results:
            if not r["reachable"] and r["error"]:
                e = r["error"].lower()
                if "not found" in e:
                    reasons["not found (deleted/renamed)"] += 1
                elif "could not read username" in e or "authentication" in e:
                    # The host is asking us to log in, which means the repo is
                    # private or gone. We never authenticate - see check_one.
                    reasons["private or gone (auth wanted)"] += 1
                elif "timeout" in e:
                    reasons["timeout"] += 1
                else:
                    reasons["other"] += 1
        print("\n  why unreachable:")
        for reason, count in reasons.most_common():
            print(f"    {reason:<22} {count:>7,}")


if __name__ == "__main__":
    main()
