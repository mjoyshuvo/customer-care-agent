# customer-care-agent

A customer support agent (chat + email) built to [`requirements-and-benchmarks.md`](requirements-and-benchmarks.md),
with docker-agent as the agent loop. Design: [`docs/architecture.md`](docs/architecture.md).
Status: [`PROGRESS.md`](PROGRESS.md), [`docs/requirements-map.md`](docs/requirements-map.md).

## Quick start

```bash
cp .env.example .env
docker compose -f deploy/compose/compose.yaml up -d --wait
uv sync
uv run alembic upgrade head
uv run ccare seed
uv run pytest
```

Run the MCP gateway (streamable HTTP at `http://127.0.0.1:8100/mcp`):

```bash
CCARE_DEMO_AUTH=1 uv run ccare gateway
```

Demo tokens (development only, spec 10.1): `demo-ada`, `demo-bjorn`, `demo-chen`, `demo-ase`, `demo-agent`,
`demo-admin`.
