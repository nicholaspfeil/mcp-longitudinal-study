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
