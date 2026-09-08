# Domain notes — session 1 (2026-09-05)

Everything below is background gathered before writing any code. Nothing here
is a commitment; it's the map.

---

## 1. Where MCP servers live

There are three distinct layers, and conflating them is the most common
mistake in this area.

**Layer 1 — the metadata layer (registries).** These store *pointers*, not
code.

| Source | What it is | Programmatic access |
|---|---|---|
| Official MCP Registry (`registry.modelcontextprotocol.io`) | Canonical, DNS/GitHub-verified namespaces. Backed by Anthropic, GitHub, PulseMCP, Microsoft. Still labelled "preview" — breaking changes and data resets possible. | **Yes.** Clean REST API. Confirmed working. |
| Glama | Aggregator/metaregistry | Yes, REST API |
| Smithery | ~7,000+ servers, also hosts remote servers itself | Site + partial API |
| mcp.so | ~19,000+ listings | No API; submissions via GitHub issues |
| MCP Market | ~10,000+ | Browsable site only |
| PulseMCP, Docker MCP Catalog | Aggregators / curated catalogs | Varies |

**Layer 2 — the package layer.** npm, PyPI, Docker Hub. This is where the
actual code is. The official registry explicitly delegates security scanning
to these and to downstream aggregators — it does not scan anything itself.

**Layer 3 — the running layer.** Live endpoints: `streamable-http` and `sse`
URLs, plus locally-run `stdio` servers. This is where a server's *actual
behavior* is, and it's the layer where scanning raises legal and ethical
questions.

### What the official registry API actually gives us

Verified live on 2026-09-05.

```
GET https://registry.modelcontextprotocol.io/v0/servers
    ?limit=<n>
    &cursor=<nextCursor>
    &updated_since=<RFC3339 timestamp>
    &version=latest
```

Response shape:

```jsonc
{
  "servers": [{
    "server": {
      "$schema": "...schemas/2025-12-11/server.schema.json",
      "name": "ai.abmeter/abmeter",        // reverse-DNS, namespace-verified
      "title": "ABMeter",
      "description": "...",
      "version": "0.2.0",
      "websiteUrl": "https://abmeter.ai",
      "repository": { "url": "https://github.com/abmeter/abmeter",
                      "source": "github" },   // OPTIONAL — often absent
      "remotes": [{ "type": "streamable-http",
                    "url": "https://mcp.abmeter.ai",
                    "headers": [...] }],
      "packages": [ /* npm / pypi / oci coordinates — when present */ ]
    },
    "_meta": {
      "io.modelcontextprotocol.registry/official": {
        "status": "active",              // also: deprecated, deleted
        "statusChangedAt": "...",
        "publishedAt": "...",
        "updatedAt": "...",
        "isLatest": true
      }
    }
  }],
  "metadata": { "nextCursor": "ai.abmeter/abmeter:0.2.0", "count": 2 }
}
```

**Why this matters enormously for us:**

- `updated_since` + cursor pagination = cheap incremental polling. We can ask
  "what changed since my last run" instead of re-fetching everything.
- The registry keeps **every version** as its own entry, with
  `publishedAt`/`updatedAt`. That is a free, pre-existing time series of
  publication events — a partial head start on our own timeline.
- `status` transitions (`active` → `deprecated` → `deleted`) with
  `statusChangedAt` is exactly the "server vanished" signal our censoring
  logic needs, handed to us with a timestamp.
- `repository` is **optional**. Servers without one can't be statically
  analyzed. That's a sampling-frame problem to think about, not ignore.

---

## 2. What "a security problem" concretely means here

Two families, and they behave completely differently over time.

### Family A — conventional software vulnerabilities

Command injection, path traversal, SSRF, hardcoded credentials, vulnerable
dependencies. Ordinary bugs that happen to be in an MCP server.

- Detectable with existing static tooling (Semgrep, Bandit, `npm audit`,
  `pip-audit`, SonarQube), so detection is *cheap and deterministic*.
- Prior work (arXiv 2506.13538) found these in ~7.2% of servers, credential
  exposure the most common at ~3.6%.
- Remediation is legible: a commit fixes it, a version bump ships it.

### Family B — MCP-specific issues

These come from the protocol's core design: the model reads tool descriptions
as instructions, and often auto-executes.

- **Tool poisoning** — hidden instructions embedded in a tool's description
  field, aimed at the model rather than the user. Found in ~5.5% of a sampled
  subset (2506.13538).
- **Rug pulls** — the description is benign at approval time and changes
  later. **Only detectable with a time series.** Nobody can measure this
  without prior snapshots.
- **Unauthenticated / exposed remote endpoints** — "Exposed by Design"
  (arXiv 2608.00150) assessed internet-facing MCP servers at scale.
- **Token passthrough / confused deputy / over-broad scopes** — the server
  holds credentials on the user's behalf and hands them around carelessly.
- **Shadow servers** — OWASP MCP Top 10 (2025) MCP09: unsanctioned servers
  in an environment. Mostly an enterprise concern; probably out of scope.

### The hard constraint on detection

MCPZoo (arXiv 2607.11086), across 64,611 servers and 8 published MCP security
scanners:

- mean precision **45.5%** (range 10.4%–96.9%)
- overall recall **24.2%**
- mean pairwise Jaccard agreement between scanners **15.7%**

Read that as: *the published tools mostly disagree about what a vulnerable MCP
server is.* For a snapshot paper that's a footnote. For us it's structural —
a detector that flips its verdict on unchanged code manufactures fake
"vulnerability appeared / was fixed" events, and those fake events land
directly in our survival curves.

**Implication for design:** prefer a small number of high-precision,
deterministic, version-pinned detectors over broad coverage. We should be able
to say "this detector, on this input, always returns this answer." Recall we
can sacrifice; precision and stability we cannot.

---

## 3. Prior work — and where the gap actually is

| Paper | Scale | Method | Time dimension |
|---|---|---|---|
| MCP at First Glance (arXiv 2506.13538) | 1,899 → 583 repos | SonarQube + mcp-scan | Snapshot, March 2025 |
| A Measurement Study of MCP (arXiv 2509.25292) | — | ecosystem measurement | Snapshot |
| First Look at Security Issues in MCP (arXiv 2510.16558, DSN 2026) | — | static analysis | Snapshot |
| MCPZoo (arXiv 2607.11086) | 64,611 servers | dynamic + scanner eval | Snapshot |
| Exposed by Design (arXiv 2608.00150) | internet-facing | dynamic assessment | Snapshot |

The gap is real: none of these measure change over time. Note two things,
though —

1. Some of these have *far* more scale than a solo undergraduate can match.
   Our contribution can't be "more servers." It has to be "the same servers,
   many times, for a long time." Design accordingly: a smaller, well-chosen,
   stable cohort beats a large sloppy one.
2. Two of these are 2026 papers. The field is moving fast, and someone may
   start a longitudinal study this year. Recheck the literature every few
   months; that's a calendar item, not a vibe.

---

## 4. Infrastructure facts confirmed

- **GitHub Actions is free and unmetered for public repositories.**
- **Scheduled workflows are disabled after 60 days of repository
  inactivity.** Widely documented; a whole genre of "keepalive" actions exists
  because of it. Having each run commit its results back does count as
  activity — but this needs verifying in practice, not assuming.
- **Scheduled workflows are best-effort.** They fire late under load and can
  be skipped entirely. Our schema must record *actual* observation time, never
  assume the nominal schedule ran. A missed run is data, not an error.

---

## 5. Open questions carried into session 2

1. Unit of observation: registry entry, source repository, or live endpoint?
2. Cohort: everything, or a fixed sampled panel?
3. Detector set: which specific, deterministic checks?
4. Do we touch live endpoints at all? (ethics + legality)
5. RQ2 (disclosure): observational only, or do we disclose ourselves?
6. Storage: SQLite committed to the repo, or Postgres?

---

## Sources

- [Official MCP Registry](https://registry.modelcontextprotocol.io/) — API verified live
- [The MCP Registry — modelcontextprotocol.io](https://modelcontextprotocol.io/registry/about)
- [modelcontextprotocol/registry on GitHub](https://github.com/modelcontextprotocol/registry)
- [MCP at First Glance (arXiv 2506.13538)](https://arxiv.org/abs/2506.13538)
- [MCPZoo: Rethinking MCP Security (arXiv 2607.11086)](https://arxiv.org/html/2607.11086)
- [A Measurement Study of MCP (arXiv 2509.25292)](https://arxiv.org/html/2509.25292v1)
- [Toward Understanding Security Issues in MCP (arXiv 2510.16558)](https://arxiv.org/html/2510.16558)
- [Exposed by Design (arXiv 2608.00150)](https://arxiv.org/html/2608.00150v1)
- [OWASP MCP Top 10 (2025) — MCP09 Shadow MCP Servers](https://owasp.org/www-project-mcp-top-10/2025/MCP09-2025%E2%80%93Shadow-MCP-Servers)
- [Best MCP Registries in 2026 — TrueFoundry](https://www.truefoundry.com/blog/best-mcp-registries)
- [Disabling and enabling a workflow — GitHub Docs](https://docs.github.com/actions/managing-workflow-runs/disabling-and-enabling-a-workflow)
