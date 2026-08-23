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


def resolve_cta_path(cta):
    """
    Returns the dApp path (or absolute URL) for a given cta id.
    Unknown or empty cta falls back to the root path ("") so publishing
    never breaks over a bad/missing cta — it just loses the CTA-specific
    targeting and links to DAPP_BASE_URL as before.
    """
    if not cta:
        return ""
    return CTA_DESTINATIONS.get(cta, "")
