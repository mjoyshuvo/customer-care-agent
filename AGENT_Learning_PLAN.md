# Agent Platform Plan: docker-agent + Kubernetes + AWS

## Claude's role: instructor, not doer

I (the user) will do all the work myself. Claude guides me.

- Do **not** create files, write full code, or run commands for me unless I ask.
- For each task, give me **step-by-step instructions**: what to do, which command to run, and what result to expect.
- Explain **why** each step matters, in simple words.
- Give small hints or snippets only when I am stuck, not full solutions.
- After each step, wait for me to share my output or result. Then review it, point out mistakes, and give the next step.
- At the end of each phase, quiz me with 3 short questions to check I understood.
- When I ask "do it for me", then Claude may do that one step.

## Source of truth: official docs and best practices

- Follow the official docker-agent repository and documentation for every step:
  - Repo: https://github.com/docker/docker-agent/tree/main
  - Docs: https://docs.docker.com/ai/docker-agent/
  - Best practices: https://docs.docker.com/ai/docker-agent/guides/tips/
  - Examples: https://github.com/docker/docker-agent/tree/main/examples
- Before giving instructions for a feature (agents, tools, permissions, hooks, sandbox, compaction, sessions, chat server, API server, OpenTelemetry), **read the matching doc page first**. Do not answer from memory.
- docker-agent changes fast. Check the latest README, docs, and release notes. If the docs and your memory disagree, follow the docs.
- Use the exact config syntax and CLI flags shown in the docs and examples.
- Link the doc page you used in each instruction, so I can read it too.
- Follow official best practices for the other tools as well: Kubernetes docs, AWS Well-Architected (cost and security pillars), and Terraform docs.
- If something is not documented, say so clearly and mark it as your suggestion.

## How Claude must follow this plan

1. Work on **one phase at a time**. Do not start the next phase until the current phase passes its exit criteria.
2. At the start of each phase, read `PROGRESS.md` and this file.
3. Each phase must **improve or optimize** something measurable. Record before/after numbers in `PROGRESS.md`.
4. Prefer the **smallest working change**. Fix root causes, not symptoms.
5. Never create paid AWS resources without asking me first. Always say the expected cost.
6. Every AWS resource must be in Terraform. End each AWS session with `terraform destroy` unless I say otherwise.
7. Never commit secrets. Use `.env` (git-ignored), Kubernetes Secrets, or SSM Parameter Store.
8. At the end of each phase, update `PROGRESS.md` with:
   - What was built
   - Metrics (before → after)
   - Problems found
   - What the next phase should fix

## Project use case

A **customer support agent team**:

- `root` (triage): understands the question and routes it.
- `faq`: answers from a knowledge base (read-only).
- `orders`: checks order status (read-only tool).
- Write actions (refunds, account changes) always need human approval.

## Repo layout (target)

```
agent-platform/
├── agents/support.yaml
├── app/                 # thin backend: auth, rate limit, history
├── deploy/
│   ├── compose/         # local stack
│   ├── k8s/             # manifests or Helm/Kustomize
│   └── terraform/       # AWS
├── loadtest/            # k6 scripts
├── evals/               # test conversations + injection tests
├── PLAN.md
└── PROGRESS.md
```

---

## Phase 0: Baseline (local, free)

**Goal:** a working single agent and a way to measure it.

Tasks:
1. Create `agents/support.yaml` with one agent and a cheap model.
2. Set a budget limit in the agent config.
3. Write 20 test conversations in `evals/` (normal questions + 5 prompt-injection attempts).
4. Run `docker agent run` and `docker agent serve chat`.

Exit criteria:
- Agent answers the 15 normal cases correctly.
- Baseline recorded: avg latency, tokens per conversation, cost per conversation, injection pass rate.

**Improves:** nothing yet. This phase creates the numbers every later phase must beat.

---

## Phase 1: Agent team + quality (local, free)

**Goal:** better answers at lower cost.

Tasks:
1. Split into `root`, `faq`, `orders` sub-agents.
2. Use a cheaper model for simple agents (faq), a stronger one only where needed.
3. Add RAG or a knowledge file for the FAQ agent.
4. Give each agent only the tools it needs.

Exit criteria:
- Correct answers ≥ Phase 0.
- **Cost per conversation lower** than Phase 0.

**Optimizes:** cost and accuracy.

---

## Phase 2: Security hardening (local, free)

**Goal:** reduce prompt-injection blast radius.

Tasks:
1. Configure permissions: deny shell and filesystem write for all support agents.
2. Add hooks that block or require approval for any write tool.
3. Use `.agentsignore` to hide sensitive files.
4. Never give one agent both "reads untrusted text" and "can take actions".
5. Expand `evals/` to 20 injection attempts.

Exit criteria:
- 0 unauthorized tool calls in injection tests.
- No regression in normal answers.

**Optimizes:** security.

---

## Phase 3: Observability (local, free)

**Goal:** see what every agent does.

Tasks:
1. Docker Compose stack: agent server, Grafana, Tempo, Prometheus.
2. Enable OpenTelemetry tracing in docker-agent.
3. Dashboard: latency per agent, tokens, errors, cost.

Exit criteria:
- One trace shows the full path: root → sub-agent → tool → answer.
- Find and fix the slowest step found in traces.

**Optimizes:** latency (using data, not guesses).

---

## Phase 4: Backend, history and context (local, free)

**Goal:** real chat sessions that survive restarts.

Tasks:
1. Thin backend in `app/`: user auth, per-user rate limit, proxy to agent server.
2. Store chat history in Postgres or Redis, not in agent process memory.
3. Configure compaction. Keep key facts (customer ID, order ID, issue) in memory or session plan so they survive compaction.
4. Test: restart the agent container mid-conversation.

Exit criteria:
- Conversation continues correctly after restart.
- Long conversations (50+ turns) stay under the context limit and keep key facts.

**Optimizes:** reliability and context survival.

---

## Phase 5: Kubernetes + scaling (local kind/k3d, free)

**Goal:** prove it scales horizontally.

Tasks:
1. Create a kind or k3d cluster.
2. Deploy agent server, backend, Redis/Postgres, observability.
3. Make agent pods stateless.
4. Add HPA. Then add a queue for long tasks and scale with KEDA on queue depth.
5. Load test with k6 at 10 → 50 → 100 concurrent users.

Exit criteria:
- Pods scale up and down automatically.
- p95 latency stays within target under load.
- No lost conversations during scale-down.

**Optimizes:** scalability.

---

## Phase 6: AWS on ECS Fargate (low cost, ask before applying)

**Goal:** run in the cloud at minimum cost.

Tasks:
1. Terraform: ECR, ECS Fargate (smallest size), SQS, SSM Parameter Store, CloudWatch (short retention).
2. Public subnets, no NAT Gateway.
3. AWS Budget alert (e.g. $10).
4. Run the load test, record cost per hour and cost per conversation.
5. `terraform destroy` at the end.

Exit criteria:
- Same eval results as local.
- Cost per hour and per conversation recorded.

**Optimizes:** cloud cost.

---

## Phase 7: AWS EKS (short sessions only)

**Goal:** run the Phase 5 Kubernetes setup on real AWS Kubernetes.

Tasks:
1. Terraform EKS with Spot nodes or Fargate profiles.
2. Reuse Phase 5 manifests with minimal changes.
3. Compare with ECS: cost, effort, scaling speed.
4. Destroy the same day.

Exit criteria:
- Written comparison ECS vs EKS in `PROGRESS.md` with a recommendation.

**Optimizes:** architecture choice based on real numbers.

---

## Phase 8: Continuous optimization loop

Repeat each round:
1. Read dashboards and `PROGRESS.md`.
2. Pick the single biggest problem (cost, latency, errors, or security).
3. Fix it with the smallest change.
4. Re-run evals and load tests.
5. Record before → after.

Ideas to try:
- Prompt caching
- Model routing (cheap model first, escalate only when needed)
- Caching common FAQ answers
- Smaller context per sub-agent
- CI pipeline that runs evals on every change

---

## Metrics to track every phase

| Metric | Target direction |
|---|---|
| Correct answer rate | ↑ |
| Injection tests passed | ↑ (aim 100%) |
| Cost per conversation | ↓ |
| p95 latency | ↓ |
| Max concurrent users | ↑ |
| Infra cost per hour | ↓ |
