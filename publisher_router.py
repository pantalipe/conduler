"""
publisher_router.py
Recebe um job do Scheduler e chama os publishers de cada plataforma.
"""

import logging
from publishers import instagram, youtube, tiktok
from utm import build_video_utm_url
from config import DAPP_BASE_URL

logger = logging.getLogger(__name__)

_PUBLISHERS = {
    "instagram": instagram.publish,
    "youtube":   youtube.publish,
    "tiktok":    tiktok.publish,
}


def _description_with_utm_link(job: dict, platform: str) -> str:
    """
    Appends a UTM-tagged pandapointscoin.com link to the job's description.
    Built per platform (not once for the whole job) so utm_source reflects
    where the click actually came from — the same video posted to YouTube,
    Instagram, and TikTok gets three different links.
    """
    link = build_video_utm_url(
        DAPP_BASE_URL,
        platform=platform,
        channel=job.get("channel", ""),
        title=job.get("title", ""),
        job_id=job.get("id", ""),
        cta=job.get("cta", ""),
    )
    description = job.get("description", "")
    return f"{description}\n\n{link}" if description else link


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
        platform_job = dict(job)
        platform_job["description"] = _description_with_utm_link(job, platform)
        results[platform] = fn(platform_job)
    return results

