"""
cta.py — closed set of CTAs a published video can point to, and the dApp
path each one resolves to.

The CTA identifier itself is declared by Rotman at video-creation time
(see rotman/core/cta.py, which must keep the same set of ids) and travels
through watch_input/ -> conduler jobs.json -> here, where it's turned into
an actual destination path for utm.build_video_utm_url().

Keep this enum in sync with rotman/core/cta.py by hand — the two repos run
as separate processes and don't share an import, so the ids are the
contract between them.
"""

import os

# cta id -> path on DAPP_BASE_URL (or a full absolute URL, for CTAs whose
# destination isn't a page on the dapp itself).
CTA_DESTINATIONS = {
    "create_wallet":          os.environ.get("CTA_PATH_CREATE_WALLET", "/wallet"),
    "try_swap":               os.environ.get("CTA_PATH_TRY_SWAP", "/bs"),
    "read_more_bitcoinfacil":  os.environ.get("CTA_PATH_READ_MORE_BITCOINFACIL", "/faq"),
    "join_community":         os.environ.get("CTA_PATH_JOIN_COMMUNITY", "/hub"),
}

DEFAULT_CTA = "join_community"

VALID_CTAS = frozenset(CTA_DESTINATIONS.keys())


def resolve_cta_path(cta, channel=""):
    """
    Returns the dApp path (or absolute URL) for a given cta id.
    Unknown or empty cta falls back to the root path ("") so publishing
    never breaks over a bad/missing cta — it just loses the CTA-specific
    targeting and links to DAPP_BASE_URL as before.

    For "join_community", the video's channel is forwarded as a `from=`
    query param on the /hub path. hub.tsx (pandapoints-dapp) reads it to
    pick which language's Telegram group to feature — bitcoinfacil -> PT,
    pandapoints -> EN — instead of pointing at Telegram directly, so the
    on-screen CTA label ("join the community at pandapointscoin.com", see
    rotman/core/cta.py) stays accurate. No channel means hub falls back to
    its own default (EN).
    """
    if not cta:
        return ""
    path = CTA_DESTINATIONS.get(cta, "")
    if path and cta == "join_community" and channel:
        separator = "&" if "?" in path else "?"
        path = f"{path}{separator}from={channel}"
    return path
