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

## After that: the alarm

Deferred deliberately, but it is the next real piece of work.

The problem: if the workflow *breaks*, GitHub emails you. If it silently never
runs, nothing happens at all — and a week where nothing ran looks exactly like
a week where nothing changed. Both are silence.

So we need something that notices **absence** rather than failure: a service
that expects a check-in every week and complains when one does not arrive.
This is called a dead man's switch. Free tiers exist.

`CLAUDE.md` calls this a requirement, not a nice-to-have. Do not let it slide
past a couple of weeks.

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
