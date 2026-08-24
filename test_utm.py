"""
test_utm.py — standalone sanity checks for utm.py and the per-platform
UTM link injection in publisher_router.py. No pytest / test framework
dependency (matches conduler's existing zero-deps style); run directly:

    python test_utm.py
"""

import sys
from urllib.parse import urlsplit, parse_qs

import utm
import publisher_router
import cta as cta_module


def test_build_utm_url_basic():
    url = utm.build_utm_url(
        "https://pandapointscoin.com", source="youtube", medium="video", campaign="pandapoints",
    )
    q = parse_qs(urlsplit(url).query)
    assert q["utm_source"] == ["youtube"], url
    assert q["utm_medium"] == ["video"], url
    assert q["utm_campaign"] == ["pandapoints"], url
    assert "utm_content" not in q, url


def test_build_utm_url_with_content():
    url = utm.build_utm_url(
        "https://pandapointscoin.com", source="tiktok", medium="video",
        campaign="bitcoinfacil", content="como-comprar-bitcoin",
    )
    q = parse_qs(urlsplit(url).query)
    assert q["utm_content"] == ["como-comprar-bitcoin"], url


def test_build_utm_url_preserves_existing_query():
    url = utm.build_utm_url("https://pandapointscoin.com/promo?ref=abc", source="instagram", medium="video", campaign="pandapoints")
    q = parse_qs(urlsplit(url).query)
    assert q["ref"] == ["abc"], url
    assert q["utm_source"] == ["instagram"], url


def test_slugify():
    assert utm.slugify("Como Comprar Panda Points!") == "como-comprar-panda-points"
    assert utm.slugify("") == ""
    assert utm.slugify("já--com  acentos & símbolos") != ""  # doesn't crash, produces *some* slug


def test_build_video_utm_url_uses_title_slug():
    url = utm.build_video_utm_url(
        "https://pandapointscoin.com", platform="youtube", channel="pandapoints",
        title="How to stake PandaPoints", job_id="abcd1234-...",
    )
    q = parse_qs(urlsplit(url).query)
    assert q["utm_source"] == ["youtube"]
    assert q["utm_campaign"] == ["pandapoints"]
    assert q["utm_content"] == ["how-to-stake-pandapoints"], url


def test_build_video_utm_url_falls_back_to_job_id():
    url = utm.build_video_utm_url(
        "https://pandapointscoin.com", platform="tiktok", channel="bitcoinfacil",
        title="", job_id="abcd1234-5678-90ef",
    )
    q = parse_qs(urlsplit(url).query)
    assert q["utm_content"] == ["abcd1234"], url


def test_build_video_utm_url_uses_cta_path():
    url = utm.build_video_utm_url(
        "https://pandapointscoin.com", platform="youtube", channel="pandapoints",
        title="Create your wallet", job_id="abcd1234", cta="create_wallet",
    )
    assert urlsplit(url).path == "/wallet", url


def test_build_video_utm_url_no_cta_keeps_root():
    url = utm.build_video_utm_url(
        "https://pandapointscoin.com", platform="youtube", channel="pandapoints",
        title="No cta here", job_id="abcd1234",
    )
    assert urlsplit(url).path in ("", "/"), url


def test_build_video_utm_url_unknown_cta_keeps_root():
    url = utm.build_video_utm_url(
        "https://pandapointscoin.com", platform="youtube", channel="pandapoints",
        title="Bogus cta", job_id="abcd1234", cta="not_a_real_cta",
    )
    assert urlsplit(url).path in ("", "/"), url


def test_cta_destinations_cover_all_valid_ctas():
    """Every id in cta.VALID_CTAS must resolve to a non-empty path — no silent gaps."""
    for cta_id in cta_module.VALID_CTAS:
        assert cta_module.resolve_cta_path(cta_id), f"missing destination for cta '{cta_id}'"


def test_resolve_cta_path_join_community_forwards_channel():
    """join_community deep-links to /hub with the video's channel, so hub.tsx
    can pick the right-language Telegram group (bitcoinfacil -> PT, pandapoints -> EN)."""
    assert cta_module.resolve_cta_path("join_community", "bitcoinfacil") == "/hub?from=bitcoinfacil"
    assert cta_module.resolve_cta_path("join_community", "pandapoints") == "/hub?from=pandapoints"


def test_resolve_cta_path_join_community_no_channel_omits_from():
    assert cta_module.resolve_cta_path("join_community") == "/hub"
    assert cta_module.resolve_cta_path("join_community", "") == "/hub"


def test_resolve_cta_path_channel_ignored_for_other_ctas():
    """Only join_community forwards the channel; other CTAs' paths are untouched by it."""
    assert cta_module.resolve_cta_path("create_wallet", "bitcoinfacil") == cta_module.resolve_cta_path("create_wallet")
    assert cta_module.resolve_cta_path("try_swap", "pandapoints") == cta_module.resolve_cta_path("try_swap")


def test_build_video_utm_url_join_community_forwards_channel_to_hub():
    url = utm.build_video_utm_url(
        "https://pandapointscoin.com", platform="youtube", channel="bitcoinfacil",
        title="Join our community", job_id="abcd1234", cta="join_community",
    )
    parts = urlsplit(url)
    assert parts.path == "/hub", url
    q = parse_qs(parts.query)
    assert q["from"] == ["bitcoinfacil"], url
    assert q["utm_campaign"] == ["bitcoinfacil"], url


def test_publish_job_uses_distinct_link_per_platform():
    """
    Same job posted to 3 platforms must get 3 different utm_source values
    in the description — this is the whole point of doing it in
    publisher_router instead of upstream in rotman.
    """
    captured = {}

    def fake_publisher(platform):
        def _publish(job):
            captured[platform] = job["description"]
            return {"ok": True, "url": "https://example.com/post", "error": ""}
        return _publish

    original_publishers = dict(publisher_router._PUBLISHERS)
    publisher_router._PUBLISHERS = {
        "youtube":   fake_publisher("youtube"),
        "instagram": fake_publisher("instagram"),
        "tiktok":    fake_publisher("tiktok"),
    }
    try:
        job = {
            "id": "job-1234-5678",
            "channel": "pandapoints",
            "title": "Buy PandaPoints with PIX",
            "description": "Learn how to buy PandaPoints instantly.",
            "platforms": ["youtube", "instagram", "tiktok"],
        }
        results = publisher_router.publish_job(job)

        assert set(results.keys()) == {"youtube", "instagram", "tiktok"}
        assert all(r["ok"] for r in results.values())

        sources = set()
        for platform, description in captured.items():
            assert "Learn how to buy PandaPoints instantly." in description
            assert "pandapointscoin.com" in description
            q = parse_qs(urlsplit(description.splitlines()[-1]).query)
            assert q["utm_source"] == [platform]
            assert q["utm_campaign"] == ["pandapoints"]
            sources.add(q["utm_source"][0])

        assert sources == {"youtube", "instagram", "tiktok"}, sources
    finally:
        publisher_router._PUBLISHERS = original_publishers


def test_publish_job_unknown_platform_error():
    job = {"id": "x", "channel": "pandapoints", "title": "t", "description": "d", "platforms": ["unknown_platform"]}
    results = publisher_router.publish_job(job)
    assert results["unknown_platform"]["ok"] is False
    assert "não implementado" in results["unknown_platform"]["error"]


def test_publish_job_passes_cta_through_to_link():
    """A job with a declared cta must publish a link pointing at that CTA's path."""
    captured = {}

    def fake_publisher(job):
        captured["description"] = job["description"]
        return {"ok": True, "url": "https://example.com/post", "error": ""}

    original_publishers = dict(publisher_router._PUBLISHERS)
    publisher_router._PUBLISHERS = {"youtube": fake_publisher}
    try:
        job = {
            "id": "job-cta-1",
            "channel": "pandapoints",
            "cta": "try_swap",
            "title": "Buy and sell PandaPoints",
            "description": "Learn how to swap.",
            "platforms": ["youtube"],
        }
        publisher_router.publish_job(job)
        link = captured["description"].splitlines()[-1]
        assert urlsplit(link).path == "/bs", link
    finally:
        publisher_router._PUBLISHERS = original_publishers


ALL_TESTS = [
    test_build_utm_url_basic,
    test_build_utm_url_with_content,
    test_build_utm_url_preserves_existing_query,
    test_slugify,
    test_build_video_utm_url_uses_title_slug,
    test_build_video_utm_url_falls_back_to_job_id,
    test_build_video_utm_url_uses_cta_path,
    test_build_video_utm_url_no_cta_keeps_root,
    test_build_video_utm_url_unknown_cta_keeps_root,
    test_cta_destinations_cover_all_valid_ctas,
    test_resolve_cta_path_join_community_forwards_channel,
    test_resolve_cta_path_join_community_no_channel_omits_from,
    test_resolve_cta_path_channel_ignored_for_other_ctas,
    test_build_video_utm_url_join_community_forwards_channel_to_hub,
    test_publish_job_uses_distinct_link_per_platform,
    test_publish_job_unknown_platform_error,
    test_publish_job_passes_cta_through_to_link,
]


def main():
    passed, failed = 0, 0
    for t in ALL_TESTS:
        try:
            t()
            print(f"PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR {t.__name__}: {e!r}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
