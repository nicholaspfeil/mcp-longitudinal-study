# Session log

One entry per working session. What we decided, what changed, what's open.
Future sessions read this first.

---

## Session 1 — 2026-09-05 — domain scoping

Deliberately no code. Mapped the problem space.

Established that "MCP server" means three different things — registry
metadata, published package/source, and running endpoint — and that prior
papers often conflate them. Verified the official MCP Registry API live: it
supports `updated_since` with cursor pagination, and every entry carries
`publishedAt`, `updatedAt`, `status` (`active`/`deprecated`/`deleted`) and
`statusChangedAt`. The status transitions are a free, timestamped "server
vanished" signal for censoring. `repository` is an optional field, which is a
sampling-frame limitation to be honest about.

Split security problems into conventional vulnerabilities (~7.2% prevalence in
prior work, credential exposure most common at ~3.6%, detectable with
deterministic tooling) and MCP-specific ones (tool poisoning ~5.5%, rug pulls,
exposed endpoints, token passthrough).

Key finding from the literature: published MCP scanners have ~45% mean
precision, ~24% recall, and ~16% pairwise agreement (MCPZoo, arXiv 2607.11086).
Concluded that detector *stability* matters more than coverage here, and that
LLM classifiers are dangerous as the outcome variable because the provider
silently changes the model underneath.

Novelty claim checked against five recent papers — all snapshots, none
longitudinal. Two are from 2026, so the literature needs rechecking every few
months.

Flagged that RQ2 (does disclosure accelerate remediation) is a causal claim
that is hard to obtain observationally, because disclosed vulnerabilities are
not a random sample. Unresolved.

Open: unit of observation; cohort design; RQ2 approach; storage format.

---

## Session 2 — 2026-09-07 — concept review

No decisions. Re-explained the study from scratch: what longitudinal means,
survival analysis, right-censoring, competing risks, why measurement
instability is the main threat, and why missed scheduled runs are data rather
than errors.

Corrected an important misconception: this study does **not** observe
breaches. It observes whether a weakness pattern is present in published code
and how long it persists. The clock runs from *first observation of the
finding* to *first observation of its absence* — both endpoints are properties
of our observation, not of the world, so all results are lower bounds.

---

## Session 3 — 2026-09-08 — scope locked, first code

**Decision: Tier 1 (registry metadata) + Tier 2 (published source) only. No
probing of third-party live endpoints.** Written up in `docs/ethics.md` as a
standing rule. Sandboxed dynamic analysis ("Tier 2.5" — running open-source
servers ourselves in a container) noted as a possible later extension that
would require its own written justification first.

Reasoning recorded in `docs/ethics.md`. Short version: consent, legal
exposure, measurement noise, and operational sustainability — plus the
observation that live probing buys a common signal ("built a scanner") at the
cost of the rare one (a year of clean data).

Started the first build step: characterising the sampling frame before
designing the schema, because the schema is the expensive decision and it
should be made against real numbers rather than assumptions.

Open: repository location; unit of observation; cohort design; RQ2 approach;
storage format.

---

## Session 4 — 2026-09-08/09 — first census, and the storage decision

`fetch_all_servers()` written and working. Nicholas wrote it; first version
unwrapped `entry["server"]` and discarded `_meta`, which would have thrown away
every timestamp in a longitudinal study. Corrected to store entries whole.
Standing rule from this: **store raw, reshape at analysis time.**

**First census: 28,625 entries, 28,625 unique names, 0 duplicates.** So
`version=latest` collapses versions correctly and 28,625 is the sampling frame.
29 MB uncompressed.

Characterisation of that snapshot:

| | count | share |
|---|---|---|
| with `repository` | 21,796 | 76.1% |
| — GitHub | 21,762 | 99.8% of those |
| — GitLab | 34 | 0.2% |
| with `packages` | 13,177 | 46.0% |
| with `remotes` | 16,512 | 57.7% |
| `active` | 28,303 | 98.9% |
| `deprecated` | 322 | 1.1% |
| `deleted` | 0 | — |

`publishedAt` spans 2025-09-09 to 2026-09-08 — the registry's entire life, so
there is almost no pre-study history to miss.

**The finding that changed the design: zero `deleted` entries.** Either nothing
has been deleted in a year, or deletion removes the entry from the API rather
than flagging it. We cannot tell from one snapshot, and the worse case has to be
assumed.

That kills the planned `updated_since` delta-fetch optimisation. A delta run
returns records that *changed*; a removed server does not appear in it at all,
because removal is an absence rather than a change. Deltas would have silently
destroyed the ability to detect disappearance, which is the censoring signal the
survival analysis depends on. **We therefore need the complete list of what
exists on every run.**

**Decision: Option A — full snapshot every run, gzipped, weekly.**

Reasoning: simplicity is the best predictor that an unattended job survives
twelve months; A's data can always be reduced to a manifest-plus-changes scheme
later, but a manifest scheme's data can never be expanded back into full
snapshots; and repo growth is not yet a measured problem. Revisit after four or
five snapshots by watching the size of `.git`.

Weekly cadence means every reported fix-time carries ±7 days of granularity,
which must be stated rather than reporting means to two decimals.

Side effect worth noting: choosing A defers the schema decision. Raw snapshots
can be reshaped into any analysis schema later, so the expensive, hard-to-reverse
choice does not have to be made now.

Open: RQ2 approach; detector set; scheduled workflow and its monitoring.

---

## Session 5 — 2026-09-08 — environment, and the gzip decision reversed

Housekeeping first. Repository created and pushed to
`github.com/nicholaspfeil/mcp-longitudinal-study`; "repository location" is
closed. Python 3.12.10 installed (this machine is **Windows on ARM64**, which
matters below), `.venv` created, `requests==2.32.3` installed.

**`pandas==2.2.3` will not install here.** No pandas 2.x release ships a
`win_arm64` wheel — checked against PyPI directly, not assumed. pip falls back
to building from source, which needs an MSVC toolchain. The first version with
an ARM64 Windows wheel is 3.0.0, a major release with breaking changes. Left
unresolved deliberately: nothing built so far needs pandas, and `characterize.py`
does its job with `json` + `collections.Counter`. Decide when a dataframe is
actually required. Note the asymmetry — the Linux x64 CI runner installs 2.2.3
fine, so `requirements.txt` currently works in CI and not on the dev machine.

**Reversed session 4's decision to gzip snapshots.** Full snapshots every run
stands — the reasoning about deletion being an absence rather than a flag is
untouched. Only the compression is reversed.

Measured it on the two real snapshots rather than arguing from file size:

|  | marginal cost of the 2nd snapshot |
|---|---|
| plain `.jsonl` | ~0.2 MB |
| gzipped `.jsonl.gz` | ~4.1 MB |

Git does not store files, it stores objects, and it *delta-compresses* similar
ones before zlib-compressing the result. Consecutive registry dumps are nearly
identical text, so git stores the second as a diff against the first. Gzip
destroys this: a `.gz` is high-entropy binary, so two gzipped files of nearly
identical input share no byte sequences, git cannot delta them, and every run
costs full size forever.

The argument that settles it regardless of churn rate: **plain JSONL's worst
case equals gzip's every case.** If a week's churn changed every line, git
would store ~4.3 MB — the same as a 4.35 MB `.gz`. Any churn below total, and
the delta wins. Gzip has no scenario where it comes out ahead.

At weekly cadence that is roughly 226 MB/year gzipped against 15–60 MB/year
plain. Session 4 said to revisit after four or five snapshots by watching
`.git`; this is that revisit, done early with a controlled comparison instead.

Consequences: both `.gz` files deleted, run 2 written as plain `.jsonl` and
verified lossless by SHA-256 round-trip, `characterize.py` reverted to reading
plain files. The 29 MB blob from `8c38199` stays in history permanently; not
worth rewriting for one file.

Also fixed: the `USER_AGENT` stale `TODO` and missing `https://` scheme, and a
docstring in `fetch_all_servers` that claimed entries were unwrapped to
`server` with `_meta` discarded, when the code correctly stores them whole.

**Cursor guard added** — the check the original stub asked for. Tracks every
cursor used in a `set` and raises if one comes back a second time.

Three details that are load-bearing:

- `next_cursor` is a separate variable from `cursor`. The old line
  `cursor = data.get(...)` read the new value and destroyed the sent one in
  the same statement; you cannot compare two values while holding one.
- The `if not next_cursor: break` must come **before** the repeat check.
  `cursor=None` means "send no cursor," which the registry reads as *start
  from the beginning* — so letting `None` past the guard would silently
  restart the walk and duplicate all 28k entries. This ordering is also why
  `None` never enters `seen_cursors`, so there is no collision with the
  initial value.
- A `set` rather than a single previous value, so `A → B → A → B` is caught
  as well as `A → A`. Costs ~287 strings.

Raises rather than breaks: a truncated snapshot on disk is indistinguishable
from a real one later and would read as a mass-deletion event in the survival
curves. Missing data is honest; corrupt data wearing a disguise is not.

Verified with a stubbed `fetch_page` — stuck cursor raises after 2 calls
(previously 1000 calls over ~17 minutes ending in a misleading `MAX_PAGES`
error), alternating cycle raises after 3, and normal/single-page pagination
does not false-positive.

**Caught during that run: `main()` was still writing `.jsonl.gz`.** The
previous commit reverted `characterize.py` but missed the writer, so the
storage decision was only half-applied and the third snapshot came out
compressed. Fixed, `gzip` import dropped, snapshot converted in place and
verified rather than re-fetching 287 pages for data already held.

Third census: 28,635 entries. Registry churn observed today: 28,625 → 28,632
→ 28,635 across roughly 2.5 hours.

Open: RQ2 approach; detector set; scheduled workflow and its monitoring; the
pandas pin.

---

## Session 6 — 2026-09-09/10 — the clock starts

`.github/workflows/snapshot.yml` written and **verified running**. Weekly,
Mondays 07:17 UTC, odd minute chosen because scheduled runs are best-effort
and top-of-the-hour schedules are the ones that get delayed or skipped. Manual
`workflow_dispatch` run went green and produced commit `9707a0a`, authored by
`github-actions[bot]`, containing a snapshot nobody made by hand.

**The study is now self-collecting.** From here, gaps in the series are
permanent.

Ordering rationale, worth keeping because it is not obvious: detectors were
deliberately deferred behind the scheduler. Registry metadata cannot be
reconstructed — the API serves current state only, so a tool description
edited tomorrow is gone. Source code can be reconstructed, because the
repositories are in git and a detector written in month four can be run
against any past commit. Collect what expires; compute what doesn't, later.

**Growth is much faster than estimated, and the estimate was bad.**

| | entries |
|---|---|
| 2026-09-08 19:17 (manual) | 28,635 |
| 2026-09-10 01:01 (robot) | 30,282 |

+1,647 in ~30 hours, about 55/hour. An earlier figure of ~4/hour in these
notes was extrapolated from a 2.5-hour window containing 10 new entries — far
too small a sample, and stated far too confidently. Treat it as retracted.

Field proportions moved at the same time: `repository` 76.1% → 77.1%,
`packages` 46.0% → 43.9%, `remotes` 57.7% → 59.7%. Proportions over ~29,000
records do not drift 1–2 points in 30 hours by themselves, so the new entries
have a different shape from the existing population — the signature of a bulk
import rather than organic growth.

Probably a burst; 5.8% per 30 hours would compound absurdly if sustained.
Watch it over the next few snapshots, because it bears on whether the sampling
frame is stable enough to be treated as a cohort at all.

Storage holding: `.git` is 5.2 MB against 114 MB of raw snapshots. The fourth
snapshot cost ~0.4 MB despite 1,647 new rows. Gzipped, the four would be
~17 MB.

Open: monitoring (deferred deliberately, do not let it slide); RQ2 approach;
detector set; the pandas pin; whether registry growth is a burst or a trend.

---

## Session 7 — 2026-09-10 — what the registry does not contain

Enumerated every server-level key across all 30,282 records rather than
inspecting one entry:

| key | coverage |
|---|---|
| `$schema`, `name`, `description`, `version` | 100% |
| `repository` | 77.8% |
| `title` | 60.1% |
| `remotes` | 59.7% |
| `websiteUrl` | 48.1% |
| `packages` | 43.9% |
| `icons` | 6.9% |
| `_meta` (server-level) | 4.2% |

**There is no tool-level data anywhere in the registry.** No `tools` key, no
per-tool descriptions, no key containing the substring "tool".

This constrains the research design and should not have to be rediscovered.
`domain-notes.md` names rug pulls — a tool description benign at approval time
and changed later — as the phenomenon *only* detectable with a time series,
and therefore as the novelty claim. **Tier 1 data cannot detect a tool-level
rug pull**, because the text sent to the model is not in what we collect.

What Tier 1 *can* measure longitudinally, and this is still substantial:

- `description` at the server level, **100% coverage**, ephemeral, and
  currently being captured weekly. A publisher rewriting their description is
  a coarse rug-pull-adjacent signal available for every server.
- `version` changes — the publisher shipped something.
- `status` transitions with `statusChangedAt` — the censoring signal.
- `name` as stable identity across snapshots.

Tool-level analysis requires Tier 2: tools are defined in source code, so they
must be parsed out of the cloned repository. This does not change the build
order — source code is in git and can be analysed retroactively, whereas
registry metadata cannot.

**Permanent hole in the sampling frame:** the ~22% of servers with no
`repository` (about 6,700) can never be analysed at tool level by any route
this project permits. Live probing would reach them; `ethics.md` rules it out.
State this in any write-up rather than burying it.

**Naming collision worth remembering:** `_meta` appears at the server level in
4.2% of records and is publisher-supplied. The `_meta` this study depends on
is one level up, on `entry`, and is present 100% of the time. Writing
`server.get("_meta")` returns `None` for 96% of records and fails silently.

Open: monitoring; RQ2 approach; detector set; the pandas pin; whether registry
growth is a burst or a trend.

---

## Session 8 - 2026-09-10 - the run that proved the gap

First scheduled-workflow failure, and it found a real design hole rather than
a bug in the workflow.

```
page 52  OK   com.openmedici/public:0.1.0
page 53  500 Server Error: Internal Server Error
```

One transient 500 from the registry on page 53 of ~303. `fetch_page` called
`raise_for_status()` with no retry, so the exception propagated, 52 pages of
good data already in memory were discarded, nothing was written, and the run
exited 1.

**Why this was urgent rather than annoying.** A walk is ~300 requests; weekly
for a year is ~15,700 requests against a free public API with no SLA. At that
volume a transient failure is not a risk being accepted, it is an event being
scheduled. Each one costs a week of the series permanently, because the
registry only serves current state and Monday does not come back.

**Fix: `urllib3.Retry` mounted on a `requests.Session`.** Chosen over a
hand-rolled loop because it also catches connection-level failures that
`except HTTPError` would miss, and because it implements exponential backoff,
which is the polite behaviour `ethics.md` asks for when a server is
struggling. The Session also reuses connections across the ~300 requests
instead of reopening each time.

Retry policy, and the reasoning behind which errors qualify:

| status | retried | why |
|---|---|---|
| 500, 502, 503, 504 | yes | the server broke; almost always transient |
| 429 | yes, honouring `Retry-After` | we are going too fast; slow down |
| connection errors, timeouts | yes | network blip |
| 4xx | **no** | we sent something wrong; retrying sends the same wrong thing and turns our own bug into a silent hang |

Verified against a local server that returns 500s on demand: three 500s then
success is absorbed in ~6s and returns data; a permanently broken server
raises `RetryError` after 6 attempts rather than hanging.

`urllib3==2.7.0` added to `requirements.txt` - it is now imported directly
rather than arriving as a hidden dependency of `requests`.

Also bumped `actions/checkout` to v5 and `actions/setup-python` to v6 ahead of
the Node 20 deprecation. Warnings now, hard failures later, and this job is
meant to run untouched for twelve months.

**Known remaining gap:** a run is still all-or-nothing. Retries cover a blip;
a sustained registry outage still costs the week. Partial-progress resumption
is possible but not built, and is probably not worth it until an outage
actually costs something.

Open: monitoring (secret still not set); RQ2 approach; detector set; the
pandas pin; whether registry growth is a burst or a trend.


---

## Session 9 - 2026-09-10 - the robot is complete

Workflow green, healthchecks.io green. Commit `f794e22` was produced by
`github-actions[bot]` with no human involved beyond pressing the button.

**The observation infrastructure is finished.** From here the study collects
itself weekly, and if it stops, something outside GitHub will say so.

What the two alarms cover, and why both are needed:

| failure | detected by | latency |
|---|---|---|
| run happens, run fails | GitHub failure email (verified working) | immediate |
| run never happens at all | healthchecks.io, absence of a check-in | up to period + grace (~8 days) |

GitHub cannot detect the second case: no run means no failure means no email.
The check-in service is deliberately outside GitHub because a monitor inside
the system it monitors cannot see that system being down - and the specific
worry, the 60-day inactivity rule disabling the schedule, is exactly that
case. Whether bot commits reset that clock is still unverified; the alarm now
means we find out within a week rather than at analysis time.

The check-in step is last in the job and guarded by `if: success()`, so a run
that fetches but fails to commit does not report health.

**Growth is bursty, and cannot yet be estimated.**

| snapshot | entries | delta | interval | implied rate |
|---|---|---|---|---|
| 09-08 17:46 | 28,625 | - | - | - |
| 09-08 18:41 | 28,632 | +7 | 55 min | ~7/hr |
| 09-08 19:17 | 28,635 | +3 | 36 min | ~5/hr |
| 09-10 01:01 | 30,282 | +1,647 | 29.7 h | ~55/hr |
| 09-10 01:45 | 30,299 | +17 | 44 min | ~23/hr |

Rates of 5, 7, 23 and 55 per hour from the same series. That is not noise
around a mean, it is bursty arrival, consistent with the bulk-import reading
of the +1,647 window. No rate should be quoted from this: five observations,
four of them clustered in two short windows, wildly uneven spacing. The weekly
runs will produce the first evenly-spaced series, and even spacing is the
point of the cadence rather than the frequency.

**Next: the diffing code.** Compare snapshot N to N-1 and emit an event
stream - appeared, description changed, version changed, status changed,
disappeared. This is the first code that uses the time dimension at all, it is
core research logic so Nicholas writes it, and there are already five
snapshots with real events in them to test against. It will also stress-test
the assumption that `name` is a stable identity across snapshots, which
everything downstream depends on.

Open: RQ2 approach; detector set; the pandas pin; whether the 60-day
inactivity rule is actually reset by bot commits (watch for it around
2026-11-09).


---

## Session 10 - 2026-09-10 - first diffs, and three findings that change the design

`diff_snapshots()` written and working. Compares two snapshots by name and
emits appeared / disappeared / version_changed / description_changed /
status_changed. Prints a summary rather than writing events, deliberately -
the event schema is the same kind of expensive decision as the storage schema
and should be made against real numbers.

Sanity check on the 44-minute pair: 30,282 -> 30,299, appeared 17,
disappeared 0, net +17. Consistent.

The three separate `if` statements rather than `if/elif` paid off immediately:
`io.gjalla/mcp` changed version AND description in the same window, so it
belongs in two lists. An `elif` would have silently dropped one on the first
real run.

### Finding 1: deletion is invisible in `status`

Six servers vanished between 09-08 19:10 and 09-10 00:55. **All six were
`active` when last seen.** No snapshot has ever contained `status: deleted` -
checked across all five.

Servers are not marked deleted. They are removed from the API silently.

This confirms the worst-case assumption from session 4, which is what killed
the `updated_since` delta-fetch and forced full snapshots. A delta run returns
records that changed; a removed record does not appear at all, because absence
is not a change. **The storage architecture argued for on theory is now
empirically vindicated.**

Consequence: the censoring signal must come from set difference between
consecutive snapshots, not from the `status` field. And there is no
`deletedAt`, so death times are **interval-censored** with interval width
equal to the polling gap - plus or minus seven days at weekly cadence. State
this; do not smooth it.

### Finding 2: status transitions are reversible

`('io.gjalla/mcp-server', 'deprecated', 'active')` - a server went backwards.
Corroborated by the deprecated counts: 322 -> 333 -> **332**.

Deprecation is a phase, not an exit. A server can deprecate and revive,
possibly repeatedly. Treating the first `deprecated` as "left the study" would
bias every fix-time estimate in a direction undetectable after the fact. The
survival model needs reversible states or recurrent events, not a simple
absorbing-state progression.

### Finding 3: one publisher is 83% of growth

Of the 1,653 entries that appeared in the 30-hour window:

| publisher | new entries |
|---|---|
| `io.github.sadri-dridi` | **1,376 (83.2%)** |
| `io.github.BuilderIO` | 13 |
| `com.bestremotetools` | 12 |

One publisher mass-producing trivial single-purpose servers - `tz-asia-muscat`,
`lang-mr`, `unicode-len`. Not organic growth.

**Most consequential finding for research design.** The sampling frame is not
a sample of the MCP ecosystem, it is substantially a sample of whoever is
bulk-publishing that week. Any aggregate claim of the form "X% of MCP servers
have credential exposure" would be dominated by one person's code style.

`domain-notes.md` anticipated this - "a smaller, well-chosen, stable cohort
beats a large sloppy one." There is now hard evidence for it. Cohort design
moves from a deferred question to the next real decision: probably per-
publisher analysis, or a cap, or reporting weighted and unweighted side by
side.

Open: cohort design (now urgent); how to model reversible status; RQ2
approach; detector set; the pandas pin; the 60-day inactivity question
(watch 2026-11-09).

