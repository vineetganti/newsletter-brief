"""YOUR TURN (Stage 1b): turn a messy link into a canonical URL, or None if it's not content.

tests/test_parse.py is the spec. Make those tests pass.

Hints:
- urllib.parse.urlsplit / parse_qsl / urlencode / urlunsplit
- Tracking params: utm_*, fbclid, gclid, mc_cid, mc_eid, ref, ...
- Canonical = lowercase host, drop fragment, drop tracking params, sort remaining
  params, strip trailing slash.
- Redirect resolving (Substack/Mailchimp) needs network: keep it a separate function
  (resolve_redirect) so canonicalize() stays pure and fast to test.
"""

TRACKING_PARAMS: set[str] = set()  # fill in; prefixes like "utm_" need separate handling


def canonicalize(url: str) -> str:
    raise NotImplementedError


def is_content_link(url: str, text: str) -> bool:
    """False for unsubscribe, 'view in browser', social, mailto:, etc."""
    raise NotImplementedError
