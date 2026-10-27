"""Structural features: *how much* traffic, of *which kind*, of *what size*.

These ignore meaning entirely. They only count messages, methods, directions,
errors and bytes, so they could be computed even from traffic whose content
we couldn't read.
"""

from __future__ import annotations

from features.base import FeatureSpec, ratio, stats
from features.session import Session

C2S, S2C = "client_to_server", "server_to_client"
SRC = "wire events (all servers of the session)"

FEATURES = [
    FeatureSpec("n_messages", "structural", "int", "Total JSON-RPC messages in the session", SRC),
    FeatureSpec("n_requests", "structural", "int", "Messages of kind request (either direction)", SRC),
    FeatureSpec("n_responses", "structural", "int", "Responses, including error responses", SRC),
    FeatureSpec("n_notifications", "structural", "int", "Notifications (no id)", SRC),
    FeatureSpec("n_protocol_errors", "structural", "int", "JSON-RPC error responses", SRC),
    FeatureSpec("n_tool_errors", "structural", "int", "tools/call results with isError=true", SRC),
    FeatureSpec("error_rate", "structural", "float", "(protocol + tool errors) / responses", SRC),
    FeatureSpec("request_response_ratio", "structural", "float", "requests / responses", SRC),
    FeatureSpec("n_client_to_server", "structural", "int", "Messages sent by the client", SRC),
    FeatureSpec("n_server_to_client", "structural", "int", "Messages sent by servers", SRC),
    FeatureSpec("server_initiated_request_count", "structural", "int",
                "Requests initiated by servers, including sampling/createMessage", SRC),
    FeatureSpec("client_share", "structural", "float", "Share of messages sent by the client", SRC),
    FeatureSpec("size_mean", "structural", "float", "Mean message size (bytes, neutralized)", SRC),
    FeatureSpec("size_std", "structural", "float", "Std. dev. of message size", SRC),
    FeatureSpec("size_min", "structural", "float", "Smallest message size", SRC),
    FeatureSpec("size_max", "structural", "float", "Largest message size", SRC),
    FeatureSpec("size_total", "structural", "float", "Total bytes exchanged", SRC),
    FeatureSpec("n_initialize", "structural", "int", "initialize requests (= servers connected)", SRC),
    FeatureSpec("n_tools_list", "structural", "int", "tools/list requests", SRC),
    FeatureSpec("n_tools_call", "structural", "int", "tools/call requests", SRC),
    FeatureSpec("tools_list_resp_size_mean", "structural", "float", "Mean size of tools/list responses",
                "tools/list responses"),
    FeatureSpec("tools_list_resp_size_max", "structural", "float", "Largest tools/list response",
                "tools/list responses"),
    FeatureSpec("tools_call_req_size_mean", "structural", "float", "Mean size of tools/call requests",
                "tools/call requests"),
    FeatureSpec("tools_call_req_size_max", "structural", "float", "Largest tools/call request",
                "tools/call requests"),
    FeatureSpec("tools_call_resp_size_mean", "structural", "float", "Mean size of tools/call results",
                "tools/call responses"),
    FeatureSpec("tools_call_resp_size_max", "structural", "float", "Largest tools/call result",
                "tools/call responses"),
]


def extract(s: Session) -> dict[str, float]:
    ev = s.events
    sizes = [e.size for e in ev]
    responses = [e for e in ev if e.kind in ("response", "error")]
    n_req = sum(e.kind == "request" for e in ev)
    n_proto_err = sum(e.kind == "error" for e in ev)
    n_tool_err = sum(e.is_error and e.kind == "response" and e.method == "tools/call" for e in ev)
    n_c2s = sum(e.direction == C2S for e in ev)
    mean, std, mn, mx = stats(sizes)
    tl_resp = [e.size for e in ev if e.method == "tools/list" and e.kind == "response"]
    tc_req = [e.size for e in ev if e.method == "tools/call" and e.kind == "request"]
    tc_resp = [e.size for e in ev if e.method == "tools/call" and e.kind in ("response", "error")]
    return {
        "n_messages": len(ev),
        "n_requests": n_req,
        "n_responses": len(responses),
        "n_notifications": sum(e.kind == "notification" for e in ev),
        "n_protocol_errors": n_proto_err,
        "n_tool_errors": n_tool_err,
        "error_rate": ratio(n_proto_err + n_tool_err, len(responses)),
        "request_response_ratio": ratio(n_req, len(responses)),
        "n_client_to_server": n_c2s,
        "n_server_to_client": sum(e.direction == S2C for e in ev),
        "server_initiated_request_count": sum(e.kind == "request" and e.direction == S2C for e in ev),
        "client_share": ratio(n_c2s, len(ev)),
        "size_mean": mean, "size_std": std, "size_min": mn, "size_max": mx,
        "size_total": float(sum(sizes)),
        "n_initialize": sum(e.method == "initialize" and e.kind == "request" for e in ev),
        "n_tools_list": sum(e.method == "tools/list" and e.kind == "request" for e in ev),
        "n_tools_call": len(tc_req),
        "tools_list_resp_size_mean": stats(tl_resp)[0], "tools_list_resp_size_max": stats(tl_resp)[3],
        "tools_call_req_size_mean": stats(tc_req)[0], "tools_call_req_size_max": stats(tc_req)[3],
        "tools_call_resp_size_mean": stats(tc_resp)[0], "tools_call_resp_size_max": stats(tc_resp)[3],
    }
