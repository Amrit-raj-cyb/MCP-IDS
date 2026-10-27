"""Behavioural features: *what the agent did*, in what order, with which servers.

These describe the sequence of tool use: how many tools and servers were
used, repeats, retries after errors, switches between servers, and how the
session moved from discovery (``tools/list``) to use (``tools/call``).

No tool *names* or argument *values* are used. They would encode the task
(and, for the canary, lab artefacts) instead of behaviour. Only generic
patterns are counted, so the features also make sense for unseen tools.
"""

from __future__ import annotations

from collections import Counter

from features.base import FeatureSpec, ratio
from features.session import Session

SRC = "tools/call requests/responses and method order"

FEATURES = [
    FeatureSpec("duplicate_tool_names_across_servers", "behavioral", "int",
                "Distinct tool names advertised by more than one server", "tools/list responses across servers"),
    FeatureSpec("n_distinct_tools_called", "behavioral", "int", "Different tools called", SRC),
    FeatureSpec("n_servers_mounted", "behavioral", "int", "Servers present in the session", "all wire events"),
    FeatureSpec("n_servers_called", "behavioral", "int", "Servers that received at least one tools/call", SRC),
    FeatureSpec("unused_server_share", "behavioral", "float", "Share of mounted servers never called", SRC),
    FeatureSpec("max_calls_per_server", "behavioral", "int", "Most tools/call requests sent to one server", SRC),
    FeatureSpec("n_single_call_servers", "behavioral", "int", "Servers called exactly once", SRC),
    FeatureSpec("first_call_server_single_use", "behavioral", "int",
                "1 if the first tool call goes to a server that is never called again", SRC),
    FeatureSpec("repeated_identical_calls", "behavioral", "int", "Calls repeating an earlier tool + arguments", SRC),
    FeatureSpec("consecutive_same_tool", "behavioral", "int", "Consecutive calls to the same tool", SRC),
    FeatureSpec("n_distinct_tool_bigrams", "behavioral", "int", "Distinct (tool, next tool) pairs", SRC),
    FeatureSpec("cross_server_transitions", "behavioral", "int", "Consecutive calls that switch server", SRC),
    FeatureSpec("cross_server_transition_share", "behavioral", "float",
                "cross_server_transitions / (calls - 1)", SRC),
    FeatureSpec("retries_after_error", "behavioral", "int", "Failed call followed by a call to the same tool", SRC),
    FeatureSpec("calls_per_server_called", "behavioral", "float", "tools/call requests / servers called", SRC),
    FeatureSpec("trans_list_to_call", "behavioral", "int",
                "Client requests where tools/list is directly followed by tools/call", "client request order"),
    FeatureSpec("trans_call_to_call", "behavioral", "int",
                "Client requests where tools/call is directly followed by tools/call", "client request order"),
    FeatureSpec("n_distinct_method_bigrams", "behavioral", "int",
                "Distinct consecutive (method, method) pairs among client messages", "client message order"),
    FeatureSpec("client_messages_per_server", "behavioral", "float",
                "Client-to-server messages / servers mounted", "all wire events"),
]


def extract(s: Session) -> dict[str, float]:
    ev = s.events
    advertised: dict[str, set[str]] = {}
    for event in ev:
        if event.method == "tools/list" and event.kind == "response":
            for tool in ((event.body.get("result") or {}).get("tools") or []):
                if tool.get("name"):
                    advertised.setdefault(str(tool["name"]), set()).add(event.server_id)
    mounted = {e.server_id for e in ev}
    # tools/call requests in order, with their result's error flag (paired by server + JSON-RPC id)
    errors = {(e.server_id, e.body.get("id")) for e in ev
              if e.method == "tools/call" and e.kind in ("response", "error") and e.is_error}
    calls = [(e.server_id, e.tool, repr(sorted(e.arguments.items())), (e.server_id, e.body.get("id")) in errors)
             for e in ev if e.tool is not None]
    n_calls = len(calls)
    per_server = Counter(c[0] for c in calls)

    seen: set[tuple] = set()
    repeated = 0
    for server, tool, args, _ in calls:
        repeated += (server, tool, args) in seen
        seen.add((server, tool, args))
    pairs = list(zip(calls, calls[1:], strict=False))  # (call, next call); lengths differ by design
    cross = sum(a[0] != b[0] for a, b in pairs)

    client_methods = [e.method for e in ev if e.direction == "client_to_server" and e.method]
    mpairs = list(zip(client_methods, client_methods[1:], strict=False))

    return {
        "duplicate_tool_names_across_servers": sum(len(servers) > 1 for servers in advertised.values()),
        "n_distinct_tools_called": len({(c[0], c[1]) for c in calls}),
        "n_servers_mounted": len(mounted),
        "n_servers_called": len(per_server),
        "unused_server_share": ratio(len(mounted) - len(per_server), len(mounted)),
        "max_calls_per_server": max(per_server.values(), default=0),
        "n_single_call_servers": sum(v == 1 for v in per_server.values()),
        "first_call_server_single_use": int(bool(calls) and per_server[calls[0][0]] == 1 and n_calls > 1),
        "repeated_identical_calls": repeated,
        "consecutive_same_tool": sum(a[:2] == b[:2] for a, b in pairs),
        "n_distinct_tool_bigrams": len({(a[:2], b[:2]) for a, b in pairs}),
        "cross_server_transitions": cross,
        "cross_server_transition_share": ratio(cross, n_calls - 1) if n_calls > 1 else 0.0,
        "retries_after_error": sum(a[3] and a[:2] == b[:2] for a, b in pairs),
        "calls_per_server_called": ratio(n_calls, len(per_server)),
        "trans_list_to_call": sum(a == "tools/list" and b == "tools/call" for a, b in mpairs),
        "trans_call_to_call": sum(a == "tools/call" and b == "tools/call" for a, b in mpairs),
        "n_distinct_method_bigrams": len(set(mpairs)),
        "client_messages_per_server": ratio(len(client_methods), len(mounted)),
    }
