# LEARNING.md

Concepts that came up while building this project, logged as we hit them, for
independent study. Not homework — a map of what's around you. Cross off what
you've actually read about.

Format: **concept** — why it matters here — where to start.

---

## Session 1 — 2026-09-05 (domain scoping)

### Statistics / methods

- [ ] **Survival analysis (time-to-event analysis)** — the entire analysis
  layer of this project. Instead of "what fraction are vulnerable," it asks
  "how long until the event happens," and it handles subjects you stop
  observing before the event. Start: the Kaplan–Meier estimator, then the
  Cox proportional hazards model. `lifelines` is the friendly Python library.

- [ ] **Right-censoring** — a server that vanishes, or is still broken when
  the study ends, has a *lower bound* on its fix time, not a missing value.
  Throwing those rows away is the classic beginner error and it biases every
  number toward "fixes are fast." Understand why before you write any
  analysis code.

- [ ] **Competing risks** — "gets fixed," "gets deleted," and "gets abandoned"
  are three different exits from the study, and treating deletion as just
  censoring is a modelling choice with consequences. Read this after
  Kaplan–Meier makes sense.

- [ ] **Precision and recall, and why they trade off** — MCPZoo (arXiv
  2607.11086) found published MCP scanners average ~46% precision and ~24%
  recall, and agree with each other only ~16% of the time. Our detector's
  error rate directly becomes noise in our fix-time estimates. Understand the
  two numbers before choosing detectors.

- [ ] **Left truncation** — servers that were already broken and fixed before
  we started observing are invisible to us. Know the name of this bias even
  if we don't correct for it.

### Data / engineering

- [ ] **Cursor pagination vs. offset pagination** — the MCP registry API hands
  back a `nextCursor`. Why do APIs do this instead of `?page=2`? (Hint: what
  happens to page 2 when someone inserts a row into page 1?)

- [ ] **Idempotency** — if a scheduled run fires twice, or you re-run it after
  a crash, the database must not end up with double rows. This is a design
  property you build in, not a bug you fix later.

- [ ] **Content hashing for change detection** — how you know a tool
  description changed without storing every version forever. Look at SHA-256
  and the idea of a "fingerprint."

- [ ] **Append-only / immutable data** — why measurement studies never
  `UPDATE`. Related: event sourcing.

- [ ] **SQL basics, then joins** — unavoidable from here on. Start with
  `SELECT / WHERE / GROUP BY`, then `JOIN`, then indexes. SQLite is a
  zero-setup place to practice.

- [ ] **cron syntax** — the five-field schedule string. You'll write one in
  session 2 or 3. crontab.guru is the standard playground.

- [ ] **GitHub Actions** — what a "runner" is, what a workflow file is, and
  what "free for public repos" actually means. Also: why scheduled workflows
  are best-effort and can fire late or be skipped under load.

### Domain

- [ ] **Model Context Protocol** — read the spec's tools and transports
  sections, not a blog summary. You need to know what a tool description
  *is* structurally before you can detect a bad one.

- [ ] **Prompt injection, and why it isn't a bug you can patch** — the
  security substrate under most MCP-specific issues.

- [ ] **Tool poisoning and "rug pulls"** — malicious instructions hidden in
  tool descriptions; a server that behaves until it's been approved, then
  changes its description. Note that a rug pull is *only* detectable with a
  time series. That's your project.

- [ ] **Responsible disclosure norms** — coordinated disclosure, embargo
  periods, CVE assignment. Read this before you contact any maintainer,
  because RQ2 depends on it.

- [ ] **Research ethics for measurement studies** — the Menlo Report is the
  standard reference for network measurement research. Relevant the moment
  we consider touching a live endpoint.

---

## Session 5 — 2026-09-08 (environment, storage format)

### Data / engineering

- [ ] **How git actually stores things — delta compression** — git does not
  store files, it stores compressed objects, and it finds *similar* objects and
  stores one as a diff against another. This is why 29 MB of JSONL only grew
  `.git` by 4.3 MB, and why gzipping the snapshots first made the repository
  grow twenty times faster per run. General lesson worth internalising:
  compressing data before handing it to a system that already compresses can
  make things worse, because you have destroyed the redundancy it was relying
  on. Start: "git internals — packfiles" in the Pro Git book.

- [ ] **Wheels, source distributions, and platform tags** — a wheel is a
  prebuilt package compiled for one specific OS + CPU + Python version, named
  like `charset_normalizer-3.5.1-cp312-cp312-win_arm64.whl`. When no wheel
  matches your platform, pip silently falls back to compiling from source and
  you need a C compiler. This is the cause of most "why won't this install"
  pain on Windows, and it is why `pandas==2.2.3` cannot install on this laptop.
  Learn to read a wheel filename; it tells you exactly what it will and will
  not run on.

- [ ] **Verifying a lossless transformation** — before deleting an original,
  prove the copy is good: same byte count, same line count, same SHA-256 of the
  decompressed content. Related: why `gzip` needs its stream *closed* before
  the file is valid (the CRC trailer is written on close), and why relying on
  garbage collection to flush a file is a bug that fails intermittently rather
  than never.

- [ ] **Content-addressed storage and hashing** — SHA-256 as an identity check
  for data. Already listed under session 1 as "content hashing for change
  detection"; this session was the first time we actually used it for
  something. Same idea, different application.
