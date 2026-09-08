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
