# NEXT STEP — read this first when you sit down

*Last updated 2026-09-09. This file always describes the one thing to do next.
Unfamiliar word? Check `docs/glossary.md`.*

---

## Done so far

- Repo set up, pushed to GitHub, virtual environment working
- Scope locked to Tier 1 + Tier 2, written up in `docs/ethics.md`
- `fetch_all_servers()` written and working — walks the whole registry
- **First census: 28,625 entries, 28,625 unique server names, 0 duplicates.**
  So `version=latest` works and that number is the study's sampling frame.
- Snapshot saved at `data/raw/registry-20260908T174659Z.jsonl` (29 MB)

## Do next: describe what's in the snapshot

You have 28,625 records. You don't yet know what's *in* them. Four counts,
all from the same loop you already wrote in `scan/characterize.py`.

Each of these changes a decision later, so they're worth getting before the
schema is designed.

### 1. How many entries have a `repository` field?

`repository` is the link to the server's public source code. No repository
means no code to read, which means that server can never be part of Tier 2
static analysis — it can only be observed at the metadata level.

**Why it matters:** this number is the ceiling on your entire code-analysis
arm. If it's 90% you're fine. If it's 40%, half the study's design changes,
and the paper has to say so out loud.

### 2. Of those, how many are GitHub?

Look at `repository["source"]`. If it's all `github`, cloning is one code
path. If GitLab and Bitbucket show up, that's extra work to plan for.

### 3. What's the `status` breakdown?

Count how many entries have each value of `status`: `active`, `deprecated`,
`deleted`. ("Breakdown" = a tally of how a population splits across the
values of one field.)

`status` lives inside `_meta`, under the long key
`"io.modelcontextprotocol.registry/official"`. Pull that nested dict into a
variable first or the lines become unreadable.

**Why it matters:** `deleted` with a timestamp is your "this server vanished"
signal, and vanishing is one of the outcomes the survival analysis has to
handle. Knowing how common it already is tells you how much of the study that
branch carries.

### 4. What's the range of `publishedAt`?

Oldest and newest. These are text timestamps, and because they're in
`YYYY-MM-DDTHH:MM:SSZ` form they sort correctly as plain strings — no date
parsing needed yet.

**Why it matters:** it tells you how much history the registry is handing you
for free, from before your study started.

## How to write it

Same shape as the unique-names loop: one counter per question, all
incremented inside the single pass over the file.

```python
with_repo = 0
...
        server = record["entry"]["server"]
        if "repository" in server:
            with_repo += 1
```

That's the pattern. The other counts are the same move.

For the status breakdown you want a tally per value rather than one number.
`collections.Counter` does this in one line if you want to look it up;
a plain dict works fine too.

## One habit: look before you count

Before counting a field, find one record that has it and print it:

```python
print(json.dumps(server, indent=2))
```

Then read the real key names. You cannot deduce what a field is called — a
large share of bugs in data work come from assuming a field is named what you
would have named it.

## After the four numbers

Two decisions, in this order, then we can put it on a schedule:

1. **Storage strategy.** 29 MB per run. Full snapshots every time, or use
   `updated_since` to fetch only what changed? Affects repo size for the next
   year and is annoying to change later.
2. **The schema.** What one row looks like. The expensive decision — change it
   in month four and months one to three stop being comparable.

Bring the four numbers back and we'll do storage.
