"""YOUR TURN (Stage 1a): fetch newsletter emails and turn them into RawEmail.

Gmail API reference: users.messages.list / users.messages.get
Docs: https://developers.google.com/gmail/api/reference/rest/v1/users.messages

Hints:
- list(userId="me", q="newer_than:1d") returns only ids; you need get(..., format="full") per id.
- Message bodies live in payload.parts (nested!). Walk the tree, find the
  mimeType "text/html" and "text/plain" parts, and base64url-decode part.body.data.
- Headers are a list of {name, value}; you need From, Subject, Date, List-Unsubscribe.
- Parse From with email.utils.parseaddr; parse Date with email.utils.parsedate_to_datetime.
- Save each raw message JSON under settings.raw_dir so you can re-run parsing offline
  without hitting the API (this also becomes your eval fixtures later).
"""
from newsletter_brief.schemas import RawEmail


def fetch_emails(query: str = "newer_than:1d") -> list[RawEmail]:
    raise NotImplementedError
