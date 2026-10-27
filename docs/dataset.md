# Dataset format

Rules: raw logs are **append-only and never modified**; processed data must
always be regenerable from raw logs plus the manifest; no real data, ever.

## 1. Raw wire logs (Phase 3 ✅)

```
data/raw/sessions/<session_id>/<server_id>.jsonl
```
One file per MCP server per session (written by that server's logging proxy).
One JSON object per line. Merge a session with `proxy.reader.load_session()`.

### Event schema (`schema_version: 2` since lab 0.8.1, defined in `proxy/models.py`)

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | int | Bumped on any format change |
| `session_id` | str | Shared by all servers of one experiment (`MCP_SESSION_ID`) |
| `server_id` | str | Which server this proxy fronts (`filesystem`, ...) |
| `seq` | int | Order within this file (per proxy) |
| `ts_ns` | int | Wall-clock nanoseconds when the proxy *read* the line. On Windows this clock ticks only every ~15.6 ms |
| `mono_ns` | int | **v2.** `time.perf_counter_ns()` at read time: precise and shared by all processes on the host. **Used to order and merge files**; not a wall-clock time. Absent in v1 logs (≤ lab 0.8.0), which are ordered by `(ts_ns, server_id, seq)` |
| `timestamp` | str | Same instant, ISO-8601 UTC |
| `direction` | str | `client_to_server`, `server_to_client`, or `proxy` (lifecycle) |
| `kind` | str | `request`, `response`, `notification`, `error`, `batch`, `invalid`, `lifecycle` |
| `method` | str/null | JSON-RPC method; **for responses, copied from the matching request** |
| `jsonrpc_id` | int/str/null | JSON-RPC id |
| `message_size` | int | Bytes on the wire, excluding the line terminator |
| `is_error` | bool | JSON-RPC error **or** tool result with `isError: true` |
| `error_code`, `error_message` | | From JSON-RPC `error` objects |
| `request_seq` | int/null | Responses: `seq` of the request they answer |
| `latency_ms` | float/null | Responses: time since that request (from `mono_ns` in v2; v1 values on Windows are rounded to ~15.6 ms) |
| `body` | object/null | The full parsed message |
| `raw` | str/null | Only for `invalid` lines: the unparseable text |

Example line (formatted for readability):
```json
{"schema_version": 2, "session_id": "df4919cc...", "server_id": "filesystem",
 "seq": 10, "ts_ns": 1790972798771000000, "mono_ns": 1234567890123,
 "timestamp": "2026-10-02T20:06:38.771000+00:00",
 "direction": "server_to_client", "kind": "response", "method": "tools/call",
 "jsonrpc_id": 4, "message_size": 156, "is_error": true, "error_code": null,
 "error_message": null, "request_seq": 9, "latency_ms": 3.0,
 "body": {"jsonrpc": "2.0", "id": 4, "result": {"content": [{"type": "text",
          "text": "Error executing tool read_file: File not found: 'reports/report.txt'"}],
          "isError": true}}, "raw": null}
```

## 2. Session manifest (Phase 5 ✅)
`<data_dir>/manifests/sessions.jsonl`, one line per session, written by the
orchestrator and validated on write (`orchestrator/manifest.py`). **Only
sessions listed in the manifest with `status: "ok"` belong to the dataset.**

| Field | Meaning |
|---|---|
| `session_id` | Joins with `raw/sessions/<session_id>/` |
| `scenario_id`, `task_id` | What was run |
| `label` | `benign` or `attack` (**the training target**) |
| `attack_family` | `null`, `poisoned_tool`, `shadowing`, `sampling_injection` |
| `attack_attempted` | malicious metadata/messages were sent (true for every attack session) |
| `attack_succeeded` | the agent followed the injected instruction (analysis only) |
| `servers` | mounted servers |
| `backend`, `seed`, `llm_usage` | agent brain, its seed, and tokens/cost for Claude |
| `status`, `error` | `ok` / `failed` + root-cause error |
| `started_at`, `ended_at`, `duration_ms` | timing (dominated by server start-up; don't use as a feature) |
| `stop_reason`, `n_tool_calls`, `n_tool_errors` | the agent's own summary (for checks; features come from logs) |
| `log_dir`, `log_files`, `n_log_events` | where the wire logs are, relative to the data dir |
| `attack_variant` | payload style of the attack (e.g. `tagged`, `param`); null for benign |
| `twin_of` | for attack sessions: the benign scenario they mirror |
| `agent_config` | e.g. `{"susceptibility": 0.35}` for the mock agent |
| `dataset_tag`, `lab_version`, `schema_version` | provenance |

Example (formatted):
```json
{"session_id": "224a4a33...", "scenario_id": "benign:db_order_status",
 "task_id": "db_order_status", "label": "benign", "attack_family": null,
 "attack_attempted": false, "attack_succeeded": false, "servers": ["sqlite"],
 "backend": "mock", "seed": 1, "status": "ok", "duration_ms": 1702.0,
 "stop_reason": "end_turn", "n_tool_calls": 3, "n_tool_errors": 1,
 "log_dir": "raw/sessions/224a4a33...", "log_files": ["sqlite.jsonl"],
 "n_log_events": 13, "dataset_tag": "dev", "lab_version": "0.8.1", ...}
```

## 3. Feature dataset (Phase 10 ✅)
Produced by `python -m features.extractor --data-dir <dataset> --out <dir>`
into a **separate** directory (it refuses to write inside the source dataset).
For the Phase 6 data: `data/try6_ml/`.

| File | Content |
|---|---|
| `features.csv` | one row per session with `status: ok`; first the **metadata** columns `session_id, scenario_id, task_id, label, attack_family, attack_variant, attack_succeeded, seed, twin_of` (analysis only, never model inputs), then the 62 feature columns |
| `feature_schema.json` | every feature: name, category, dtype, description, source, preprocessing, `used_for_training`; plus the neutralization note |
| `dataset_summary.json` | source path, source SHA-256, counts, styles, feature counts, versions |
| `README.md` | short description of the above |

Derived data is always regenerable from the raw logs and manifest. The
source dataset's SHA-256 is recorded so models can be traced to the exact
data they were trained on. See [ml.md](ml.md) for the feature definitions.

## 4. Phase 9 generated dataset

`python -m scripts.generate_phase9` creates a separate directory such as
`data/phase9_081_targeted/`. By default it creates 30 matched benign/attack
trials per family (180 sessions), cycling through the corresponding calculator,
shadowing-probe and sampling-probe tasks, including all-server variants. Every
sampling-labeled session is verified to contain `sampling/createMessage`. It
uses the deterministic mock agent and fixed seed (`9000`). Run it in
Docker so the synthetic web origin and environment are stable:

```bash
docker compose build
docker compose run --rm lab python -m scripts.generate_phase9 --output /lab/data/phase9_081_targeted --seed 9000 --parallel 4 --sessions-per-family 30
docker compose run --rm lab python -m scripts.generate_phase9 --output /lab/data/phase9_081_targeted --verify-only
```

The earlier verified release contains six matched task-sized pairs (12
sessions), recorded with lab 0.7.0. **Do not use it for sampling detection:**
in lab 0.7.0 the client advertised the sampling capability only in
sampling-simulation sessions, a label leak in every `initialize` (fixed in
0.8.0). It also omitted six-server `all_servers` scenarios and included
different twin result text. Generate a fresh dataset using lab 0.8.1. The
generator refuses a non-empty output directory. It writes the existing
manifest and raw proxy JSONL plus `generation_config.json`, `metadata.json`,
and a dataset `README.md`. Verification checks session and manifest
agreement, completion status, event schema, required fields, labels, and
unique session IDs. `metadata.json` records counts, attack family/variant and
success distributions, runtime details, and a SHA-256 digest. Do not edit raw
records; regenerate into a fresh directory if a new run is needed.

The preserved `data/phase9/` directory failed lifecycle verification, and
`data/phase9_verified/` was recorded with lab 0.7.0. Do not use either for
current multi-family ML. The current verified run is
`data/phase9_081_targeted/`; `data/phase9_081_balanced/` is a separate
interrupted attempt and is explicitly marked unusable in its README.

## 5. Unique benign corpus (held-out test set)

`python -m scripts.generate_benign_corpus` builds the largest **unique** benign
corpus the lab can currently produce: for each of the 22 benign tasks it
finds every distinct mock-agent behaviour (100 in total; seeds 50000–51999
searched) and runs each one once in both server mixes. Output:
`data/benign_unique_081/` (200 sessions, `verify` consistent, 197 distinct
feature vectors), with `generation_config.json` (the chosen seeds),
`metadata.json` and `README.md`. Benign only: the script refuses any attack
scenario. Two hashes exist: `metadata.json` hashes every file of the folder;
`features.extractor` hashes manifest + logs (`dataset_summary.json`).

```bash
docker compose run --rm lab python -m scripts.generate_benign_corpus --output /lab/data/benign_unique_081
docker compose run --rm lab python -m scripts.generate_benign_corpus --output /lab/data/benign_unique_081 --verify-only
```

### Lab 0.9.0 corpora and composition

| Folder | Sessions | Content |
|---|---|---|
| `data/benign_unique_090` | 634 | every distinct behaviour of all 38 tasks × both server mixes, original wording |
| `data/benign_varied_090` | 317 | every distinct behaviour once, all benign servers mounted, reworded descriptions (wordings 1/2/3 cycled) |
| `data/combined_p9_benign090` | 814 | copy of `phase9_081_targeted` + `benign_unique_090` (training set of `exp_005`) |

### Lab 0.9.1 corpora and the final dataset (2026-10-10)

| Folder | Sessions | Content |
|---|---|---|
| `data/benign_sampling_091` | 232 | the four benign sampling tasks: 29 distinct behaviours × 2 server mixes × 4 wordings (composed from `benign_sampling_091_v0`…`_v3`) |
| `data/combined_sampling_20261010` | 1,586 | `combined_expanded_20261006` + `benign_sampling_091` |
| `data/combined_canonical_20261010` | **2,220** | the above + `benign_unique_090`: **the current training and evaluation dataset** (1,860 benign / 360 attack, 42 tasks, 52,162 MCP messages) |

Adding `benign_unique_090` removed a wording confound: before, every attack session used the
servers' original tool wording while 808 of 1,226 benign sessions used reworded descriptions,
so wording alone hinted at the label (see docs/ml.md). Feature tables are in the matching
`*_ml` folders.

Generator options: `--server-mix both|own|all`, `--description-variant 0|1|2|3|cycle`,
`--tasks t1,t2` (only these tasks).
`scripts/compose_dataset.py` copies manifests and raw logs of several datasets
into a new folder (sources are only read), refuses duplicate session IDs and
non-empty outputs, runs `verify`, and writes `composition.json` with each
source's SHA-256. The manifest field `description_variant` records the wording
used per session (null = original).
