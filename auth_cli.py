"""
auth_cli.py
Script standalone para disparar o fluxo OAuth de cada plataforma.

Uso:
    python auth_cli.py youtube
    python auth_cli.py instagram
    python auth_cli.py tiktok
    python auth_cli.py status        # mostra quais tokens estão salvos
    python auth_cli.py clear youtube # apaga token salvo de uma plataforma

Pré-requisito: .env preenchido com as credenciais da plataforma desejada.
"""

import sys
import json
import os


def _load_dotenv(path=".env"):
    """Carrega variáveis do .env sem dependências externas."""
    env_path = os.path.join(os.path.dirname(__file__), path)
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key   = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


_load_dotenv()

# Importa helpers do conduler
from config import (
    TOKENS_FILE,
    YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET,
    INSTAGRAM_APP_ID, INSTAGRAM_APP_SECRET,
    TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET,
)
from auth.oauth_flow import (
    authorize_youtube,
    authorize_instagram,
    authorize_tiktok,
    load_tokens,
    clear_token,
)

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


# ── helpers ──────────────────────────────────────────────────────────────────

def _require(value: str, var_name: str):
    if not value:
        log.error("Variável de ambiente '%s' não está definida no .env.", var_name)
        sys.exit(1)


def _print_token_summary(platform: str, token_data: dict):
    """Imprime um resumo legível do token recebido."""
    print(f"\n✅  Token salvo para '{platform}'")
    safe = {k: v for k, v in token_data.items() if "secret" not in k.lower()}
    print(json.dumps(safe, indent=2, ensure_ascii=False))

    if "refresh_token" in token_data:
        print("\n💾  refresh_token presente — conduler renovará o access_token automaticamente.")
    elif platform == "instagram":
        print("\n⚠️   Token do Instagram expira em ~60 dias. Rode este script novamente para renovar.")


def _show_status():
    tokens = load_tokens()
    if not tokens:
        print("Nenhum token salvo em", TOKENS_FILE)
        return
    print(f"Tokens em {TOKENS_FILE}:\n")
    for platform, data in tokens.items():
        keys = list(data.keys())
        has_refresh = "refresh_token" in data
        expires_in  = data.get("expires_in", "?")
        print(f"  {platform:12s}  campos={keys}  refresh_token={'sim' if has_refresh else 'não'}  expires_in={expires_in}")


# ── dispatcher ────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)

    cmd = args[0].lower()

    if cmd == "status":
        _show_status()
        return

    if cmd == "clear":
        if len(args) < 2:
            log.error("Uso: python auth_cli.py clear <plataforma>")
            sys.exit(1)
        platform = args[1].lower()
        clear_token(platform)
        print(f"Token de '{platform}' removido.")
        return

    if cmd == "youtube":
        _require(YOUTUBE_CLIENT_ID,     "YOUTUBE_CLIENT_ID")
        _require(YOUTUBE_CLIENT_SECRET, "YOUTUBE_CLIENT_SECRET")
        print("Abrindo browser para autorização do YouTube...")
        print("Após aprovar, a aba pode ser fechada.\n")
        token = authorize_youtube(YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET)
        _print_token_summary("youtube", token)
        return

    if cmd == "instagram":
        _require(INSTAGRAM_APP_ID,     "INSTAGRAM_APP_ID")
        _require(INSTAGRAM_APP_SECRET, "INSTAGRAM_APP_SECRET")
        print("Abrindo browser para autorização do Instagram (Meta)...")
        print("Após aprovar, a aba pode ser fechada.\n")
        token = authorize_instagram(INSTAGRAM_APP_ID, INSTAGRAM_APP_SECRET)
        _print_token_summary("instagram", token)
        return

    if cmd == "tiktok":
        _require(TIKTOK_CLIENT_KEY,    "TIKTOK_CLIENT_KEY")
        _require(TIKTOK_CLIENT_SECRET, "TIKTOK_CLIENT_SECRET")
        print("Abrindo browser para autorização do TikTok...")
        print("Após aprovar, a aba pode ser fechada.\n")
        token = authorize_tiktok(TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET)
        _print_token_summary("tiktok", token)
        return

    log.error("Plataforma desconhecida: '%s'. Use: youtube | instagram | tiktok | status | clear", cmd)
    sys.exit(1)


if __name__ == "__main__":
    main()
