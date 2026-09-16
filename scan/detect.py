"""Detect exposed credentials in a repository's source.

The outcome variable of this study. Everything else records whether things
exist; this records whether they are broken.

Design constraints, all from docs/ -- read these before changing anything here:

  Precision over recall. Published MCP scanners average ~46% precision and
  ~24% recall (MCPZoo, arXiv 2607.11086). In a snapshot paper that is a
  footnote. Here a detector that changes its mind about unchanged code
  manufactures fake "vulnerability appeared" and "vulnerability fixed" events
  that flow straight into the survival curves. Recall we can sacrifice.
  Precision and stability we cannot.

  Determinism. This detector, on this input, must always return this answer --
  forever, not just today. That is why dependency auditing (pip-audit, npm
  audit) is deliberately absent: those compare against a CVE database that
  changes, so untouched code would flip from clean to vulnerable the day a CVE
  is published, recording a "vulnerability appeared" event for code nobody
  edited.

  Never store a credential. This repository is public. Findings record a hash
  of the match, never the match itself.

RULES_VERSION and the re-scan policy (decided 2026-09-13):

  Any change to RULES or ALLOWLIST bumps RULES_VERSION, and the whole history
  is then re-scanned so the series stays comparable. The alternative -- letting
  detector versions be a hard boundary -- would split the study at every rule
  change, and a continuous twelve-month series is the entire product.

  The cost of that choice: we can never lose the ability to re-run. Raw
  snapshots, the panel file, and the ability to fetch any past commit must all
  be preserved indefinitely.

Usage:
    python -m scan.detect PATH_TO_REPO
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

# Bump this on ANY change to RULES or ALLOWLIST below, then re-scan history.
RULES_VERSION = 1

# Chosen because each format is unambiguous -- a string matching one of these
# is a credential, not a coincidence.
#
# Deliberately NOT included: `password\s*=`, `api_key\s*=`, and high-entropy
# string detection. They would raise recall and destroy precision, and their
# false positives move when unrelated lines are edited, which manufactures fake
# remediation events.
RULES: dict[str, str] = {
    "aws_access_key_id":  r"AKIA[0-9A-Z]{16}",
    "github_token":       r"ghp_[A-Za-z0-9]{36}",
    "google_api_key":     r"AIza[0-9A-Za-z_-]{35}",
    "stripe_live_key":    r"sk_live_[0-9a-zA-Z]{24}",
    "slack_token":        r"xox[baprs]-[0-9A-Za-z-]{10,}",
    "private_key_block":  r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
}

COMPILED = {name: re.compile(pattern) for name, pattern in RULES.items()}

# Documentation placeholders that match the patterns above but are not real
# credentials. These are stable false positives -- they do not flicker, so they
# would not create fake events, but they would inflate prevalence with a
# constant. Add to this list as they are found; adding here bumps RULES_VERSION.
ALLOWLIST: set[str] = {
    "AKIAIOSFODNN7EXAMPLE",      # AWS's own documentation example
    "AKIAI44QH8DHBEXAMPLE",      # AWS docs, second example
}

# Vendored third-party code. Scanning it would measure npm's and PyPI's
# security and attribute it to this author -- and a finding would "appear" the
# day someone commits the output of `npm install`.
EXCLUDED_DIRS = {
    ".git", "node_modules", "vendor", "venv", ".venv", "env",
    "site-packages", "dist", "build", ".next", "target",
    "__pycache__", ".tox", ".mypy_cache", ".pytest_cache",
}

# Minified bundles and data blobs are slow to scan and are not hand-written
# source. 1 MB is far above any real source file.
MAX_FILE_BYTES = 1_000_000


def iter_source_files(root: Path):
    """Yield every scannable file under root.

    You do not need to modify this. It is the mechanical part: skipping
    vendored directories, oversized files, and anything that is not text.
    """
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        yield path


def read_text(path: Path) -> str | None:
    """Read a file as text, or return None if it is binary/unreadable.

    You do not need to modify this. A NUL byte in the first block is the
    standard cheap test for "this is not text".
    """
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in raw[:8192]:
        return None
    return raw.decode("utf-8", errors="replace")


def fingerprint(matched_text: str) -> str:
    """Hash a matched secret. Identity and redaction in one step.

    You do not need to modify this.

    This is what makes a finding trackable across weeks. Identity must NOT
    include the line number: if someone adds an import above a hardcoded key,
    the key moves from line 40 to line 47 without changing. Keyed on line, that
    reads as one finding fixed and a new one appearing -- two fake events.

    It must also not be the file alone, or two different AWS keys in one file
    would collapse into a single finding.

    And the hash is why the credential itself is never written down. This repo
    is public; committing live keys found in other people's code would be
    indefensible.
    """
    return hashlib.sha256(matched_text.encode("utf-8")).hexdigest()


def scan_text(text: str, relative_path: str) -> list[dict]:
    """Find every credential in one file's text.

    ---- YOUR JOB. ----

    Contract:
      - `text` is the whole file. `relative_path` is its path relative to the
        repository root, as a string, used only for reporting.
      - Returns a list of finding dicts, each with exactly these keys:

            "file"          relative_path
            "line"          1-based line number where the match starts
            "rule"          the key from RULES that matched
            "match_sha256"  fingerprint() of the matched text

      - Returns an empty list when there is nothing. Never None.

    The shape of the work:
      - Walk the file a line at a time. `enumerate(text.splitlines(), 1)` gives
        you (line_number, line) pairs with 1-based numbering.
      - For each line, try every compiled pattern in COMPILED. `.finditer()`
        returns every match in that line, not just the first -- a config file
        can easily hold two keys on one line.
      - Skip any match whose text is in ALLOWLIST.

    Things that are easy to get wrong:
      - A single line can match MORE THAN ONE rule, and a single rule can match
        more than once on a line. Do not stop at the first hit.
      - `line` is recorded for a human investigating later. It is deliberately
        NOT part of the finding's identity -- see fingerprint() above for why
        that distinction is load-bearing.
      - Use match.group(0) for the matched text: that is what gets hashed and
        what gets checked against ALLOWLIST.
      - Do not lowercase, strip, or normalise anything. These patterns are
        case-sensitive on purpose, and normalising is a research decision being
        made by accident.

    Roughly 12 lines.
    """
    findings: list[dict] = []

    for line_number, line in enumerate(text.splitlines(), 1):
        # Every rule against every line: one line can match more than one rule.
        for rule_name, pattern in COMPILED.items():
            # finditer, not search: one rule can match more than once per line.
            for match in pattern.finditer(line):
                matched_text = match.group(0)
                if matched_text in ALLOWLIST:
                    continue
                findings.append({
                    "file": relative_path,
                    "line": line_number,
                    "rule": rule_name,
                    "match_sha256": fingerprint(matched_text),
                })

    return findings


def scan_repo(root: Path) -> list[dict]:
    """Scan every source file in a repository. Mechanical; already written."""
    findings: list[dict] = []
    for path in iter_source_files(root):
        text = read_text(path)
        if text is None:
            continue
        relative = path.relative_to(root).as_posix()
        findings.extend(scan_text(text, relative))
    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", help="path to a checked-out repository")
    parser.add_argument("--json", action="store_true", help="emit JSON lines")
    args = parser.parse_args()

    root = Path(args.repo)
    if not root.is_dir():
        raise SystemExit(f"Not a directory: {root}")

    findings = scan_repo(root)

    if args.json:
        for f in findings:
            print(json.dumps({"rules_version": RULES_VERSION, **f}, ensure_ascii=False))
        return

    scanned = sum(1 for _ in iter_source_files(root))
    print(f"{root.name}: {scanned:,} files scanned, {len(findings)} finding(s)")
    for f in findings:
        print(f"  {f['rule']:<20} {f['file']}:{f['line']}  sha256={f['match_sha256'][:12]}")


if __name__ == "__main__":
    main()
