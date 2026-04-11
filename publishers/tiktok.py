"""
publishers/tiktok.py
Publica um vídeo no TikTok via Content Posting API v2.
Documentação: https://developers.tiktok.com/doc/content-posting-api-get-started
"""

import json
import os
import urllib.parse
import urllib.request
import logging

from auth.oauth_flow import get_token, set_token

logger = logging.getLogger(__name__)

API_BASE  = "https://open.tiktokapis.com/v2"
TOKEN_URL = f"{API_BASE}/oauth/token/"


def _refresh_if_needed(token_data: dict) -> dict:
    from config import TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET

    if not token_data.get("refresh_token"):
        return token_data

    body = urllib.parse.urlencode({
        "client_key":    TIKTOK_CLIENT_KEY,
        "client_secret": TIKTOK_CLIENT_SECRET,
        "grant_type":    "refresh_token",
        "refresh_token": token_data["refresh_token"],
    }).encode()

    req = urllib.request.Request(TOKEN_URL, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=30) as r:
        new_data = json.loads(r.read().decode())

    token_data.update(new_data.get("data", new_data))
    set_token("tiktok", token_data)
    return token_data


def _api_post(endpoint: str, access_token: str, payload: dict) -> dict:
    body = json.dumps(payload).encode()
    req  = urllib.request.Request(f"{API_BASE}{endpoint}", data=body, method="POST")
    req.add_header("Authorization", f"Bearer {access_token}")
    req.add_header("Content-Type",  "application/json; charset=UTF-8")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def publish(job: dict) -> dict:
    """
    Publica o vídeo do job no TikTok.
    Retorna {"ok": bool, "url": str, "error": str}
    """
    token_data = get_token("tiktok")
    if not token_data:
        return {"ok": False, "url": "", "error": "Token TikTok não encontrado. Execute /auth/tiktok primeiro."}

    token_data   = _refresh_if_needed(token_data)
    access_token = token_data.get("access_token", "")
    video_path   = job["video_path"]
    title        = job.get("title", "")
    description  = job.get("description", "")

    if not os.path.isfile(video_path):
        return {"ok": False, "url": "", "error": f"Arquivo não encontrado: {video_path}"}

    file_size = os.path.getsize(video_path)

    try:
        # 1. Iniciar upload de vídeo (FILE_UPLOAD)
        init_payload = {
            "post_info": {
                "title":           (f"{title} {description}".strip())[:2200],
                "privacy_level":   "PUBLIC_TO_EVERYONE",
                "disable_duet":    False,
                "disable_comment": False,
                "disable_stitch":  False,
            },
            "source_info": {
                "source":            "FILE_UPLOAD",
                "video_size":        file_size,
                "chunk_size":        file_size,
                "total_chunk_count": 1,
            },
        }

        init_res = _api_post("/post/publish/video/init/", access_token, init_payload)

        if init_res.get("error", {}).get("code") != "ok":
            msg = init_res.get("error", {}).get("message", str(init_res))
            return {"ok": False, "url": "", "error": f"TikTok init falhou: {msg}"}

        upload_url = init_res["data"]["upload_url"]
        publish_id = init_res["data"]["publish_id"]

        logger.info("TikTok upload URL obtida. publish_id=%s", publish_id)

        # 2. Enviar o arquivo
        with open(video_path, "rb") as f:
            video_bytes = f.read()

        upload_req = urllib.request.Request(upload_url, data=video_bytes, method="PUT")
        upload_req.add_header("Content-Type",   "video/mp4")
        upload_req.add_header("Content-Length", str(file_size))
        upload_req.add_header("Content-Range",  f"bytes 0-{file_size - 1}/{file_size}")

        with urllib.request.urlopen(upload_req, timeout=300):
            pass

        logger.info("TikTok video enviado.")

        # A URL definitiva do post nao e retornada imediatamente pela API —
        # o TikTok processa de forma assincrona.
        return {
            "ok":    True,
            "url":   f"https://www.tiktok.com/ (publish_id: {publish_id})",
            "error": "",
        }

    except Exception as e:
        logger.error("Erro TikTok: %s", e)
        return {"ok": False, "url": "", "error": str(e)}
