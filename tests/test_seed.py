from sqlalchemy import func, select

from ccare.db import models as m


def count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def test_seed_counts(db):
    assert count(db, m.Customer) == 4
    assert count(db, m.Staff) == 2
    assert count(db, m.Order) == 6
    assert count(db, m.Refund) == 0
    assert count(db, m.Ticket) == 3
    assert count(db, m.MailboxMessage) == 7


def test_seed_money_is_integer_cents(db):
    assert db.get(m.Order, "O-1002").total_cents == 12000
    assert db.get(m.Order, "O-4001").total_cents == 99900


def test_thread_ticket_has_conversation_summary_and_fact(db):
    ticket = db.get(m.Ticket, "T-a1000001")
    conv = db.get(m.Conversation, ticket.conversation_id)
    assert conv.summary_through_seq == 2
    facts = db.scalars(select(m.ConversationFact).where(m.ConversationFact.conversation_id == conv.id)).all()
    assert [(f.key, f.value) for f in facts] == [("order:O-1002", "delivered 2026-10-03")]


def test_seed_mail_bodies_end_with_one_line_break(db):
    for msg_id in ["<seed-benign-001@mail.example.com>", "<seed-thread-002@mail.example.com>"]:
        body = db.scalar(select(m.MailboxMessage.body).where(m.MailboxMessage.message_id == msg_id))
        assert body.endswith("\n") and not body.endswith("\n\n")


def test_seed_is_repeatable(db, engine):
    from ccare.db.engine import session_factory
    from ccare.seed import data

    with session_factory(engine)() as s, s.begin():
        data.load(s)
    assert count(db, m.Order) == 6
