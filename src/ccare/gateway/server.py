"""MCP tool gateway (spec 6.5). Phase 0: only the `whoami` spike tool.

Identity comes from the bearer token of the HTTP request that carries the MCP call, never from tool
arguments (B-06, B-20). The spike shows which headers docker-agent actually sends, so we can decide how a
per-session identity reaches this server.
"""

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers

from ccare.db.engine import session_factory
from ccare.principal import Principal, from_demo_token
from ccare.settings import get_settings

mcp = FastMCP("ccare-gateway")

# Headers worth seeing in the spike. Never echo Authorization itself.
SPIKE_HEADERS = {"x-conversation-id", "x-channel", "x-session-id", "user-agent", "mcp-session-id"}


def resolve_principal(headers: dict[str, str]) -> Principal | None:
    auth = headers.get("authorization", "")
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    if not get_settings().ccare_demo_auth:
        return None  # no real authenticator yet; demo tokens only work when switched on (spec 2.2)
    with session_factory()() as session:
        return from_demo_token(session, token)


@mcp.tool
def whoami() -> dict:
    """Return the customer this session acts for. Spike tool for Phase 0; removed in Phase 1."""
    headers = get_http_headers(include_all=True)
    principal = resolve_principal(headers)
    return {
        "principal": principal.model_dump() if principal else None,
        "had_bearer": headers.get("authorization", "").lower().startswith("bearer "),
        "headers_seen": {k: v for k, v in headers.items() if k in SPIKE_HEADERS},
    }


def http_app():
    return mcp.http_app(path="/mcp")
