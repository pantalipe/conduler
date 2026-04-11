"""
auth/oauth_flow.py
Fluxo OAuth 2.0 generico para Instagram, YouTube e TikTok.
Abre o browser, sobe um servidor local temporario para capturar o callback
e salva o token em auth/tokens.json.
"""

import json
import os
import urllib.parse
import urllib.request
import webbrowser
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

from config import OAUTH_REDIRECT_PORT, OAUTH_REDIRECT_URI, TOKENS_FILE

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Tokens
# ------------------------------------------------------------------

def load_tokens():
    try:
        with open(TOKENS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        logger.error("Erro ao carregar tokens: %s", e)
        return {}


def save_tokens(tokens: dict):
    os.makedirs(os.path.dirname(TOKENS_FILE), exist_ok=True)
    with open(TOKENS_FILE, "w", encoding="utf-8") as f:
        json.dump(tokens, f, indent=2, ensure_ascii=False)


def get_token(platform: str):
    return load_tokens().get(platform)


def set_token(platform: str, token_data: dict):
    tokens = load_tokens()
    tokens[platform] = token_data
    save_tokens(tokens)
    logger.info("Token salvo para %s", platform)


def clear_token(platform: str):
    tokens = load_tokens()
    tokens.pop(platform, None)
    save_tokens(tokens)


# ------------------------------------------------------------------
# Servidor local de callback
# ------------------------------------------------------------------

_callback_result = {}


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        _callback_result["code"]  = params.get("code", [None])[0]
        _callback_result["error"] = params.get("error", [None])[0]

        body = b"<h2>Autorizado! Pode fechar esta aba.</h2>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # silencia log do servidor temporario


def _wait_for_callback(timeout=120):
    """Sobe um servidor HTTP temporario e aguarda o redirect OAuth."""
    server = HTTPServer(("127.0.0.1", OAUTH_REDIRECT_PORT), _CallbackHandler)
    server.timeout = timeout

    def serve():
        server.handle_request()

    t = Thread(target=serve, daemon=True)
    t.start()
    t.join(timeout=timeout + 2)
    server.server_close()
    return _callback_result.get("code"), _callback_result.get("error")


# ------------------------------------------------------------------
# Helpers de troca de codigo por token (POST via urllib)
# ------------------------------------------------------------------

def _post_json(url, data: dict, headers: dict = None):
    body = urllib.parse.urlencode(data).encode()
    req  = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


# ------------------------------------------------------------------
# Fluxos por plataforma
# ------------------------------------------------------------------

def authorize_instagram(app_id: str, app_secret: str):
    """
    Inicia o fluxo OAuth do Instagram Basic Display / Graph API.
    Escopo minimo para publicar Reels: pages_show_list, instagram_basic,
    instagram_content_publish.
    """
    params = urllib.parse.urlencode({
        "client_id":     app_id,
        "redirect_uri":  OAUTH_REDIRECT_URI,
        "scope":         "pages_show_list,instagram_basic,instagram_content_publish",
        "response_type": "code",
    })
    auth_url = f"https://www.facebook.com/v21.0/dialog/oauth?{params}"
    webbrowser.open(auth_url)
    logger.info("Aguardando autorizacao Instagram no browser...")

    code, error = _wait_for_callback()
    if error or not code:
        raise RuntimeError(f"Instagram OAuth falhou: {error}")

    token_data = _post_json(
        "https://graph.facebook.com/v21.0/oauth/access_token",
        {
            "client_id":     app_id,
            "client_secret": app_secret,
            "redirect_uri":  OAUTH_REDIRECT_URI,
            "code":          code,
        }
    )
    set_token("instagram", token_data)
    return token_data


def authorize_youtube(client_id: str, client_secret: str):
    """
    Inicia o fluxo OAuth do YouTube Data API v3.
    Escopo: https://www.googleapis.com/auth/youtube.upload
    """
    params = urllib.parse.urlencode({
        "client_id":     client_id,
        "redirect_uri":  OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope":         "https://www.googleapis.com/auth/youtube.upload",
        "access_type":   "offline",
        "prompt":        "consent",
    })
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{params}"
    webbrowser.open(auth_url)
    logger.info("Aguardando autorizacao YouTube no browser...")

    code, error = _wait_for_callback()
    if error or not code:
        raise RuntimeError(f"YouTube OAuth falhou: {error}")

    token_data = _post_json(
        "https://oauth2.googleapis.com/token",
        {
            "client_id":     client_id,
            "client_secret": client_secret,
            "redirect_uri":  OAUTH_REDIRECT_URI,
            "grant_type":    "authorization_code",
            "code":          code,
        }
    )
    set_token("youtube", token_data)
    return token_data


def authorize_tiktok(client_key: str, client_secret: str):
    """
    Inicia o fluxo OAuth do TikTok Content Posting API.
    Escopo: video.upload
    """
    params = urllib.parse.urlencode({
        "client_key":    client_key,
        "redirect_uri":  OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope":         "video.upload",
    })
    auth_url = f"https://www.tiktok.com/v2/auth/authorize/?{params}"
    webbrowser.open(auth_url)
    logger.info("Aguardando autorizacao TikTok no browser...")

    code, error = _wait_for_callback()
    if error or not code:
        raise RuntimeError(f"TikTok OAuth falhou: {error}")

    token_data = _post_json(
        "https://open.tiktokapis.com/v2/oauth/token/",
        {
            "client_key":    client_key,
            "client_secret": client_secret,
            "code":          code,
            "grant_type":    "authorization_code",
            "redirect_uri":  OAUTH_REDIRECT_URI,
        }
    )
    set_token("tiktok", token_data)
    return token_data
