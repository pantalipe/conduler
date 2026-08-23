"""
utm.py
Builds outbound links tagged with UTM params for attribution in the
PandaPoints analytics pipeline. Mirrors utils/utmBuilder.ts on the
pandapoints-dapp side — same four params, same semantics — so a link
built here and a link built there are interchangeable.

Stdlib only (urllib.parse, re) — no external dependencies.
"""

import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from cta import resolve_cta_path


def slugify(text: str, max_len: int = 60) -> str:
    """
    Lowercase, ASCII-ish slug for use as utm_content (e.g. video title →
    'como-comprar-panda-points'). Falls back to '' for empty/None input.
    """
    if not text:
        return ""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len].strip("-")


def build_utm_url(base_url: str, source: str, medium: str, campaign: str, content: str = "") -> str:
    """
    Appends utm_source/utm_medium/utm_campaign/(utm_content) query params
    to base_url. Any existing query string on base_url is preserved.
    """
    parts = urlsplit(base_url)
    query = dict(parse_qsl(parts.query))
    query["utm_source"] = source
    query["utm_medium"] = medium
    query["utm_campaign"] = campaign
    if content:
        query["utm_content"] = content
    new_query = urlencode(query)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))


def build_video_utm_url(base_url: str, platform: str, channel: str, title: str = "", job_id: str = "", cta: str = "") -> str:
    """
    Convenience wrapper for the conduler publishing flow:
      - utm_source   = platform ('youtube' / 'instagram' / 'tiktok') — the
                        actual destination the click came from
      - utm_medium   = 'video'
      - utm_campaign = channel ('bitcoinfacil' / 'pandapoints')
      - utm_content  = slugified title, falling back to a short job id
                        so every video is still distinguishable even
                        without a usable title

    `cta` selects which page on the dapp the link actually points to (see
    cta.py) — e.g. cta="create_wallet" links to base_url + "/wallet"
    instead of the bare root. Empty/unknown cta falls back to base_url
    unchanged, so callers that don't pass one keep today's behavior.
    """
    content = slugify(title) or (job_id[:8] if job_id else "")
    dest_path = resolve_cta_path(cta)
    if dest_path:
        parts = urlsplit(base_url)
        if dest_path.startswith("http://") or dest_path.startswith("https://"):
            base_url = dest_path
        else:
            base_url = urlunsplit((parts.scheme, parts.netloc, dest_path, "", ""))
    return build_utm_url(
        base_url,
        source=platform,
        medium="video",
        campaign=channel or "unknown",
        content=content,
    )
