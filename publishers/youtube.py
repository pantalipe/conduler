"""
publishers/youtube.py
Faz upload de um Short/vídeo no YouTube via Data API v3 (resumable upload).
Documentação: https://developers.google.com/youtube/v3/docs/videos/insert
"""

import json
import os
import urllib.parse
import urllib.request
import logging

from auth.oauth_flow import get_token, set_token

logger = logging.getLogger(__name__)

UPLOAD_URL   = "https://www.googleapis.com/upload/youtube/v3/videos"
TOKEN_URL    = "https://oauth2.googleapis.com/token"
MAX_CHUNK    = 256 * 1024 * 1024  # 256 MB


def _refresh_if_needed(token_data: dict) -> dict:
    """Tenta renovar o access_token usando o refresh_token."""
    from config import YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET

    if not token_data.get("refresh_token"):
        return token_data

    body = urllib.parse.urlencode({
        "client_id":     YOUTUBE_CLIENT_ID,
        "client_secret": YOUTUBE_CLIENT_SECRET,
        "refresh_token": token_data["refresh_token"],
        "grant_type":    "refresh_token",
    }).encode()

    req = urllib.request.Request(TOKEN_URL, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=30) as r:
        new_data = json.loads(r.read().decode())

    token_data.update(new_data)
    set_token("youtube", token_data)
    return token_data


def publish(job: dict) -> dict:
    """
    Faz upload do vídeo do job para o YouTube.
    Retorna {"ok": bool, "url": str, "error": str}
    """
    token_data = get_token("youtube")
    if not token_data:
        return {"ok": False, "url": "", "error": "Token YouTube não encontrado. Execute /auth/youtube primeiro."}

    token_data    = _refresh_if_needed(token_data)
    access_token  = token_data.get("access_token", "")
    video_path    = job["video_path"]
    title         = job.get("title", os.path.basename(video_path))
    description   = job.get("description", "")
    tags          = job.get("tags", [])

    if not os.path.isfile(video_path):
        return {"ok": False, "url": "", "error": f"Arquivo não encontrado: {video_path}"}

    file_size = os.path.getsize(video_path)

    metadata = json.dumps({
        "snippet": {
            "title":       title[:100],
            "description": description,
            "tags":        tags,
            "categoryId":  "22",  # People & Blogs — comum para Shorts de criadores
        },
        "status": {
            "privacyStatus":           "public",
            "selfDeclaredMadeForKids": False,
        },
    }).encode()

    try:
        # 1. Iniciar upload resumível
        params = urllib.parse.urlencode({
            "uploadType": "resumable",
            "part":       "snippet,status",
        })
        init_req = urllib.request.Request(
            f"{UPLOAD_URL}?{params}",
            data=metadata,
            method="POST",
        )
        init_req.add_header("Authorization",          f"Bearer {access_token}")
        init_req.add_header("Content-Type",           "application/json; charset=UTF-8")
        init_req.add_header("X-Upload-Content-Type",  "video/mp4")
        init_req.add_header("X-Upload-Content-Length", str(file_size))

        with urllib.request.urlopen(init_req, timeout=30) as r:
            upload_uri = r.getheader("Location")

        if not upload_uri:
            return {"ok": False, "url": "", "error": "YouTube não retornou URI de upload."}

        logger.info("YouTube upload URI obtida.")

        # 2. Enviar o arquivo em um único chunk (para vídeos <= 256 MB)
        with open(video_path, "rb") as f:
            video_bytes = f.read()

        upload_req = urllib.request.Request(upload_uri, data=video_bytes, method="PUT")
        upload_req.add_header("Authorization",  f"Bearer {access_token}")
        upload_req.add_header("Content-Type",   "video/mp4")
        upload_req.add_header("Content-Length", str(file_size))

        with urllib.request.urlopen(upload_req, timeout=300) as r:
            result = json.loads(r.read().decode())

        video_id = result.get("id", "")
        url      = f"https://www.youtube.com/watch?v={video_id}"
        logger.info("YouTube publicado: %s", url)
        return {"ok": True, "url": url, "error": ""}

    except Exception as e:
        logger.error("Erro YouTube: %s", e)
        return {"ok": False, "url": "", "error": str(e)}
