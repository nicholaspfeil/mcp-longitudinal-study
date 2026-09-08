# Scope and ethics

**Status: standing rule. Decided 2026-09-08. Do not quietly widen this.**

This study observes software written by real people who did not volunteer to
be studied. The scope below is deliberately narrower than what is technically
possible.

## What this project does

**Tier 1 — registry metadata.** Read public registry APIs (the official MCP
Registry, and possibly other aggregators). Names, descriptions, versions, tool
descriptions, publish timestamps, status transitions.

*Justification:* these are public REST APIs whose stated purpose is
consumption by automated aggregators. The official registry's own docs
instruct aggregators to poll on a regular basis.

**Tier 2 — published source code.** For servers that link a public source
repository, clone it and run static analysis. Reading only; no execution.

*Justification:* the code was deliberately published under an open licence.
Static analysis of public repositories is standard practice in software
engineering research and is what the existing literature does.

## What this project does NOT do

**No probing of third-party live endpoints.** We do not send requests to
anyone's deployed MCP server to observe its behavior.

Reasons, in order of weight:

1. **Consent and impact.** A hosted endpoint is someone's running
   infrastructure. Requests consume their compute, appear in their logs, and
   may trigger their alerting. Nobody opted into that.
2. **Legal exposure.** Depending on what is sent and where the server is
   hosted, automated probing can engage computer-misuse statutes. This is a
   solo undergraduate project with no institutional review behind it.
3. **Measurement quality.** A server that is temporarily down is
   indistinguishable from one that has been deleted. Live probing injects
   exactly the kind of noise that corrupts survival curves — the analysis this
   whole project exists to produce.
4. **Sustainability.** Live probing roughly doubles the operational surface
   area of an unattended 12-month robot. The single largest threat to this
   project is that it quietly dies in month five.

**No exploitation, ever.** We identify the *presence* of a weakness pattern.
We never attempt to trigger, confirm, or exercise one. We are not measuring
breaches and cannot see them; we measure whether a recognizable weakness
appears in published code and how long it remains.

**No naming and shaming.** Findings are reported in aggregate. Individual
servers are not called out by name in any public output without a specific,
separately considered reason.

## Possible future extension, not currently in scope

**Tier 2.5 — sandboxed dynamic analysis.** Cloning an open-source server and
running it *ourselves* in a container, then inspecting its live behavior with
our own MCP client. This touches nobody else's infrastructure and is
consistent with the licences under which these servers are published.

If this is ever added, it gets its own section here first, written before any
code.

## Operating rules

- Identify ourselves. Any HTTP client sends a descriptive `User-Agent`
  naming the project and linking the repository.
- Be gentle. Rate limit below anything that could be mistaken for abuse, even
  where no published limit exists. We are never in a hurry; the study runs
  for a year.
- Respect the exits. If a maintainer asks to be excluded, they are excluded,
  and the exclusion is recorded as a censoring event rather than silently
  deleted from the data.
- Cache aggressively. Never re-fetch what has not changed. `updated_since`
  exists; use it.

## If in doubt

The default answer is the less intrusive one. Nothing in this project is
urgent enough to justify the other choice.
