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
