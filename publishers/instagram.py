"""
publishers/instagram.py
Publica um Reel no Instagram via Graph API v21.
Fluxo: upload de container → aguardar processamento → publicar.
Documentação: https://developers.facebook.com/docs/instagram-api/guides/content-publishing
"""

import json
import time
import urllib.parse
import urllib.request
import logging

from auth.oauth_flow import get_token

logger = logging.getLogger(__name__)

GRAPH = "https://graph.facebook.com/v21.0"


def _api_get(path, params):
    url = f"{GRAPH}{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode())


def _api_post(path, data):
    body = urllib.parse.urlencode(data).encode()
    req  = urllib.request.Request(f"{GRAPH}{path}", data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def publish(job: dict) -> dict:
    """
    Publica o vídeo do job como Reel no Instagram.
    Retorna {"ok": bool, "url": str, "error": str}
    """
    token_data = get_token("instagram")
    if not token_data:
        return {"ok": False, "url": "", "error": "Token Instagram não encontrado. Execute /auth/instagram primeiro."}

    access_token = token_data.get("access_token", "")
    video_path   = job["video_path"]
    title        = job.get("title", "")
    description  = job.get("description", "")
    caption      = f"{title}\n\n{description}".strip() if title else description

    try:
        # 1. Descobrir o Instagram Business Account ID
        me = _api_get("/me/accounts", {"access_token": access_token})
        page        = me["data"][0]
        page_token  = page["access_token"]
        page_id     = page["id"]

        ig_data = _api_get(f"/{page_id}", {
            "fields":       "instagram_business_account",
            "access_token": page_token,
        })
        ig_id = ig_data["instagram_business_account"]["id"]

        # 2. Criar container de mídia (Reel)
        # NOTA: video_url deve ser uma URL pública acessível.
        # Em ambiente de teste, use uma URL de hospedagem temporária.
        video_url = job.get("video_url", "")  # campo opcional — preencher antes de agendar
        if not video_url:
            return {
                "ok":    False,
                "url":   "",
                "error": "Campo 'video_url' ausente no job. O Instagram exige URL pública para upload.",
            }

        container = _api_post(f"/{ig_id}/media", {
            "media_type":   "REELS",
            "video_url":    video_url,
            "caption":      caption,
            "access_token": page_token,
        })
        container_id = container["id"]
        logger.info("Instagram container criado: %s", container_id)

        # 3. Aguardar processamento (polling)
        for _ in range(20):
            time.sleep(5)
            status = _api_get(f"/{container_id}", {
                "fields":       "status_code",
                "access_token": page_token,
            })
            if status.get("status_code") == "FINISHED":
                break
            if status.get("status_code") == "ERROR":
                return {"ok": False, "url": "", "error": "Erro no processamento do vídeo pelo Instagram."}
        else:
            return {"ok": False, "url": "", "error": "Timeout aguardando processamento Instagram."}

        # 4. Publicar
        publish_res = _api_post(f"/{ig_id}/media_publish", {
            "creation_id":  container_id,
            "access_token": page_token,
        })
        media_id = publish_res.get("id", "")
        post_url = f"https://www.instagram.com/p/{media_id}/"
        logger.info("Instagram publicado: %s", post_url)
        return {"ok": True, "url": post_url, "error": ""}

    except Exception as e:
        logger.error("Erro Instagram: %s", e)
        return {"ok": False, "url": "", "error": str(e)}
