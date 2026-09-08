# Glossary

Terms used in this project, defined in plain language. Grows as we go. If a
word shows up in conversation and isn't here, it should be — say so.

---

## Data shapes

**Field** — one named piece of information inside a record. In
`{"name": "abmeter", "version": "0.2.0"}`, the fields are `name` and
`version`. "Field name" means the label on the left of the colon. It matters
because you have to spell it exactly right to read it — `repository` and
`repo` are different fields, and asking for the wrong one gets you nothing.

**Key** — same thing as a field name, in Python dictionary language. `d["name"]`
means "give me the value stored under the key `name`."

**Nested** — a field whose value is itself a whole record with its own fields.
`server["repository"]["url"]` reads: inside `server`, find `repository`, and
inside that, find `url`. Records nest arbitrarily deep.

**JSON** — the standard text format for structured data on the web. Curly
braces for records, square brackets for lists.

**JSONL** ("JSON Lines") — a file where every *line* is one complete JSON
record. Our snapshots use it because you can read one line at a time without
loading the whole file, and you can append a new record without rewriting
what's already there. A plain `.json` file holding one giant list would have
to be rewritten in full every time.

**Record / entry** — one item in the data. In our snapshots, one line = one
registry entry = one MCP server.

**Snapshot** — everything the registry said at one moment in time, saved to a
file. The study is a stack of snapshots taken at different moments.

**Schema** — the agreed shape of your records: which fields exist, what they
mean, what types they hold. Deciding the schema is deciding what questions you
will be able to ask a year from now, which is why we're being slow about it.

---

## The MCP registry specifically

**Registry** — a directory of MCP servers. It stores *descriptions* of servers,
not the servers themselves. Like a library catalogue: it tells you a book
exists and where to find it, but the catalogue card is not the book.

**Package registry** — a different thing, and the source of most confusion.
npm (JavaScript), PyPI (Python) and Docker Hub host the actual downloadable
*code*. The MCP registry just points at them.

**`packages`** — a field on a registry entry listing where the server's code is
published: which npm package name, or PyPI name, or Docker image, plus how to
run it. Its presence means "you can download and run this yourself." Its
absence usually means the server is remote-only.

**`remotes`** — a field listing live URLs where the server is already running
and can be connected to over the network. We deliberately never contact these;
see `ethics.md`.

**`repository`** — a field pointing at the server's public source code, usually
a GitHub URL. **Optional**, which is a real limitation for us: no repository
means no source code to analyse, so that server can only ever be observed at
the metadata level.

**`_meta`** — the block on each entry holding registry bookkeeping rather than
server description: `status`, `statusChangedAt`, `publishedAt`, `updatedAt`,
`isLatest`. This is the time information, and it is the reason this study is
possible. Never discard it.

**`status`** — the registry's own label for an entry's lifecycle state:
`active`, `deprecated`, or `deleted`. A **status breakdown** just means
counting how many entries have each value — "24,000 active, 3,900 deprecated,
700 deleted." A breakdown is a count of how a population splits across the
possible values of one field.

**Cursor** — a bookmark the API hands you meaning "you've read up to here, send
this back to get the next batch." See `next-step.md` for why APIs use them.

---

## Working with code

**Repository (git sense)** — a folder whose change history git is tracking.
Confusingly the same word as the registry field above. Context tells you which.

**Cloning** — downloading a complete copy of someone's git repository to your
machine, history included (`git clone <url>`). For Tier 2 analysis we clone a
server's public repository, read its source code, and delete it. Reading only —
we never run it.

**Static analysis** — examining source code without executing it, looking for
patterns that indicate a problem (a password written into the file, a shell
command built from user input). "Static" as opposed to "dynamic," which means
running the thing and watching what it does. We only do static.

**Counter** — a plain variable holding a running total, incremented as you loop
over data. `with_repo = 0`, then `with_repo += 1` each time you see one. Not a
special tool, just a habit.

**Virtual environment (venv)** — a private package folder for one project, so
this project's library versions can't collide with another project's. Has to be
activated in each new terminal: `.venv\Scripts\Activate.ps1`.

**Traceback** — the block of text Python prints when it crashes. The **last**
line says what went wrong; the lines above show the path of calls that led
there. Read it bottom-up.

---

## The research

**Longitudinal** — measuring the same subjects repeatedly over time, as opposed
to a **snapshot** or **cross-sectional** study which measures many subjects
once.

**Sampling frame** — the full set of things you could possibly observe. Ours is
28,625 servers. Every percentage you report is relative to it, so it has to be
stated.

**Survival analysis** — statistics for "how long until an event happens."
Borrowed from medicine. Here the event is "the security problem disappeared."

**Right-censoring** — when the study ends before the event happens, so all you
know is that the true duration is *longer* than what you observed. Common and
correctly handled by survival analysis; discarding these cases is a classic
error that makes fixes look faster than they are.

**Remediation** — the problem getting fixed.

**Precision and recall** — two ways a detector can be wrong. Low precision =
it flags things that are fine. Low recall = it misses things that aren't.
Published MCP scanners score badly on both, which is why we favour a few
reliable checks over many unreliable ones.
