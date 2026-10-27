# Security, Safety Scope and Threat Model

## 1. Purpose and scope

This is a **defensive, educational research lab**. Its question is *"How can an
IDS detect suspicious behaviour in MCP communication?"* — not *"How can MCP
systems be compromised?"*.

Everything runs on the researcher's machine, inside Docker, on an internal
network with no internet route, using synthetic data only.

## 2. Hard rules

**Allowed:** localhost · Docker containers · dummy SQLite databases · synthetic
files in `sandbox/` · lab-built MCP servers · inert attack simulations ·
placeholder credentials (`placeholder-not-a-real-key`).

**Never:** real credentials or user data · real organisations or targets ·
production systems · credential theft · persistence · malware/ransomware ·
destructive commands · real exploitation · network scanning · data
exfiltration · weakening or bypassing safeguards.

## 3. What makes an attack simulation "inert"

Each attack server in `servers/attack/` (Phases 6–8) must satisfy all of:

1. **Payload is a labelled test string.** Injected text contains the marker
   `[LAB-SIMULATION]` and asks only for something harmless and observable:
   call `add_numbers(1337, 7331)` and/or write `CANARY-7F3A`
   (`common/simulation.py`). It never asks for secrets, file deletion, or
   network access. `tests/test_attacks.py` scans every payload for forbidden
   content (URLs, paths, credentials, delete/exec/send...).
2. **The server itself does nothing harmful.** Its tools return benign values
   (e.g. `add_numbers` really adds numbers). The "attack" exists only as
   *metadata or messages on the wire*.
3. **No real cross-server tampering.** The shadowing simulation only publishes
   conflicting *metadata*; it never modifies or talks to the benign server.
4. **Success is a safe family-specific interaction**, not damage: poisoned
   tool success is measured by its harmless canary; shadowing by a call to its
   static fixture; sampling by the fixed callback acknowledgement. None means
   that a server was compromised.
5. **Lab-only.** Attack servers are registered only in this project's registry
   and are only launched by the orchestrator inside the lab container.

Phase 7 publishes duplicate raw tool-name metadata from a separate fixture
server and never changes or intercepts the filesystem server. The client
namespaces tools per server, so this creates telemetry without overwriting a
tool. Phase 8 sends one bounded, labelled sampling request to a callback that
does not invoke an LLM, tools, or resources.

## 4. Isolation controls (implemented in Phase 1)

| Control | Where |
|---|---|
| Filesystem server confined to sandbox (`..`, absolute paths, symlinks rejected) | `servers/benign/filesystem/server.py`, tested in `tests/test_servers.py` |
| Read/write size limits | same |
| Container runs as non-root UID 10001 | `docker/Dockerfile` |
| All Linux capabilities dropped, `no-new-privileges` | `docker-compose.yml` |
| Internal-only Docker network, no published ports | `docker-compose.yml` (`labnet: internal: true`) |
| Only explicitly scoped `./data`, `./models`, `./results`, `./experiments` folders mounted; code + sandbox baked into image | `docker-compose.yml`, `.dockerignore` |
| Memory and PID limits | `docker-compose.yml` |
| No Docker socket inside containers | design decision, see ARCHITECTURE.md §4.3 |
| Attack servers behave identically to their benign twins (tested); only metadata differs | `servers/attack/`, `tests/test_attacks.py` |
| Server modules configure logging only when run as servers (no side effects on importers) | `common/logsetup.py` |
| Logging proxy never modifies or blocks traffic; logging failures cannot break sessions | `proxy/`, `tests/test_proxy.py` |
| SQLite: read-only authorizer (no writes, ATTACH, PRAGMA, extensions), 2 s query limit, 200-row cap, allow-listed parameterised inserts | `servers/benign/sqlite/server.py` |
| Web fetch: exact-origin allow-list, no credentials in URLs, no redirects, no env proxies, 5 s / 256 KiB limits | `servers/benign/web_fetch/server.py` |
| Test site container: read-only filesystem, internal network only | `docker-compose.yml` (`testweb`) |

Logs contain **full message bodies**, so anything an MCP server returns ends
up in `data/raw/`. That is another reason only synthetic data may exist in the
lab. API keys are read from the environment only and are never sent over MCP
or logged.

Live detector (Phase 14) is observe-only: it runs as a separate process that only
reads the proxies' log files, so it cannot block or rewrite traffic (tested:
logs are byte-identical after the detector ran)
(Phase 14).

## 5. Threat model (what the IDS is meant to detect)

**Assets:** the agent's instructions/goal, the integrity of tool selection, the
data reachable through benign servers.

**Trusted:** the MCP client/agent host, benign servers, the user.

**Untrusted (adversary):** a third-party MCP server mounted in the same agent
session. The adversary controls only what that server sends over MCP:

| Attack family | MCP surface | Direction | Phase |
|---|---|---|---|
| Poisoned tool | `tools/list` → tool `description` | server → client | 6 |
| Tool shadowing | `tools/list` metadata referring to *another* server's tools | server → client | 7 |
| Sampling injection | `sampling/createMessage` server-initiated request | server → client | 8 |

**Out of scope:** compromised client/host, transport-level attacks (MITM on
stdio is not meaningful locally), supply-chain attacks on packages, denial of
service, and attacks requiring real exploitation.

**Detection target:** the *attempt* (malicious metadata/messages present), not
only successful manipulation.

## 6. Reporting issues

If you find that any component could act outside the lab (reach the network,
touch files outside `sandbox/`, or carry a non-inert payload), treat it as a
bug: stop data generation, fix it, and add a regression test.
