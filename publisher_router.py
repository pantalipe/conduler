"""
publisher_router.py
Recebe um job do Scheduler e chama os publishers de cada plataforma.
"""

import logging
from publishers import instagram, youtube, tiktok

logger = logging.getLogger(__name__)

_PUBLISHERS = {
    "instagram": instagram.publish,
    "youtube":   youtube.publish,
    "tiktok":    tiktok.publish,
}


def publish_job(job: dict) -> dict:
    """
    Retorna {platform: {"ok": bool, "url": str, "error": str}}
    """
    results = {}
    for platform in job.get("platforms", []):
        fn = _PUBLISHERS.get(platform)
        if not fn:
            results[platform] = {"ok": False, "url": "", "error": f"Publisher '{platform}' não implementado."}
            continue
        logger.info("Publicando em %s...", platform)
        results[platform] = fn(job)
    return results
