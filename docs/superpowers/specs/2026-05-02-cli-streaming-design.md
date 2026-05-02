# CLI Streaming Output Protocol

## Problem

The CLI currently blocks for the entire duration of a multi-query, multi-provider
search, then emits a single JSON blob to stdout. When a provider has a low rate
limit (e.g. 1 req/s), the caller sees nothing for tens of seconds. Calling
agents have no way to distinguish "still running" from "stuck".

## Solution: NDJSON Line Protocol

stdout becomes a newline-delimited stream of JSON objects. Each line is
independently parseable. stderr is reserve for human-readable progress
messages (optional, not part of the contract).

Every event object has two fixed fields:

| Field | Type | Meaning |
|---|---|---|
| `finish` | bool | Whether the process is complete. Always `false` except on the last line. |
| `type` | string | Discriminator — one of `progress`, `papers`, `result`. |

### Event: `progress`

Emitted at the start and before each provider call. Gives the caller
instant feedback that work is happening.

```json
{"finish":false,"type":"progress","current":1,"total":16,"message":"searching openalex for 'silicon anode'..."}
```

| Field | Type | Meaning |
|---|---|---|
| `current` | int | 1-based index of the current operation. |
| `total` | int | Total number of operations (`len(queries) * len(providers)`). |
| `message` | string | Human-readable status text. |

### Event: `papers`

Emitted once per successful (provider, query) pair. Lets the caller
process results incrementally.

```json
{"finish":false,"type":"papers","provider":"openalex","query":"silicon anode","count":15,"papers":[{...},...]}
```

| Field | Type | Meaning |
|---|---|---|
| `provider` | string | Provider name. |
| `query` | string | The query string that produced these results. |
| `count` | int | Number of papers in this batch. |
| `papers` | array | Array of paper objects (same structure as `_paper_to_dict`). |

These are **raw per-provider results** — they may contain duplicates with
results from other providers. The final `result` event contains the
deduplicated authoritative set.

### Event: `error`

Emitted when a single provider call fails. The process continues with
remaining providers.

```json
{"finish":false,"type":"error","provider":"arxiv","query":"silicon anode","message":"Connection timeout"}
```

| Field | Type | Meaning |
|---|---|---|
| `provider` | string | Provider name. |
| `query` | string | The query string that failed. |
| `message` | string | Error description. |

### Event: `result`

Always the last line. Contains the deduplicated, sorted final result set.

```json
{"finish":true,"type":"result","success":true,"count":27,"results":[...],"warnings":["..."]}
```

On total failure (zero successful calls):

```json
{"finish":true,"type":"result","success":false,"error":"All search attempts failed.","warnings":["arxiv: timeout","..."]}
```

| Field | Type | Meaning |
|---|---|---|
| `success` | bool | Whether at least one provider returned results. |
| `count` | int | Total paper count (present when success=true). |
| `results` | array | Deduplicated, date-sorted papers (present when success=true). |
| `warnings` | array | Non-fatal warnings accumulated during the run. |
| `error` | string | Fatal error message (present when success=false). |

### Paper object format (unchanged)

Same structure as the current `_paper_to_dict`:

```json
{
  "source": "openalex",
  "external_id": "W123",
  "title": "...",
  "authors": ["Author A", "Author B"],
  "publication_date": "2024-06-01",
  "doi": "10.1000/example",
  "venue": "Nature",
  "abstract": "...",
  "url": "https://...",
  "quartile": "Q1"
}
```

## Changes

### cli.py

- Replace `_output()` calls with a new `_emit(event: dict)` helper that
  prints a single JSON line to stdout via `print(json.dumps(event))`.
- Restructure `_run_search` to emit `progress` → `papers|error` → `result`
  as it iterates through the query×provider loop.
- Update error paths to emit a `result` event with `success: false` instead
  of calling `_error()` directly.
- The `--compact` flag becomes a no-op (each line is already compact) and is
  kept only for backward-compat argument parsing.
- stderr output: added for human-readable progress (e.g. `print(f"[{i}/{total}] searching {provider} for '{query}'...", file=sys.stderr)`) — non-contract, informational only.

### scraper.py

- Change `time.sleep(delay_seconds)` to `await asyncio.sleep(delay_seconds)`.
  This was caught during the same pass: the scraper runs inside `asyncio.run()`
  but used a synchronous sleep that blocks the event loop.

### Backward Compatibility

This is a breaking change to the stdout format: from a single JSON document
to line-delimited JSON. Mitigating factors:

- Project is v0.1.0 with a small user base.
- The protocol is strictly more agent-friendly: line-by-line consumption is
  the norm for agent input handling.
- Callers that `json.loads()` the full stdout will break. Migration is
  straightforward: read line by line, keep the last `finish:true` line.

## Non-Goals

- **QuartileStore memory/connection optimization** — separate cycle.
- **MCP progress notifications** — separate cycle after the CLI protocol is
  stable.
- **Provider-level result caching** — out of scope.
