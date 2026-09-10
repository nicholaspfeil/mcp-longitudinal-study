# NEXT STEP — read this first when you sit down

*Last updated 2026-09-09. This file always describes the one thing to do next.
Unfamiliar word? Check `docs/glossary.md`.*

---

## Done so far

- Repo public at `github.com/nicholaspfeil/mcp-longitudinal-study`, venv working
- Scope locked to Tier 1 + Tier 2, written up in `docs/ethics.md`
- `fetch_all_servers()` walks the whole registry, with a repeated-cursor guard
- Snapshot described: 76.1% have a `repository` (99.8% of those GitHub),
  46.0% have `packages`, 57.7% have `remotes`, 98.9% `active` / 1.1%
  `deprecated` / **0 `deleted`**
- Storage decided: **full snapshot every run, uncompressed JSONL, weekly.**
  Gzip was tried and reversed — it defeats git's delta compression and makes
  the repo grow ~20x faster per run. See `docs/sessions.md` session 5.
- Three censuses collected: 28,625 → 28,632 → 28,635 (2026-09-08)
- `.github/workflows/snapshot.yml` written — the weekly robot

## Do next: prove the robot works

The workflow is committed but has never run. Until it runs successfully once,
you do not have a study, you have a script.

1. Go to the **Actions** tab on GitHub.
2. Pick **Weekly registry snapshot** in the left sidebar.
3. Click **Run workflow** → **Run workflow**.
4. Watch it. It takes about six minutes.

**What success looks like:** a green check, and a new commit in your repo
called "Weekly registry snapshot (...)" containing a new file in `data/raw/`
that you did not create.

**If it fails on the last step** with something about permissions, go to
Settings → Actions → General → Workflow permissions and select **Read and
write permissions**. A workflow cannot grant itself more access than the
repository settings allow.

## Do next: finish the alarm

The workflow step is already written and committed. It does nothing until you
create the account and add the secret — three steps, all on your side.

**1. Sign up at https://healthchecks.io** — free tier, no card.

**2. Create a check** named something like `mcp-registry-snapshot`.
   - **Period: 1 week** — how often you promise to check in
   - **Grace: 1 day** — how long it waits after a missed check-in before
     alerting. Grace exists because scheduled runs are best-effort; a job four
     hours late is fine, a job a day late is not.

   Copy the ping URL it gives you (`https://hc-ping.com/...`).

**3. Add it to GitHub:** repo → Settings → Secrets and variables → Actions →
   New repository secret. Name it exactly `HEALTHCHECK_URL`.

   It goes in a secret rather than the workflow file because this repo is
   public, and anyone who could read the URL could ping it themselves — the
   alarm would then report health while the collector was dead.

**Then trigger the workflow by hand again** (Actions → Run workflow) and
confirm healthchecks.io flips the check to green. Until you have seen it go
green once, the alarm is not real.

### Why this design

Called a dead man's switch, after the pedal a train driver holds down: if they
collapse and let go, the train brakes by itself. Safety comes from the
*absence* of a signal.

If the workflow breaks, GitHub emails you. If it silently never runs, nothing
happens at all — and a week where nothing ran looks exactly like a week where
nothing changed. Both are silence.

The service is deliberately **outside** GitHub. A monitor inside the system it
monitors cannot detect that system being down. The specific failure to worry
about is the 60-day inactivity rule disabling the schedule; an in-GitHub
checker would stop at the same moment and tell you nothing.

The check-in step is last in the job and guarded by `if: success()`, so a run
that fetches but fails to commit does not report health.

## Then: the detectors

Deliberately last, and this is not procrastination — it is the correct order.

Registry metadata cannot be reconstructed. The API shows current state only,
so a tool description edited next Tuesday is gone forever unless we snapshot
it first. Source code *can* be reconstructed: the repos are in git, so a
detector written in month four can still be run against any past commit and
produce a clean time series backwards.

Collect the thing that expires. Compute the thing that doesn't, later.

Open questions carried forward: RQ2 approach; the detector set; whether
`pandas` stays pinned at 2.2.3 (it cannot install on this ARM64 laptop —
no pandas 2.x ships a `win_arm64` wheel).
