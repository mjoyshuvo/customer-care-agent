"""The authenticated identity of a request (spec: Terms, "Principal")."""

from typing import Literal

from pydantic import BaseModel
from sqlalchemy.orm import Session

from ccare.db import models as m
from ccare.settings import TENANT

AuthLevel = Literal["session", "email_verified", "email_unverified", "system"]


class Principal(BaseModel, frozen=True):
    id: str  # customer id, or staff id for staff
    tenant_id: str = TENANT
    display_name: str
    roles: tuple[str, ...]
    auth_level: AuthLevel = "session"

    @property
    def is_customer(self) -> bool:
        return "customer" in self.roles


def from_demo_token(session: Session, token: str) -> Principal | None:
    row = session.get(m.DemoToken, token)
    if row is None:
        return None
    if customer := session.get(m.Customer, row.principal_id):
        return Principal(id=customer.customer_id, display_name=customer.display_name, roles=("customer",))
    if staff := session.get(m.Staff, row.principal_id):
        return Principal(id=staff.staff_id, display_name=staff.display_name, roles=tuple(staff.roles))
    return None
