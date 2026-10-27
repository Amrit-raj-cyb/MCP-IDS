# MCP background

## Simple version
An AI assistant on its own can only produce text. The **Model Context Protocol**
gives it "hands": the assistant (MCP **client**) connects to MCP **servers**,
each of which offers **tools** it can call. A filesystem server offers
`read_file`; a database server offers `query`.

## Technical version
* Messages are **JSON-RPC 2.0**: *requests* (have `id` + `method`), *responses*
  (have `id` + `result` or `error`), and *notifications* (`method`, no `id`).
* Lifecycle: `initialize` -> `notifications/initialized` -> normal operation.
* Client -> server requests: `tools/list`, `tools/call`, `resources/read`, `prompts/get`, ...
* Server -> client requests: `sampling/createMessage` (ask the client's LLM to
  generate text), `elicitation/create`, `roots/list`.
* Transports: **stdio** (server is a child process; one JSON message per line
  on stdin/stdout) - used in this project - and Streamable HTTP.

## Why it creates a security problem
1. **Metadata is model input.** Tool names and descriptions from `tools/list`
   are placed into the LLM's context. Whoever writes them can attempt prompt
   injection (*tool poisoning*).
2. **Many servers, one context.** A malicious server's descriptions sit next to
   trusted servers' tools and can try to redefine how those are used (*tool
   shadowing*).
3. **Servers can ask the model things.** `sampling/createMessage` lets a server
   push text into the client's LLM (*sampling injection*).
4. **Traditional IDSs are blind here.** Traffic is local (stdio), structured
   JSON, and the "attack" is natural-language intent, not a malformed packet.

## What we observe on the wire (Phase 1 demo)
```
client -> server  initialize
server -> client  result {serverInfo: lab-filesystem 0.1.0, capabilities: {tools}}
client -> server  notifications/initialized
client -> server  tools/list
server -> client  result {tools: [list_directory, read_file, write_file, search_files]}
client -> server  tools/call read_file {"path": "notes.txt"}
server -> client  result {content: [...], isError: false}
client -> server  tools/call read_file {"path": "../outside.txt"}
server -> client  result {content: ["Access denied ..."], isError: true}
```
Phase 3's logging proxy will record exactly these messages as JSONL.
