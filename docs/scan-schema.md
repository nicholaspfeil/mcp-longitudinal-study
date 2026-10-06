# Scan output schema

**Status: decided 2026-10-06 (session 15) by Nicholas. Changing it changes the
data - treat like `RULES_VERSION`.**

The scanner writes two append-only JSON Lines files per run. They are linked by
`(repository_url, observed_at)`.

## `data/scans/scans-<timestamp>.jsonl` - one line per repository attempted

Every repository the scanner *tries* gets exactly one line, whether it was
clean, had findings, or failed. A missing line means "not attempted", never
"clean".

| field | meaning |
|---|---|
| `repository_url` | the repo scanned. Scans are keyed by URL, not server: 16% of live panel servers share a repo |
| `observed_at` | when this repo was scanned (UTC, ISO 8601) |
| `commit_sha` | the commit **actually cloned and read**, from the checkout itself - not the SHA the liveness check recorded, which may be older |
| `rules_version` | `detect.RULES_VERSION` at scan time |
| `status` | `scanned`, `not_found`, `unreachable`, `timeout` or `scan_error` |
| `n_findings` | number of findings; meaningful only when `status == "scanned"` |
| `error` | error message for non-`scanned` statuses, else `null` |

Status meanings:

- `scanned` - the scan completed. "Clean" is `scanned` with `n_findings == 0`;
  "found keys" is a subset of `scanned`, not its own status.
- `not_found` - git reported the repository missing or private. Evidence of
  death (feeds the death rule).
- `unreachable` - network failure. Evidence of nothing; never counts as death.
- `timeout` - exceeded the clone/scan time limit. Kept separate because it is
  *not random*: large repositories hit it repeatedly.
- `scan_error` - our own code failed. A bug to fix, not a property of the repo.

## `data/scans/findings-<timestamp>.jsonl` - one line per credential found

| field | meaning |
|---|---|
| `repository_url`, `observed_at` | link to exactly one scan line |
| `file` | path relative to repo root |
| `line` | 1-based line number (for humans; not part of identity) |
| `rule` | key from `detect.RULES` |
| `match_sha256` | fingerprint of the match; the credential itself is never stored |

Facts about the scan (commit, rules version, status) live only on the scan
line, never copied into findings, so the two files cannot disagree.

## Not recorded, on purpose

Repositories whose HEAD has not changed since their last successful scan are
not re-scanned and get no new line: the code is byte-identical, and the
liveness file records that the commit did not change.
