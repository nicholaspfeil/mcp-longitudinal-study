# A longitudinal measurement study of MCP server security

Everything published about security in the Model Context Protocol ecosystem so
far is a snapshot: *"we scanned N servers and M were vulnerable."* This
repository is an attempt at the missing dimension — **time**.

An automated observer runs on a schedule and records, with a timestamp, what
it sees in the public MCP server ecosystem. It has been running since
September 2026. The resulting dataset cannot be reconstructed after the fact
by anyone who did not also start observing a year earlier.

## Research questions

1. When a public MCP server has a security problem, does it get fixed — and
   how long does that take?
2. Does public disclosure accelerate remediation?
3. Is the ecosystem getting healthier over time, or accumulating unfixed
   problems as it grows?

## Method, briefly

- **Observe** the official MCP Registry and the public source repositories it
  points at, on a fixed schedule.
- **Detect** a small, deliberately conservative set of security weakness
  patterns using deterministic, version-pinned tooling. High precision is
  prioritised over coverage — see below.
- **Record** every observation append-only, with the actual observation
  timestamp. History is never overwritten.
- **Analyse** with survival analysis (time-to-remediation), with
  right-censoring for servers that vanish rather than get fixed.

## Two things that are load-bearing

**The dataset is the asset, not the code.** The scanner could be rewritten in
a weekend. A year of observations could not. Any change that threatens the
comparability of the time series is a bigger decision than it looks.

**Detector stability beats detector coverage.** A published evaluation of
eight MCP security scanners found mean precision around 45%, recall around
24%, and pairwise agreement between scanners of roughly 16%. In a snapshot
study that is a limitation; here it is fatal, because a detector that changes
its mind about unchanged code manufactures fake "vulnerability appeared" and
"vulnerability fixed" events that flow straight into the survival curves.
Detectors are therefore pinned, versioned in the schema, and chosen for
determinism.

## Scope

Registry metadata and published source code only. **No probing of
third-party live endpoints.** See [`docs/ethics.md`](docs/ethics.md) — that
document is a standing rule, not a preference.

## Repository layout

```
docs/
  domain-notes.md   background: registries, prior work, what's fetchable
  ethics.md         scope rules — read before adding any data source
  sessions.md       running log of decisions
CLAUDE.md           working agreement for AI collaboration on this repo
LEARNING.md         concepts to study independently, logged as they arise
```

## Status

Early. Currently characterising the sampling frame before committing to a
storage schema.
