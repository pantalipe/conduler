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


ALL_TESTS = [
    test_build_utm_url_basic,
    test_build_utm_url_with_content,
    test_build_utm_url_preserves_existing_query,
    test_slugify,
    test_build_video_utm_url_uses_title_slug,
    test_build_video_utm_url_falls_back_to_job_id,
    test_publish_job_uses_distinct_link_per_platform,
    test_publish_job_unknown_platform_error,
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
