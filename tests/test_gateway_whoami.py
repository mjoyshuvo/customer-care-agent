import pytest
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

from ccare.gateway.server import http_app


@pytest.fixture
def demo_auth(monkeypatch):
    monkeypatch.setenv("CCARE_DEMO_AUTH", "1")


async def call_whoami(headers: dict[str, str]) -> dict:
    import httpx

    app = http_app()
    async with app.router.lifespan_context(app):
        transport = StreamableHttpTransport(
            "http://test/mcp",
            headers=headers,
            httpx_client_factory=lambda **kw: httpx.AsyncClient(transport=httpx.ASGITransport(app=app), **kw),
        )
        async with Client(transport) as client:
            result = await client.call_tool("whoami", {})
            return result.data


@pytest.mark.anyio
async def test_whoami_binds_bearer_to_customer(db, demo_auth):
    out = await call_whoami({"Authorization": "Bearer demo-ada", "X-Conversation-Id": "abc"})
    assert out["principal"]["id"] == "C-1001"
    assert out["principal"]["roles"] == ["customer"]
    assert out["headers_seen"]["x-conversation-id"] == "abc"
    assert "authorization" not in out["headers_seen"]


@pytest.mark.anyio
async def test_whoami_without_token_has_no_principal(db, demo_auth):
    out = await call_whoami({})
    assert out["principal"] is None


@pytest.mark.anyio
async def test_demo_tokens_ignored_when_demo_auth_off(db, monkeypatch):
    monkeypatch.setenv("CCARE_DEMO_AUTH", "0")
    out = await call_whoami({"Authorization": "Bearer demo-ada"})
    assert out["principal"] is None


@pytest.fixture
def anyio_backend():
    return "asyncio"
