# NEXT STEP - read this first when you sit down

*Last updated 2026-11-10 (session 16). Unfamiliar word? Check `docs/glossary.md`.*

---

## Where things are

All four parts of the pipeline exist:

| | what | when (UTC) |
|---|---|---|
| Tier 1 | registry snapshot (`snapshot.yml`) | Mondays 07:17 |
| Tier 2 | repo liveness check (`repo-check.yml`) | Mondays 08:23 |
| Tier 3 | credential scan (`scan.yml`) | Tuesdays 06:41 |
| alarm | healthchecks.io, one check per job | - |

## Do next

1. **Add the scan alarm.** healthchecks.io -> new check `mcp-credential-scan`,
   period 1 week, grace 1 day. GitHub -> Settings -> Secrets and variables ->
   Actions -> new secret `HEALTHCHECK_URL_SCAN` = its ping URL.
2. **Smoke-test the scan.** Actions -> *Weekly credential scan* -> Run
   workflow, `limit` = 5, **untick commit**. Expect 16 green shards and a
   collect job that reports about 80 scan lines.
3. **After Monday 11-16:** check that `data/raw/` gained a *folder*
   `registry-20261116.../` with `part-000.jsonl` and `part-001.jsonl`. That is
   the first snapshot in the new layout.
4. **After Tuesday 11-17:** the first full scan (~16,500 repos). Look at the
   commit: count of `status` values, and how many findings.

## When the alarm emails you

Re-run the failed workflow **the same day** (Actions -> the run -> Re-run
jobs). Read the failing step's log first. A registry snapshot can't be taken
retroactively, so a run that isn't repeated is a permanent gap. That's how
the 10-12 snapshot was lost.

## Still undecided (research decisions, yours)

- death rule: how many unreachable weeks in a row count as dead (N)
- what counts as "fixed": removed from HEAD, or revoked?
- what to do about live keys we find (ethics + RQ2)
