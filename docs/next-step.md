# NEXT STEP — read this first when you sit down

*Last updated 2026-09-09. This file always describes the one thing to do next.
When it's done, we replace it with the next one.*

---

## Where the project is right now

Setup is finished. Repo created, pushed to GitHub, virtual environment
working, `requests` installed.

**One function is unwritten**, and nothing else can happen until it exists:
`fetch_all_servers()` in `scan/fetch_registry.py`.

## What that function does, in one sentence

The MCP registry hands out its list of servers 100 at a time, and this
function keeps asking for the next batch until it has them all.

The registry won't give you everything in one response. Each response ends
with a **cursor** — a bookmark meaning "you got up to here." You send that
bookmark back to get the next batch. Repeat until the response comes back
without one, which is how the registry says "that's everything." Your job is
the loop that does that.

## Start the session

1. Open VS Code → File → Open Recent → `mcp-longitudinal`
2. Ctrl + ` to open the terminal at the bottom
3. `.venv\Scripts\Activate.ps1` — the prompt should show `(.venv)`
4. Open `scan/fetch_registry.py` from the sidebar, find `fetch_all_servers`,
   delete the `raise NotImplementedError` line

If you ever see `ModuleNotFoundError: No module named 'requests'`, it means
step 3 didn't happen. It's almost always step 3.

## Write it in eight pieces

Indentation matters in Python: pieces 1 and 8 sit at 4 spaces (function
level), pieces 3–7 at 8 spaces (inside the loop).

**1. What you're carrying through the loop**

```python
    all_servers: list[dict] = []
    cursor: str | None = None
    seen_cursors: set[str] = set()
```

The list you're filling, the bookmark for the next request (`None` means
"start at the beginning"), and a record of bookmarks already used.

**2. The loop**

```python
    for page_num in range(1, MAX_PAGES + 1):
```

A `for` over a range instead of `while True`, so the page cap is enforced
automatically and there's no counter to forget.

**3. Fetch a page and keep its servers**

```python
        data = fetch_page(cursor=cursor, updated_since=updated_since)

        page_servers = data["servers"]
        all_servers.extend(page_servers)
        print(f"page {page_num}: {len(page_servers)} servers, {len(all_servers)} total")
```

`extend` adds the items. `append` would add the whole list as one item and
you'd get a list of lists.

**4. Look for the next bookmark**

```python
        next_cursor = data["metadata"].get("nextCursor")
```

`.get()` returns `None` when the key is missing. Square brackets would crash
on the final page, because that's exactly where the key stops being there.

**5. Stop when there isn't one**

```python
        if next_cursor is None:
            print(f"no nextCursor on page {page_num} — walk complete")
            break
```

**6. Stop if the bookmark repeats**

```python
        if next_cursor in seen_cursors:
            print(f"cursor {next_cursor!r} repeated — stopping to avoid a loop")
            break
        seen_cursors.add(next_cursor)
```

Without this, a registry bug that returns the same cursor twice means you
request the same page forever, hitting someone else's server once a second
until you notice.

**7. Move the bookmark forward, then wait a moment**

```python
        cursor = next_cursor
        time.sleep(SLEEP_BETWEEN_PAGES)
```

**8. Warn if you ran out of pages, and hand back the results**

```python
    else:
        print(f"WARNING: hit MAX_PAGES ({MAX_PAGES}) — results may be incomplete")

    return all_servers
```

That `else` belongs to the `for`, not to an `if` — it lines up with the `for`
and runs only if the loop ended without hitting a `break`. Here that means you
burned through every allowed page and never found the end, so the data is
truncated and you need to know.

## Run it

```powershell
python -m scan.fetch_registry
```

You should see pages tick past, then a line saying where the file was written
(somewhere under `data/raw/`).

## Two numbers to write down

- **Did every page return 100?** If they all come back 50, the API is
  silently capping the page size and `PAGE_SIZE` is a fiction.
- **What was the total?** That number is the sampling frame for the entire
  study. Every percentage you ever report is relative to it.

## When it works

```powershell
git add -A
git commit -m "Add registry pagination walker"
git push
```

Then say so, and we move on to reading what's actually in that file — which is
the step that decides the database schema.

## If it breaks

Copy the whole error, bottom line included, and bring it back. Reading a
traceback is a skill worth having; the last line says what went wrong and the
lines above say where.
