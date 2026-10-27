# Architecture

Spec: [`requirements-and-benchmarks.md`](../requirements-and-benchmarks.md). Requirement status:
[`requirements-map.md`](requirements-map.md). Progress: [`../PROGRESS.md`](../PROGRESS.md).

## 1. Principles

1. **The tool layer is the security boundary, not the prompt.** Identity, ownership checks, approvals,
   idempotency and limits live in the gateway. A model or agent-YAML mistake cannot break them (spec 6, R-4.6.1).
2. **docker-agent is only the agent loop.** It is one of three interchangeable loops behind one interface:
   `docker-agent`, `scripted` (no-model baseline, spec 15.2) and `fake` (scripted tool calls, for the red team).
   Server, tools, policy and evals stay the same when the loop changes (B-16).
3. **The database is the source of truth.** Any docker-agent session is a cache that can be rebuilt from the
   summary, pinned facts and history (R-4.3.1).
4. **Offline by default.** No model call unless `CCARE_LIVE=1`; every live call goes through the spend ledger.
5. **Open-source for the edges.** Chat UI, login and dashboards are off-the-shelf; we only build what the spec
   makes ours.

## 2. Containers

```mermaid
flowchart LR
    subgraph Users
        C[Customer]
        S[Staff / Admin]
    end

    subgraph UI["Open-source UI and dashboards"]
        OW["Open WebUI<br/>login, chat, model picker"]
        LF["Langfuse<br/>traces, tokens, cost, context"]
        GF["Grafana + Prometheus<br/>latency, errors, cost, escalations"]
    end

    subgraph Platform["Platform (Python, built here)"]
        APP["app — FastAPI<br/>spec API + SSE<br/>OpenAI-compatible /v1 adapter<br/>turn pipeline, guards<br/>staff console"]
        GW["gateway — FastMCP<br/>14 tools, policy, approvals,<br/>idempotency, audit"]
        WK["worker<br/>outbox, email poll,<br/>expiry, retention"]
        KB["kb<br/>ingest, hybrid search, rerank"]
        ML["mail<br/>email pipeline 3.2"]
    end

    subgraph Agent["Agent loop (your track)"]
        DA["docker-agent API server<br/>agents/support.yaml<br/>root · faq · orders · email"]
    end

    PG[("Postgres<br/>+ pgvector, FTS, RLS")]
    LLM["Model providers<br/>Anthropic · OpenAI · OpenRouter<br/>LiteLLM proxy · Docker Model Runner"]

    C --> OW
    OW -- "OpenAI-compatible /v1<br/>+ forwarded user headers" --> APP
    S --> APP
    APP -- "run turn" --> DA
    DA -- "LLM calls" --> LLM
    DA -- "MCP streamable HTTP<br/>per-session token" --> GW
    GW --> KB
    GW --> PG
    APP --> PG
    WK --> PG
    WK --> ML
    ML -- "agent turn, channel email" --> APP
    APP -. OTel .-> LF
    GW -. OTel .-> LF
    DA -. OTel .-> LF
    APP -. metrics .-> GF
```

| Container | Owns | Spec |
|---|---|---|
| `app` | Auth, routes, SSE, turn pipeline, input/output guards, budgets, persistence, staff console, OpenAI-compatible adapter for Open WebUI | 3.1, 7.2-7.5, 9 |
| `gateway` | The 14 tools, closed schemas, execution order, policy file, approvals, idempotency, tool-output filter, audit | 6, 7.1, 7.7 |
| `worker` | Outbox (approved actions, email send), approval expiry, retention, inbox poll | 3.3, 6.7, 7.8 |
| `kb` | Heading-path chunks, embeddings, BM25 + vector, RRF, rerank, citations | B-04 |
| `mail` | Dedupe, loop rules, sender trust, quarantined reader, triage hardening, threading | 3.2 |
| docker-agent | Model calls, routing between sub-agents | (any framework) |
| Postgres | All state; pgvector for KB and history; row-level security per customer | 8, B-19 |

Code layout: everything Python is under `src/ccare/` (`app`, `gateway`, `kb`, `mail`, `db`, `seed`). The email
package is `mail`, not `email`, so it does not shadow the standard library.

## 3. Identity: how a tool call knows the customer

The model never names the customer (B-06, B-20). The bearer token of the HTTP request that carries the MCP call
decides.

```mermaid
sequenceDiagram
    autonumber
    participant OW as Open WebUI
    participant APP as app
    participant DA as docker-agent
    participant GW as gateway (MCP)
    participant DB as Postgres

    OW->>APP: POST /v1/chat/completions (X-OpenWebUI-User-Email)
    APP->>APP: map user to principal (C-1001), mint turn token<br/>bound to conversation + channel
    APP->>DA: run turn (session = conversation, token)
    DA->>GW: tools/call request_refund {order_id, amount_eur, ...}<br/>Authorization: Bearer (turn token)
    GW->>DB: resolve token -> principal, check ownership
    GW-->>DA: {"status": "pending_approval", ...}
    DA-->>APP: events, final text
    APP-->>OW: streamed reply (after output guard)
```

**Open point (Phase 0 spike):** how docker-agent attaches a per-session token to a remote MCP toolset. The
gateway already reads `Authorization: Bearer` and logs `X-Conversation-Id`, `X-Channel` and `Mcp-Session-Id`
(`whoami` tool). The spike decides between: per-session headers from docker-agent, an environment-expanded header
per session, or one docker-agent session per conversation started with its own token. The decision goes here.

## 4. Turn pipeline (spec 3.1, order is normative)

```mermaid
flowchart TD
    A[customer message] --> B{rate limit<br/>20 turns / 60 s}
    B -- over --> X1[guard_block + final 'blocked']
    B -- ok --> C[persist user message]
    C --> D{input guard<br/>score ≥ 0.8?}
    D -- block --> X2[guard_block + final 'blocked'<br/>0 model calls]
    D -- redact / pass --> E[build context:<br/>fixed system prompt +<br/>summary, facts, memory block +<br/>messages after last compaction +<br/>escalation signal]
    E --> F{> 40 messages or<br/>> 30k tokens?}
    F -- yes --> G[compact, pin facts first]
    F -- no --> H
    G --> H[agent loop under turn timeout<br/>every tool call via gateway<br/>stream filter on text]
    H -- timeout / budget / error --> X3[error + final fallback]
    H --> I[output guard on final text<br/>final text is authoritative]
    I --> J[persist tool msgs, assistant msg, turns row<br/>emit turn.completed, pin facts]
    J --> K[final event]
```

## 5. Gateway execution order (spec 6.5)

```mermaid
flowchart TD
    T[tools/call] --> U{known tool?}
    U -- no --> R1[unknown_tool]
    U -- yes --> V{allowed for role<br/>and channel?}
    V -- no --> R2[denied + audit tool.denied]
    V -- yes --> W{turn tool budget<br/>and rate limit}
    W -- over --> R3[budget_exceeded / rate_limited]
    W -- ok --> X{closed schema valid?}
    X -- no --> R4["invalid_args [{loc, msg}]"]
    X -- yes --> Y{policy: unverified sender,<br/>disabled, always_approve,<br/>tool approval rule}
    Y -- deny --> R2
    Y -- needs approval,<br/>none approved --> R5[pending action + audit<br/>approval.requested → pending_approval]
    Y -- allow --> Z{read-only?}
    Z -- yes --> RO[handler under timeout → tool-output filter → ok]
    Z -- no --> WR[reserve idempotency key →<br/>ONE transaction: re-check approval, handler,<br/>output filter, store result, audit tool.executed<br/>failure: rollback, release key, audit tool.failed]
```

## 6. Approval flow (spec 3.3)

```mermaid
stateDiagram-v2
    [*] --> pending: tool needs approval
    pending --> approved: staff approves (compare-and-set)
    pending --> rejected: staff rejects
    pending --> expired: 24 h, maintenance job
    approved --> executed: outbox worker runs tool as system principal
    approved --> failed: handler fails (retried by outbox, 5 attempts)
    executed --> [*]
    rejected --> [*]
    expired --> [*]
    failed --> [*]
```

A customer deciding gets 403; a second decision gets 409; two concurrent decisions: exactly one wins.

## 7. Email pipeline (spec 3.2)

```mermaid
flowchart TD
    M[inbound mail] --> D1{known Message-ID?}
    D1 -- yes --> DROP[drop]
    D1 -- no --> L{loop rules:<br/>auto-reply, bulk, noreply, OOO subject}
    L -- match --> SK[skipped, audit email.skipped]
    L -- no --> ST{DMARC pass AND<br/>header From on file?}
    ST -- no --> HU[route to human]
    ST -- yes --> Q["quarantined reader — NO tools<br/>→ closed triage schema"]
    Q -- fails --> HU
    Q --> H[harden triage against the mail:<br/>drop unseen ids/amounts, phishing, injection]
    H --> RT{auto-reply? phishing?<br/>3 replies / 24 h?}
    RT -- auto-reply --> SK
    RT -- phishing / rate --> HU
    RT -- ok --> TH{thread to ticket via<br/>In-Reply-To / References}
    TH -- ticket escalated --> HU
    TH --> AG["agent turn, channel email<br/>sees only 'Ticket: T-…' + triage block"]
    AG --> DR[draft_reply → send_reply]
    DR -- draft mode --> AP[pending approval → staff edits/approves]
    AP --> OB["outbox email.send<br/>To = ticket.verified_sender (read at send time)"]
```

## 8. Data model (core)

```mermaid
erDiagram
    customers ||--o{ orders : places
    orders ||--o{ refunds : "refunded by"
    customers ||--o{ conversations : has
    conversations ||--o{ messages : contains
    conversations ||--o{ conversation_facts : pins
    conversations ||--o{ conversation_summaries : "compacted into"
    conversations ||--o{ turns : "measured by"
    customers ||--o{ customer_memory : remembers
    customers ||--o{ tickets : opens
    tickets ||--o{ mailbox_messages : threads
    tickets ||--o{ email_drafts : "replied by"
    customers ||--o{ pending_actions : requests
    pending_actions ||--o| outbox : "executed via"
    customers ||--o{ idempotency_records : "scoped by"
```

Full column list: spec section 8 and [`src/ccare/db/models.py`](../src/ccare/db/models.py). Extra tables not in
the spec: `staff`, `demo_tokens` (seed principals of 10.1) and `spend_ledger` (B-12). Money is integer cents.

## 9. Models and providers

| Task | Where the call happens | Default model (live) | Offline |
|---|---|---|---|
| Chat / email agent turns | docker-agent (`agents/support.yaml`) | cheap model for faq, stronger for refunds and email | `scripted` loop |
| Email reader (quarantined, no tools) | `mail`, via LiteLLM SDK | small model | rule-based reader (3.2) |
| LLM judge | `evals`, via LiteLLM SDK | small model, one shared id | rule judge, criteria `skipped` |
| Compaction summary | `app`, via LiteLLM SDK | small model | deterministic summary |

Providers reachable from both docker-agent and LiteLLM: Anthropic, OpenAI, OpenRouter (OpenAI-compatible
`base_url`), a LiteLLM proxy (OpenAI-compatible), Docker Model Runner. Every model id needs a row in the price
table (input, output, cache read, cache write); an unknown model raises (B-22).

## 10. Deployment path

| Stage | Where | Notes |
|---|---|---|
| Local | `deploy/compose/compose.yaml` | Phase 0: Postgres. Grows to the full stack above. |
| Kubernetes | kind / k3d, `deploy/k8s/` | Stateless pods; turn lock, rate limits and SSE buffers move to Redis first (R-4.1.2). HPA, then KEDA on outbox depth. |
| AWS ECS Fargate | `deploy/terraform/` | Smallest tasks, no NAT, SSM for secrets, budget alert, destroy after each session. |
| AWS EKS | `deploy/terraform/` | Same manifests as kind; Spot or Fargate profiles; destroyed the same day. |
