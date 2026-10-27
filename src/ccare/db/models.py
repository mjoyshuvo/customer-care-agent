"""Tables of spec section 8. Names and columns follow the spec so end-state checks map 1:1.

Money is integer cents. Times are timezone-aware UTC.
"""

from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# paraphrase-multilingual-MiniLM-L12-v2 (spec Appendix F.1 reference embedder).
EMBEDDING_DIM = 384


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSONB, list[Any]: JSONB, datetime: DateTime(timezone=True)}


def _now() -> Mapped[datetime]:
    return mapped_column(server_default=func.now())


# --- 8.1 business tables -------------------------------------------------------------------


class Customer(Base):
    __tablename__ = "customers"
    customer_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(32))
    display_name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320), unique=True)
    locale: Mapped[str] = mapped_column(String(8))
    created_at: Mapped[datetime] = _now()


class Staff(Base):
    """Not in spec 8.1, which only names principals in 10.1. Kept apart so staff never own customer rows."""

    __tablename__ = "staff"
    staff_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(32))
    display_name: Mapped[str] = mapped_column(String(200))
    roles: Mapped[list[Any]]


class DemoToken(Base):
    """Static demo bearer tokens of spec 10.1. Only honoured when demo auth is switched on."""

    __tablename__ = "demo_tokens"
    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    principal_id: Mapped[str] = mapped_column(String(32))


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(32))
    customer_id: Mapped[str] = mapped_column(
        ForeignKey("customers.customer_id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(16))
    items: Mapped[list[Any]]
    total_cents: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    carrier: Mapped[str | None] = mapped_column(String(64))
    tracking_number: Mapped[str | None] = mapped_column(String(64))
    eta: Mapped[datetime | None]
    created_at: Mapped[datetime]
    shipped_at: Mapped[datetime | None]
    delivered_at: Mapped[datetime | None]


class Refund(Base):
    __tablename__ = "refunds"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(32))
    customer_id: Mapped[str] = mapped_column(
        ForeignKey("customers.customer_id", ondelete="CASCADE"), index=True
    )
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16))
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True)
    approval_id: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = _now()
    executed_at: Mapped[datetime | None]


class Ticket(Base):
    __tablename__ = "tickets"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(32))
    customer_id: Mapped[str] = mapped_column(
        String(32), index=True
    )  # may be the pseudo customer `unverified`
    conversation_id: Mapped[str | None] = mapped_column(String(32))
    channel: Mapped[str] = mapped_column(String(8))
    subject: Mapped[str] = mapped_column(String(500))
    category: Mapped[str] = mapped_column(String(32))
    priority: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(24))
    queue: Mapped[str] = mapped_column(String(32))
    summary: Mapped[str] = mapped_column(Text)
    assignee: Mapped[str | None] = mapped_column(String(32))
    sla_due_at: Mapped[datetime | None]
    inbound_message_id: Mapped[str | None] = mapped_column(String(500))
    verified_sender: Mapped[str | None] = mapped_column(String(320))
    send_mode: Mapped[str] = mapped_column(String(8), default="draft")
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = _now()


class MailboxMessage(Base):
    __tablename__ = "mailbox_messages"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(32))
    customer_id: Mapped[str | None] = mapped_column(String(32), index=True)
    ticket_id: Mapped[str | None] = mapped_column(String(16), index=True)
    folder: Mapped[str] = mapped_column(String(4))
    status: Mapped[str] = mapped_column(String(16))
    message_id: Mapped[str] = mapped_column(String(500), unique=True)
    in_reply_to: Mapped[str | None] = mapped_column(String(500))
    references: Mapped[list[Any]] = mapped_column(default=list)
    from_addr: Mapped[str] = mapped_column(String(320))
    to_addr: Mapped[str] = mapped_column(String(320))
    subject: Mapped[str] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text)
    headers: Mapped[dict[str, Any]] = mapped_column(default=dict)
    auth_results: Mapped[dict[str, Any] | None]
    triage: Mapped[dict[str, Any] | None]
    received_at: Mapped[datetime]


class EmailDraft(Base):
    __tablename__ = "email_drafts"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(32))
    customer_id: Mapped[str] = mapped_column(String(32), index=True)
    ticket_id: Mapped[str] = mapped_column(String(16), index=True)
    in_reply_to: Mapped[str] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text)
    edited_body: Mapped[str | None] = mapped_column(Text)
    edit_ratio: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(8))
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = _now()


# --- 8.2 agent-state tables ----------------------------------------------------------------


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(32))
    customer_id: Mapped[str] = mapped_column(String(32), index=True)
    channel: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(16))
    agent_version: Mapped[str | None] = mapped_column(String(64))
    title: Mapped[str | None] = mapped_column(String(500))
    summary: Mapped[str | None] = mapped_column(Text)
    summary_through_seq: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = _now()


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("conversation_id", "seq"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    customer_id: Mapped[str] = mapped_column(String(32), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(16))
    author: Mapped[str | None] = mapped_column(String(64))
    content: Mapped[str] = mapped_column(Text)
    data: Mapped[dict[str, Any] | None]
    trace_id: Mapped[str | None] = mapped_column(String(32))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    created_at: Mapped[datetime] = _now()


class ConversationFact(Base):
    __tablename__ = "conversation_facts"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    customer_id: Mapped[str] = mapped_column(String(32), index=True)
    key: Mapped[str] = mapped_column(String(200))
    value: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(16))
    superseded_by: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = _now()


class ConversationSummary(Base):
    __tablename__ = "conversation_summaries"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    customer_id: Mapped[str] = mapped_column(String(32), index=True)
    summary: Mapped[str] = mapped_column(Text)
    through_seq: Mapped[int] = mapped_column(Integer)
    trigger: Mapped[str] = mapped_column(String(8))
    tokens_before: Mapped[int] = mapped_column(Integer)
    tokens_after: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = _now()


class CustomerMemory(Base):
    __tablename__ = "customer_memory"
    __table_args__ = (UniqueConstraint("customer_id", "key"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(32), index=True)
    key: Mapped[str] = mapped_column(String(64))
    value: Mapped[str] = mapped_column(Text)
    provenance: Mapped[dict[str, Any]]
    created_at: Mapped[datetime] = _now()
    expires_at: Mapped[datetime | None]


class PendingAction(Base):
    __tablename__ = "pending_actions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(32))
    customer_id: Mapped[str] = mapped_column(String(32), index=True)
    conversation_id: Mapped[str | None] = mapped_column(String(32))
    channel: Mapped[str] = mapped_column(String(8))
    tool_name: Mapped[str] = mapped_column(String(64))
    args: Mapped[dict[str, Any]]
    idempotency_key: Mapped[str] = mapped_column(String(300), unique=True)
    status: Mapped[str] = mapped_column(String(16), index=True)
    reason: Mapped[str] = mapped_column(Text)
    requested_at: Mapped[datetime] = _now()
    decided_by: Mapped[str | None] = mapped_column(String(32))
    decided_at: Mapped[datetime | None]
    decision_note: Mapped[str | None] = mapped_column(String(500))
    result: Mapped[dict[str, Any] | None]


class Outbox(Base):
    __tablename__ = "outbox"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(32))
    customer_id: Mapped[str | None] = mapped_column(String(32), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict[str, Any]]
    idempotency_key: Mapped[str] = mapped_column(String(300), unique=True)
    status: Mapped[str] = mapped_column(String(16), index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = _now()
    claimed_at: Mapped[datetime | None]
    last_error: Mapped[str | None] = mapped_column(Text)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    scope: Mapped[str] = mapped_column(String(32), primary_key=True)
    key: Mapped[str] = mapped_column(String(300), primary_key=True)
    tool_name: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    response: Mapped[dict[str, Any] | None]
    created_at: Mapped[datetime] = _now()


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = _now()
    tenant_id: Mapped[str] = mapped_column(String(32))
    customer_id: Mapped[str | None] = mapped_column(String(32), index=True)
    conversation_id: Mapped[str | None] = mapped_column(String(32))
    trace_id: Mapped[str | None] = mapped_column(String(32))
    actor: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64), index=True)
    attrs: Mapped[dict[str, Any]] = mapped_column(default=dict)


class Turn(Base):
    __tablename__ = "turns"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # = trace id
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    customer_id: Mapped[str] = mapped_column(String(32), index=True)
    model: Mapped[str | None] = mapped_column(String(128))
    agent_version: Mapped[str | None] = mapped_column(String(64))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    ttft_ms: Mapped[int | None] = mapped_column(Integer)
    tool_calls: Mapped[int] = mapped_column(Integer, default=0)
    stop_reason: Mapped[str] = mapped_column(String(24))
    created_at: Mapped[datetime] = _now()


class RuntimeState(Base):
    __tablename__ = "runtime_state"
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True
    )
    framework: Mapped[str] = mapped_column(String(32), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(32), index=True)
    state: Mapped[dict[str, Any]]


class KbChunk(Base):
    __tablename__ = "kb_chunks"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(32))
    doc_id: Mapped[str] = mapped_column(String(64), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(300))
    section: Mapped[str] = mapped_column(String(500))
    text: Mapped[str] = mapped_column(Text)
    lang: Mapped[str] = mapped_column(String(3))
    url: Mapped[str] = mapped_column(String(500))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))


class SpendLedger(Base):
    """Shared live-spend ledger (B-12): every live call is checked against the cap, then recorded."""

    __tablename__ = "spend_ledger"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = _now()
    label: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(128))
    cost_usd: Mapped[float] = mapped_column(Float)
