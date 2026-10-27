# Progress

Two tracks (see the approved plan and [`docs/architecture.md`](docs/architecture.md)):

- **Track A, platform (Claude builds, you review):** FastAPI app, FastMCP gateway, Postgres, KB, guards,
  approvals, outbox, email pipeline, eval harness, compose, docs.
- **Track B, learning (you build, Claude instructs):** docker-agent (`agents/support.yaml`), Kubernetes, AWS.

Requirement status per row: [`docs/requirements-map.md`](docs/requirements-map.md).

## Phase 0: Foundations + spikes

### Track A — done (2026-10-27)

- Python 3.12 project (`uv`, `ruff`, `pytest`), package `src/ccare/`.
- `deploy/compose/compose.yaml`: Postgres 17 + pgvector on port 5433.
- Schema for every table of spec section 8 (+ `staff`, `demo_tokens`, `spend_ledger`), Alembic migration.
- Seed loader for spec section 10 (`uv run ccare seed`): 4 customers, 2 staff, 6 orders, 3 tickets, 7 mails, the
  T-a1000001 email conversation with summary and pinned fact.
- Gateway stub: FastMCP over streamable HTTP at `/mcp` with a `whoami` tool. Identity comes only from
  `Authorization: Bearer`; demo tokens work only with `CCARE_DEMO_AUTH=1`.
- KB: the 14 Appendix D documents in `kb/docs/` (`scripts/extract_spec.py`).
- Requirements map: 111 rows (79 MUST, 32 SHOULD, 4 waived), each with component and phase.
- Tests: 8 passed (seed counts, cents, thread fact, mail bodies, reseed; whoami binds token, no token, demo off).

### Track B — your steps

1. `git init`, link `github.com/mjoyshuvo/customer-care-agent`. Commit when you are ready (I do not commit).
2. docker-agent (installed: `docker agent` v1.27.1). Run an official example on Anthropic, then on OpenRouter
   or a LiteLLM proxy.
3. Identity spike: `uv run ccare gateway` (needs `CCARE_DEMO_AUTH=1`), point an agent's MCP toolset at
   `http://127.0.0.1:8100/mcp` with a bearer token, ask it to call `whoami`. Record which headers arrive.

### Metrics

| Metric | Before | After | n |
|---|---|---|---|
| Offline tests passing | 0 | 8 | 8 |
| Requirement rows mapped | 0 | 111 | 111 |

No agent metrics yet: the live baseline is recorded in Phase 2.

### Problems found

- A local Postgres already uses port 5432; compose uses 5433.
- `email` as a package name would shadow the standard library; the package is `mail`.

### Next phase should

- Settle the identity mechanism from the spike before the gateway grows to 14 tools.
