from newsletter_brief.parse.canonicalize import canonicalize, is_content_link


def test_strips_tracking_params():
    assert (
        canonicalize("https://Example.com/post?utm_source=nl&utm_medium=email&id=7#top")
        == "https://example.com/post?id=7"
    )


def test_param_order_and_trailing_slash_normalized():
    assert canonicalize("https://example.com/a/?b=2&a=1") == canonicalize("https://example.com/a?a=1&b=2")


def test_same_story_different_tracking_is_equal():
    a = canonicalize("https://blog.dev/x?mc_cid=abc&mc_eid=1")
    b = canonicalize("https://blog.dev/x?utm_campaign=z")
    assert a == b == "https://blog.dev/x"


def test_non_content_links_dropped():
    assert not is_content_link("https://nl.com/unsubscribe?u=1", "Unsubscribe")
    assert not is_content_link("https://nl.com/web/abc", "View in browser")
    assert not is_content_link("https://twitter.com/someone", "Follow us")
    assert not is_content_link("mailto:hi@nl.com", "Reply")


def test_real_article_kept():
    assert is_content_link("https://blog.dev/agents-in-prod", "How we run agents in prod")
