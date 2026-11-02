"""Shared data shapes. Stage 1 only: raw email in, parsed email out.

Summary/brief-item schemas get added in Stage 2.
"""
from datetime import datetime

from pydantic import BaseModel


class RawEmail(BaseModel):
    id: str
    sender: str  # full "Name <addr>" From header
    sender_addr: str  # bare address, lowercased; this is the allowlist key
    subject: str
    date: datetime
    html: str | None = None
    text: str | None = None
    has_list_unsubscribe: bool = False


class Link(BaseModel):
    text: str
    url: str  # canonical form (tracking stripped)


class ParsedEmail(BaseModel):
    email_id: str
    sender_addr: str
    subject: str
    body_text: str
    links: list[Link]
